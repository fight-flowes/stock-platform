from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import re
from typing import Any, Callable

from .ids import stable_id
from .market_event_judge import MarketEventJudgeDecision


_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")
_NORMALIZE_RE = re.compile(r"[\s\u3000\"'“”‘’（）()，,。:：;；、】【/\\-]+")
_INDUSTRY_HINT_RE = re.compile(r"(板块|行业|概念|期货|价格|会议|海关总署|国家能源局|协会|出口|库存|产量|销量)")


@dataclass(slots=True)
class ClusterMember:
    row: dict[str, Any]
    merge_method: str
    merge_confidence: float | None = None
    merge_reason: str = ""
    is_primary: bool = False


@dataclass(slots=True)
class EventCluster:
    cluster_key: str
    members: list[ClusterMember] = field(default_factory=list)
    merge_method: str = "rule"

    @property
    def primary_member(self) -> ClusterMember:
        return self.members[0]

    @property
    def items(self) -> list[dict[str, Any]]:
        return [member.row for member in self.members]


class MarketEventBuilder:
    def __init__(
        self,
        *,
        judge: Callable[[dict[str, Any], dict[str, Any]], MarketEventJudgeDecision | None] | None = None,
    ) -> None:
        self._judge = judge

    def build(self, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        bucketed: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            bucket_key = self._build_candidate_bucket(row)
            bucketed.setdefault(bucket_key, []).append(row)

        clusters: list[EventCluster] = []
        for bucket_rows in bucketed.values():
            for row in sorted(bucket_rows, key=self._row_sort_key, reverse=True):
                matched_cluster: EventCluster | None = None
                matched_decision: MarketEventJudgeDecision | None = None
                candidate_bucket_key = self._build_candidate_bucket(row)
                candidate_clusters = [item for item in clusters if item.cluster_key == candidate_bucket_key]
                for cluster in candidate_clusters:
                    decision = self._decide_same_event(row, cluster.primary_member.row)
                    if decision.same_event:
                        matched_cluster = cluster
                        matched_decision = decision
                        break
                if matched_cluster is None:
                    clusters.append(
                        EventCluster(
                            cluster_key=candidate_bucket_key,
                            members=[
                                ClusterMember(
                                    row=row,
                                    merge_method="rule",
                                    merge_reason="cluster_primary",
                                    is_primary=True,
                                )
                            ],
                            merge_method="rule",
                        )
                    )
                    continue
                matched_cluster.members.append(
                    ClusterMember(
                        row=row,
                        merge_method=matched_decision.merge_method,
                        merge_confidence=matched_decision.confidence if matched_decision.merge_method == "llm" else None,
                        merge_reason=matched_decision.reason,
                        is_primary=False,
                    )
                )
                if matched_decision.merge_method == "llm":
                    matched_cluster.merge_method = "llm"

        now = datetime.now(timezone.utc).isoformat()
        market_events: list[dict[str, Any]] = []
        members: list[dict[str, Any]] = []
        for cluster in clusters:
            items = cluster.items
            primary_item = self._pick_primary_item(items)
            primary_member = next(
                (member for member in cluster.members if str(member.row.get("event_id") or "") == str(primary_item.get("event_id") or "")),
                cluster.primary_member,
            )
            event_type = self._pick_event_type(items)
            event_scope = self._pick_event_scope(items)
            merge_key = self._build_market_cluster_key(cluster)
            event_key = self._make_event_key(merge_key, primary_item)
            affected_stocks = self._merge_affected_stocks(items)
            affected_industries = self._merge_string_lists(item.get("affected_industries") for item in items)
            affected_themes = self._merge_string_lists(item.get("affected_themes") for item in items)
            event_name = str(primary_item.get("event_name") or "")
            event_content = self._pick_longest_text(item.get("event_content") for item in items)
            primary_theme = affected_themes[0] if affected_themes else self._infer_primary_theme(event_name, event_content)
            primary_industry = affected_industries[0] if affected_industries else self._infer_primary_industry(primary_theme, event_name, event_content)
            active_dates = self._sorted_report_dates(items)
            first_seen_date = active_dates[0] if active_dates else ""
            latest_active_date = active_dates[-1] if active_dates else ""
            timeline = self._build_timeline(items)
            source_event_ids = sorted({str(item.get("event_id") or "").strip() for item in items if str(item.get("event_id") or "").strip()})
            market_events.append(
                {
                    "event_key": event_key,
                    "event_name": event_name,
                    "event_time_text": str(primary_item.get("event_time_text") or ""),
                    "event_content": event_content,
                    "event_type": event_type,
                    "event_scope": event_scope,
                    "scope_reason": self._pick_longest_text(item.get("scope_reason") for item in items),
                    "primary_industry": primary_industry,
                    "primary_theme": primary_theme,
                    "risk_summary": self._pick_longest_text(item.get("risk_summary") for item in items),
                    "affected_stock_count": len(affected_stocks),
                    "affected_stocks_preview_json": affected_stocks[:3],
                    "affected_stocks_json": affected_stocks,
                    "affected_industries_json": affected_industries,
                    "affected_themes_json": affected_themes,
                    "source_report_count": len({str(item.get("report_id") or "").strip() for item in items if str(item.get("report_id") or "").strip()}),
                    "source_event_count": len(source_event_ids),
                    "source_event_ids_json": source_event_ids,
                    "first_seen_date": first_seen_date,
                    "latest_active_date": latest_active_date,
                    "active_dates_json": active_dates,
                    "is_cross_stock": len(affected_stocks) > 1,
                    # is_active is DEPRECATED — the old "5 days since latest_active_date"
                    # heuristic produced misleading "发酵中" badges in the UI (see
                    # apps/calenderapp/frontend git history). Kept on the model so
                    # historical rows stay readable and the column doesn't need a
                    # schema migration; new rows always write False until a fresh
                    # definition replaces this. ``_is_active_date`` is kept as
                    # historical reference but no longer called.
                    "is_active": False,
                    "timeline_json": timeline,
                    "merge_method": cluster.merge_method,
                    "merge_confidence": primary_member.merge_confidence,
                    "merge_reason": primary_member.merge_reason,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            for member in cluster.members:
                members.append(
                    {
                        "event_key": event_key,
                        "event_id": str(member.row.get("event_id") or ""),
                        "report_id": str(member.row.get("report_id") or ""),
                        "is_primary": str(member.row.get("event_id") or "") == str(primary_item.get("event_id") or ""),
                        "merge_method": member.merge_method,
                        "merge_confidence": member.merge_confidence,
                        "merge_reason": member.merge_reason,
                        "created_at": now,
                    }
                )
        return market_events, members

    def _row_sort_key(self, row: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
        return (
            1 if str(row.get("source_url") or "").strip() else 0,
            1 if str(row.get("source_name") or "").strip() else 0,
            len(row.get("affected_stocks") or []),
            len(row.get("affected_industries") or []),
            len(row.get("affected_themes") or []),
            len(str(row.get("evidence_text") or row.get("event_content") or "")),
        )

    def _decide_same_event(self, left: dict[str, Any], right: dict[str, Any]) -> MarketEventJudgeDecision:
        if self._build_strict_rule_key(left) == self._build_strict_rule_key(right):
            return MarketEventJudgeDecision(True, 1.0, "strict_rule_match", "rule")

        left_type = self._normalize_event_type(left)
        right_type = self._normalize_event_type(right)
        if left_type != right_type:
            return MarketEventJudgeDecision(False, 1.0, "different_event_type", "rule")

        if left_type == "stock":
            left_stock = self._primary_stock_code(left)
            right_stock = self._primary_stock_code(right)
            if left_stock and right_stock and left_stock != right_stock:
                return MarketEventJudgeDecision(False, 1.0, "different_stock_code", "rule")

        left_time = str(left.get("event_time_normalized") or "")
        right_time = str(right.get("event_time_normalized") or "")
        if left_time and right_time and left_time != right_time:
            return MarketEventJudgeDecision(False, 1.0, "different_event_date", "rule")

        left_source = self._normalize_text(str(left.get("source_url") or "") or str(left.get("source_name") or ""))
        right_source = self._normalize_text(str(right.get("source_url") or "") or str(right.get("source_name") or ""))
        if left_source and right_source:
            if left_source == right_source and self._number_signature(left) == self._number_signature(right):
                return MarketEventJudgeDecision(True, 0.95, "same_source_and_numbers", "rule")
            if left_source != right_source and self._number_signature(left) != self._number_signature(right):
                return MarketEventJudgeDecision(False, 0.95, "different_source_and_numbers", "rule")

        if self._normalized_evidence(left) and self._normalized_evidence(left) == self._normalized_evidence(right):
            return MarketEventJudgeDecision(True, 0.95, "same_normalized_evidence", "rule")

        if not self._is_ambiguous_candidate(left, right):
            return MarketEventJudgeDecision(False, 0.8, "rule_not_similar_enough", "rule")

        if self._judge is None:
            return MarketEventJudgeDecision(False, 0.5, "no_llm_judge_configured", "rule")

        decision = self._judge(left, right)
        if decision is not None:
            return decision
        return MarketEventJudgeDecision(False, 0.5, "llm_judge_skipped", "rule")

    def _is_ambiguous_candidate(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        numbers_match = bool(self._number_signature(left) and self._number_signature(left) == self._number_signature(right))
        category_match = self._category_key(left) and self._category_key(left) == self._category_key(right)
        text_overlap = self._text_overlap_score(self._normalized_evidence(left), self._normalized_evidence(right)) >= 0.55
        if self._normalize_event_type(left) == "industry":
            return bool(numbers_match or (category_match and text_overlap))
        return bool(category_match and (numbers_match or text_overlap))

    def _build_candidate_bucket(self, row: dict[str, Any]) -> str:
        event_type = self._normalize_event_type(row)
        time_key = str(row.get("event_time_normalized") or "") or self._extract_iso_date(str(row.get("report_date") or ""))
        source_key = self._normalize_text(str(row.get("source_url") or "") or str(row.get("source_name") or ""))
        category_key = self._category_key(row)
        if event_type == "industry":
            return stable_id("industry_bucket", time_key, source_key or category_key or self._number_signature(row) or "misc")
        return stable_id("stock_bucket", self._primary_stock_code(row), time_key)

    def _build_strict_rule_key(self, row: dict[str, Any]) -> str:
        event_type = self._normalize_event_type(row)
        time_key = str(row.get("event_time_normalized") or "") or self._extract_iso_date(str(row.get("report_date") or ""))
        source_key = self._normalize_text(str(row.get("source_url") or "") or str(row.get("source_name") or ""))
        evidence_key = self._normalized_evidence(row)
        numbers_key = self._number_signature(row)
        category_key = self._category_key(row)
        if event_type == "industry":
            if source_key:
                return stable_id("industry_strict", time_key, source_key, category_key, numbers_key)
            return stable_id("industry_strict", time_key, category_key, numbers_key, evidence_key[:96])
        stock_code = self._primary_stock_code(row)
        if source_key:
            return stable_id("stock_strict", stock_code, time_key, source_key, numbers_key)
        return stable_id("stock_strict", stock_code, time_key, numbers_key, evidence_key[:96])

    def _build_market_cluster_key(self, cluster: EventCluster) -> str:
        primary = cluster.primary_member.row
        return stable_id(
            self._normalize_event_type(primary),
            self._extract_iso_date(str(primary.get("report_date") or "")) or str(primary.get("event_time_normalized") or ""),
            self._category_key(primary),
            self._number_signature(primary),
            ",".join(sorted(str(member.row.get("event_id") or "") for member in cluster.members)),
        )

    def _make_event_key(self, merge_key: str, row: dict[str, Any]) -> str:
        event_type = self._normalize_event_type(row)
        title = self._normalize_text(str(row.get("event_name") or ""))[:48]
        title = re.sub(r"[^0-9a-z]+", "_", title).strip("_")
        merge_hash = stable_id(merge_key)[:12]
        if title:
            return f"mkt_{event_type}_{title}_{merge_hash}"
        return f"mkt_{event_type}_{merge_hash}"

    def _pick_primary_item(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return max(items, key=self._row_sort_key)

    def _pick_event_type(self, items: list[dict[str, Any]]) -> str:
        types = [self._normalize_event_type(item) for item in items]
        if "industry" in types:
            return "industry"
        return "stock"

    def _normalize_event_type(self, row_or_value: Any) -> str:
        if isinstance(row_or_value, dict):
            raw = str(row_or_value.get("event_type") or "").strip().lower()
            if raw in {"industry", "stock"}:
                return raw
            return self._infer_event_type_from_row(row_or_value)
        return "industry" if str(row_or_value or "").strip().lower() == "industry" else "stock"

    def _pick_event_scope(self, items: list[dict[str, Any]]) -> str:
        priority = {"mixed": 4, "industry": 3, "macro": 2, "stock": 1, "": 0}
        best = ""
        for item in items:
            value = str(item.get("event_scope") or "").strip().lower()
            if priority.get(value, 0) > priority.get(best, 0):
                best = value
        return best

    def _merge_affected_stocks(self, items: list[dict[str, Any]]) -> list[dict[str, str]]:
        merged: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in items:
            for stock in item.get("affected_stocks") or []:
                if not isinstance(stock, dict):
                    continue
                stock_code = str(stock.get("stock_code") or "").strip()
                stock_name = str(stock.get("stock_name") or "").strip()
                dedupe_key = stock_code or stock_name
                if not dedupe_key or dedupe_key in seen:
                    continue
                merged.append({"stock_code": stock_code, "stock_name": stock_name})
                seen.add(dedupe_key)
        return merged

    def _merge_string_lists(self, values: Any) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for raw_items in values:
            items = raw_items if isinstance(raw_items, list) else []
            for raw in items:
                text = str(raw or "").strip()
                normalized = text.lower()
                if not text or normalized in seen:
                    continue
                merged.append(text)
                seen.add(normalized)
        return merged

    def _sorted_report_dates(self, items: list[dict[str, Any]]) -> list[str]:
        dates = {
            self._extract_iso_date(str(item.get("report_date") or ""))
            for item in items
            if self._extract_iso_date(str(item.get("report_date") or ""))
        }
        return sorted(date_value for date_value in dates if date_value)

    def _build_timeline(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        timeline_map: dict[str, dict[str, Any]] = {}
        for item in items:
            report_date = self._extract_iso_date(str(item.get("report_date") or "")) or str(item.get("report_date") or "")
            if not report_date:
                continue
            entry = timeline_map.setdefault(
                report_date,
                {
                    "date": report_date,
                    "stocks": [],
                    "affected_stock_count": 0,
                    "source_report_count": 0,
                },
            )
            seen_codes = {str(stock.get("stock_code") or stock.get("stock_name") or "") for stock in entry["stocks"]}
            for stock in item.get("affected_stocks") or []:
                if not isinstance(stock, dict):
                    continue
                dedupe_key = str(stock.get("stock_code") or stock.get("stock_name") or "")
                if not dedupe_key or dedupe_key in seen_codes:
                    continue
                entry["stocks"].append(
                    {
                        "stock_code": str(stock.get("stock_code") or ""),
                        "stock_name": str(stock.get("stock_name") or ""),
                    }
                )
                seen_codes.add(dedupe_key)
            entry["affected_stock_count"] = len(entry["stocks"])
            entry["source_report_count"] = entry.get("source_report_count", 0) + 1
        return [timeline_map[key] for key in sorted(timeline_map)]

    def _pick_longest_text(self, values: Any) -> str:
        texts = [str(value or "").strip() for value in values if str(value or "").strip()]
        if not texts:
            return ""
        return max(texts, key=len)

    def _pick_first_string(self, values: Any) -> str:
        items = values if isinstance(values, list) else []
        for raw in items:
            text = str(raw or "").strip()
            if text:
                return text
        return ""

    def _primary_stock_code(self, row: dict[str, Any]) -> str:
        affected_stocks = row.get("affected_stocks") or []
        for stock in affected_stocks:
            if not isinstance(stock, dict):
                continue
            stock_code = str(stock.get("stock_code") or "").strip()
            if stock_code:
                return stock_code
        return str(row.get("stock_code") or "").strip()

    def _number_signature(self, row: dict[str, Any]) -> str:
        text = " ".join(
            [
                str(row.get("event_name") or ""),
                str(row.get("evidence_text") or ""),
                str(row.get("event_content") or ""),
            ]
        )
        return ",".join(sorted(set(_NUMBER_RE.findall(text))))

    def _category_key(self, row: dict[str, Any]) -> str:
        primary_theme = self._pick_first_string(row.get("affected_themes"))
        primary_industry = self._pick_first_string(row.get("affected_industries"))
        return self._normalize_text(primary_theme or primary_industry or self._infer_category_hint(row))

    def _infer_category_hint(self, row: dict[str, Any]) -> str:
        text = " ".join(
            [
                str(row.get("event_name") or ""),
                str(row.get("event_content") or ""),
                str(row.get("evidence_text") or ""),
            ]
        )
        match = _INDUSTRY_HINT_RE.search(text)
        if match:
            return match.group(1)
        return text[:32]

    def _infer_event_type_from_row(self, row: dict[str, Any]) -> str:
        scope = str(row.get("event_scope") or "").strip().lower()
        if scope in {"industry", "macro", "mixed"}:
            return "industry"
        if scope == "stock":
            return "stock"
        if row.get("affected_industries") or row.get("affected_themes"):
            return "industry"
        affected_stocks = row.get("affected_stocks") or []
        valid_stocks = [
            stock for stock in affected_stocks
            if isinstance(stock, dict) and (str(stock.get("stock_code") or "").strip() or str(stock.get("stock_name") or "").strip())
        ]
        if len(valid_stocks) > 1:
            return "industry"
        return "stock"

    def _normalized_evidence(self, row: dict[str, Any]) -> str:
        return self._normalize_text(str(row.get("evidence_text") or "") or str(row.get("event_content") or "") or str(row.get("event_name") or ""))

    def _normalize_text(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        raw = raw.replace("nvidia", "英伟达")
        return _NORMALIZE_RE.sub("", raw)

    def _text_overlap_score(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
        if shorter in longer:
            return len(shorter) / max(len(longer), 1)
        overlap_chars = len(set(shorter) & set(longer))
        return overlap_chars / max(len(set(shorter)), 1)

    def _infer_primary_theme(self, event_name: str, event_content: str) -> str:
        text = f"{event_name} {event_content}"
        theme_keywords = (
            "超级电容",
            "机器人",
            "工业机器人",
            "REITs",
            "煤炭",
            "煤矿安全",
            "电力",
            "算力",
            "白酒",
            "区块链",
            "半导体",
            "光刻胶",
            "储能",
            "风电",
            "消费",
        )
        for keyword in theme_keywords:
            if keyword in text:
                return keyword
        return ""

    def _infer_primary_industry(self, primary_theme: str, event_name: str, event_content: str) -> str:
        theme_industry_map = {
            "超级电容": "电子",
            "机器人": "机械设备",
            "工业机器人": "机械设备",
            "REITs": "房地产",
            "煤炭": "煤炭",
            "煤矿安全": "煤炭",
            "电力": "公用事业",
            "算力": "计算机",
            "白酒": "食品饮料",
            "区块链": "计算机",
            "半导体": "电子",
            "光刻胶": "电子",
            "储能": "电力设备",
            "风电": "电力设备",
            "消费": "商贸零售",
        }
        if primary_theme in theme_industry_map:
            return theme_industry_map[primary_theme]
        text = f"{event_name} {event_content}"
        if "煤" in text:
            return "煤炭"
        if "电" in text:
            return "公用事业"
        return ""

    def _is_active_date(self, latest_active_date: str) -> bool:
        """DEPRECATED — historical reference only.

        This was the original heuristic backing the ``is_active`` column /
        the frontend "发酵中" badge: "the event is active if the latest
        report mentioning it landed within the last 5 days". The badge has
        been removed and the writer no longer calls this — kept here so a
        future redesign can compare its definition against alternatives
        without spelunking through git history.
        """
        parsed = self._parse_date_like(latest_active_date)
        if parsed is None:
            return False
        return (date.today() - parsed).days <= 5

    def _parse_date_like(self, value: Any) -> date | None:
        raw = self._extract_iso_date(str(value or ""))
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _extract_iso_date(self, text: str) -> str:
        match = re.search(r"(20\d{2}-\d{2}-\d{2})", str(text or ""))
        return match.group(1) if match else ""

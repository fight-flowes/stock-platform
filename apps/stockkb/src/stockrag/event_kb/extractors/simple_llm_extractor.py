from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

import requests

from ..config import EventKBSettings
from ..ids import stable_id
from ..schemas import (
    MarkdownDocument,
    SimpleAffectedStock,
    SimpleEventCandidate,
    SimpleReportSummary,
)
from .event_normalizer import normalize_simple_events


_SKIP_SECTION_TOKENS = (
    "免责声明",
    "搜索记录",
    "数据来源说明",
)
_SKIP_TEXT_TOKENS = (
    "多源搜索执行说明",
    "时效性窗口定义",
    "搜索工具",
    "搜索次数",
)
_PRIORITY_SECTION_TOKENS = (
    "涨停原因",
    "涨停逻辑",
    "核心逻辑",
    "催化",
    "事件",
    "概念",
    "行业",
    "产业链",
    "数据",
    "公告",
    "风险提示",
)
_PRIORITY_TEXT_TOKENS = (
    "海关总署",
    "统计局",
    "工信部",
    "国家能源局",
    "发改委",
    "行业协会",
    "交易所",
    "公司公告",
    "公告称",
    "披露",
    "发布数据显示",
    "出口",
    "销量",
    "产量",
    "产销",
    "库存",
    "价格",
    "期货",
    "涨价",
    "提价",
    "订单",
    "签约",
    "中标",
    "投产",
    "投运",
    "增资",
    "并购",
    "回购",
    "REITs",
    "重大会议",
    "专项整改",
    "安全会议",
    "英伟达",
    "NVIDIA",
    "GB300",
    "Rubin",
    "机器人",
    "工业机器人",
    "超级电容",
    "算力",
    "主题催化",
    "概念股",
)
_DISCOURAGED_TEXT_TOKENS = (
    "高位震荡",
    "放量",
    "缩量",
    "连板",
    "二板",
    "回调结束",
    "技术面",
    "盘面",
)
_DATE_LIKE_RE = re.compile(r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}|\d{1,2}月\d{1,2}日)")
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", re.DOTALL)
_EVENT_SECTION_RE = re.compile(r"(?:^| / )(事件\d+[：:].+)$")
_SOURCE_LINE_RE = re.compile(r"^(?:来源|来源名称|信息来源)[：:]\s*(.+?)\s*$")
_URL_LINE_RE = re.compile(r"^(?:URL|链接|来源链接)[：:]\s*(https?://\S+)\s*$", re.IGNORECASE)
_MAX_SIMPLE_EVENTS = 8

_SIMPLE_SYSTEM_PROMPT = """你是A股涨停分析报告的事件抽取器。
你的首要目标不是“少输出”，而是“不要漏掉任何真正重要的事件”。

你要先尽量找全报告里所有符合定义的事件，再做去重和压缩。

只保留下面这些信息：
1. event_name：事件名称
2. event_time_text：事件时间原文，可以不完全标准
3. event_content：用一两句话说清楚发生了什么、为什么重要
4. event_scope：事件范围，只能是 stock | industry | mixed | macro
5. scope_reason：一句话说明为什么这样判断
6. source_name：事件来源平台/媒体/发布方；如果报告里没有明确来源，输出空字符串
7. source_url：事件原始链接；如果报告里没有明确URL，输出空字符串
8. affected_stocks：受影响个股列表
9. affected_industries：受影响行业列表
10. affected_themes：受影响主题/概念列表
11. core_logic：输出“上涨逻辑”报告级摘要，用 2-4 句写成可读的短段落，讲清楚为什么涨
12. risk_summary：输出“风险摘要”报告级摘要，用 2-4 句写成可读的短段落，讲清楚主要不确定性

事件定义：
- 事件必须是“外部发生的新信息”或“能够改变估值、预期、交易情绪、资金行为的触发器”
- 如果一条信息能解释为什么股票或板块走强，它通常应被视为候选事件

必须重点检查、优先保留的事件类型：
- 宏观政策、产业政策、监管变化、重要会议
- 公司公告、增资、订单、项目进展、投产、并购、回购、REITs进展
- 事故、停产、整改、供应链变化
- 官方数据、行业数据、统计数据、协会数据、海关数据、出口数据、产销数据、库存数据、价格数据
- 期货价格变化、现货价格变化、资金行为
- 技术发布、产业链催化、主题源头事件

特别要求：
- 如果报告里出现海关总署、统计局、工信部、国家能源局、行业协会、交易所、公司公告等发布的新数据或新变化，默认优先保留
- 如果报告里出现出口大增、销量增长、产量增长、装机量增长、库存变化、价格上涨、期货大涨等行业数据，并且这些信息会影响板块或个股预期，也要保留
- 如果“券商研报/研报指出/机构观点”段落里引用了明确的新事实，也必须保留这些事实本身，例如：
  - 官方或行业新数据
  - 海外龙头新品、技术架构升级、产品从选配变标配
  - 产业链需求放量时间点
  - 公司公告、项目、订单、价格、供需变化
- 像“英伟达 GB300 / Rubin 带动超级电容需求升级”这类有清晰产业源头的主题催化，属于正式事件，不要漏掉
- 不要因为“想精简输出”而省略符合定义的事件

不要输出：
- 技术形态、涨停、连板、回调、整理、放量、缩量这类盘面描述本身
- 纯观点、纯情绪、纯研报态度；但如果研报段落中包含明确的新事实或数据，要保留事实，不要把它误删
- 没有新信息的复盘结论

抽取规则：
- 同一底层事件只保留一条，不要重复
- 如果时间不标准，保留原文即可，不要硬改
- 你必须判断事件范围：
  - stock：主要影响单一公司，核心信息是公司公告、订单、增资、业绩、项目、股东变化等
  - industry：主要影响一个行业、板块或多只股票，核心信息是政策、行业数据、价格、会议、主题催化等
  - mixed：既有明确行业催化，又明确落到若干重点公司
  - macro：宏观、监管、跨行业制度变化
- 不要把所有事件都判成 stock；只要核心影响对象明显是行业/板块/主题，就应优先判为 industry 或 mixed
- core_logic 必须是“可读的短段落摘要”，不是标签。禁止只输出“板块驱动型 / 事件驱动型 / 情绪驱动型 / 资金驱动型 / 个股驱动型”这类分类词
- core_logic 优先覆盖：板块/主题催化、关键外部事件、公司自身受益点或兑现抓手
- risk_summary 只允许一条报告级摘要，不要拆成多条风险事件
- core_logic 和 risk_summary 都写成 2-4 句短段落，总长度控制在大约 60-220 字，基于报告事实，不要空泛发挥
- 优先保证召回完整，最多输出 8 条正式事件
- 如果某条行业/官方数据明显是板块催化源头，不要漏掉

正例：
- 海关总署发布数据显示工业机器人出口大增
- 国家能源局发布用电量或行业预测数据
- 公司公告完成增资或签订大额订单
- 交易所或公司披露 REITs 项目进展
- 期货价格大涨强化供给收缩或涨价预期

反例：
- 二板涨停
- 高位震荡放量
- 回调结束
- 资金关注度提升
- 券商看好
- 板块走强

输出 JSON：
{
  "events": [
    {
      "event_name": "...",
      "event_time_text": "...",
      "event_content": "...",
      "event_scope": "stock|industry|mixed|macro",
      "scope_reason": "...",
      "source_name": "...",
      "source_url": "...",
      "affected_stocks": [
        {"stock_code": "...", "stock_name": "..."}
      ],
      "affected_industries": ["..."],
      "affected_themes": ["..."],
      "anchor_block_id": "...",
      "evidence_text": "...",
      "confidence_score": 0.0,
      "needs_review": false,
      "review_reason": ""
    }
  ],
  "core_logic": "...",
  "risk_summary": "..."
}

只能返回 JSON，不要解释。
"""

_SIMPLE_REVIEW_PROMPT = """你是A股涨停分析报告的事件补漏检查器。
你的任务不是重做整份抽取，而是检查“当前已抽取事件”是否有遗漏。

输入里会给你：
- report_date
- primary_stock_code
- primary_stock_name
- blocks：候选正文块
- existing_events：第一轮已经抽到的事件

你的目标：
- 只输出“第一轮漏掉、但应该保留”的事件
- 特别检查官方数据、行业数据、海关数据、出口数据、产销数据、库存数据、价格数据、期货数据、资金行为、技术发布、公司公告
- 特别检查“研报指出/机构观点”里面是否埋着明确的新事实，例如技术架构升级、产品标准变化、放量时间点、官方或行业数据
- 如果这些内容能解释个股或板块走强，就应该补出来
- 补漏时同样必须判断 event_scope，并给出 affected_industries / affected_themes

不要做的事：
- 不要重复 existing_events 已经包含的事件
- 不要输出技术形态、涨停、连板、回调、整理、放量、缩量这类盘面描述
- 不要输出纯观点、纯情绪、纯研报态度；但如果其中包含明确事实，请抽“事实事件”而不是删掉整段

输出 JSON：
{
  "missed_events": [
    {
      "event_name": "...",
      "event_time_text": "...",
      "event_content": "...",
      "event_scope": "stock|industry|mixed|macro",
      "scope_reason": "...",
      "source_name": "...",
      "source_url": "...",
      "affected_stocks": [
        {"stock_code": "...", "stock_name": "..."}
      ],
      "affected_industries": ["..."],
      "affected_themes": ["..."],
      "anchor_block_id": "...",
      "evidence_text": "...",
      "confidence_score": 0.0,
      "needs_review": false,
      "review_reason": ""
    }
  ]
}

如果没有遗漏，就返回：
{"missed_events":[]}

只能返回 JSON，不要解释。
"""


def extract_simple_events_and_risk(
    document: MarkdownDocument,
    report_date: str,
    kb_settings: EventKBSettings,
    *,
    primary_stock_code: str = "",
    primary_stock_name: str = "",
) -> tuple[list[SimpleEventCandidate], SimpleReportSummary]:
    if not kb_settings.llm_extract_enabled:
        return [], SimpleReportSummary()

    blocks = _collect_blocks(document, kb_settings.llm_extract_max_blocks)
    if not blocks:
        return [], SimpleReportSummary()

    payload = json.dumps(
        {
            "report_date": report_date,
            "primary_stock_code": primary_stock_code,
            "primary_stock_name": primary_stock_name,
            "blocks": blocks,
        },
        ensure_ascii=False,
        indent=2,
    )
    if not kb_settings.llm_extract_base_url or not kb_settings.llm_extract_model:
        return [], SimpleReportSummary()

    parsed = _call_simple_llm(payload, kb_settings, system_prompt=_SIMPLE_SYSTEM_PROMPT)
    events, risk_summary = _parse_simple_response(parsed, primary_stock_code, primary_stock_name)
    events = normalize_simple_events(events, blocks=blocks, report_date=report_date)
    events = _backfill_source_metadata(events, blocks=blocks)
    reviewed_events = _review_missed_events(
        blocks=blocks,
        report_date=report_date,
        primary_stock_code=primary_stock_code,
        primary_stock_name=primary_stock_name,
        existing_events=events,
        kb_settings=kb_settings,
    )
    reviewed_events = normalize_simple_events(reviewed_events, blocks=blocks, report_date=report_date)
    reviewed_events = _backfill_source_metadata(reviewed_events, blocks=blocks)
    merged_events = _merge_simple_events([*events, *reviewed_events])
    return merged_events[:_MAX_SIMPLE_EVENTS], risk_summary


def _collect_blocks(document: MarkdownDocument, max_blocks: int) -> list[dict[str, str]]:
    event_bundles = _build_event_section_bundles(document)
    bundled_section_paths = {str(item.get("section_path") or "").strip() for item in event_bundles}
    candidates: list[tuple[int, int, dict[str, str]]] = []
    seen_texts: set[str] = set()
    for block in document.blocks:
        if block.block_type not in {"paragraph", "list_item", "table"}:
            continue
        if block.section_path in bundled_section_paths:
            continue
        if any(token in block.section_path for token in _SKIP_SECTION_TOKENS):
            continue
        text = _render_block_text(block)
        if not text or len(text) < 12:
            continue
        if any(token in text for token in _SKIP_TEXT_TOKENS):
            continue
        normalized_text = re.sub(r"\s+", " ", text)
        if normalized_text in seen_texts:
            continue
        seen_texts.add(normalized_text)
        score = _score_block(block, text)
        source_name, source_url = _resolve_adjacent_source_metadata(block, document.blocks)
        candidates.append(
            (
                score,
                block.source_line_start,
                {
                    "block_id": block.block_id,
                    "section_path": block.section_path,
                    "block_type": block.block_type,
                    "content_text": text,
                    "source_name": source_name,
                    "source_url": source_url,
                },
            )
        )
    for bundle in event_bundles:
        text = str(bundle.get("content_text") or "").strip()
        if not text:
            continue
        normalized_text = re.sub(r"\s+", " ", text)
        if normalized_text in seen_texts:
            continue
        seen_texts.add(normalized_text)
        score = _score_bundle_text(str(bundle.get("section_path") or ""), text)
        candidates.append((score, int(bundle.get("source_line_start") or 0), bundle))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in candidates[:max_blocks]]


def _build_event_section_bundles(document: MarkdownDocument) -> list[dict[str, str]]:
    grouped: dict[str, list[Any]] = {}
    for block in document.blocks:
        if block.block_type not in {"paragraph", "list_item", "table"}:
            continue
        if not _EVENT_SECTION_RE.search(block.section_path):
            continue
        grouped.setdefault(block.section_path, []).append(block)

    bundles: list[dict[str, str]] = []
    for section_path, blocks in grouped.items():
        ordered_blocks = sorted(blocks, key=lambda item: (item.source_line_start, item.source_line_end))
        content_lines = [f"事件小节: {section_path.split(' / ')[-1]}"]
        source_name = ""
        source_url = ""
        for block in ordered_blocks:
            text = _render_block_text(block) if block.block_type == "table" else (block.content_text or "").strip()
            if not text:
                continue
            content_lines.append(text)
            if not source_name:
                source_name = _extract_source_name(text)
            if not source_url:
                source_url = _extract_source_url(text)
        if not content_lines:
            continue
        if not source_name or not source_url:
            fallback_name, fallback_url = _resolve_adjacent_source_metadata(ordered_blocks[-1], document.blocks)
            source_name = source_name or fallback_name
            source_url = source_url or fallback_url
        bundles.append(
            {
                "block_id": stable_id(section_path, "bundle", ordered_blocks[0].source_line_start, ordered_blocks[-1].source_line_end),
                "section_path": section_path,
                "block_type": "bundle",
                "content_text": "\n".join(content_lines).strip(),
                "source_line_start": ordered_blocks[0].source_line_start,
                "source_line_end": ordered_blocks[-1].source_line_end,
                "source_name": source_name,
                "source_url": source_url,
            }
        )
    return bundles


def _render_block_text(block: Any) -> str:
    if block.block_type != "table":
        return (block.content_text or "").strip()
    lines: list[str] = []
    if block.table_headers:
        lines.append("表头: " + " | ".join(cell for cell in block.table_headers if cell))
    important_headers = {"时间/预期锚点日期", "时间", "事件", "事件状态", "时效性分类", "预计兑现日期", "来源", "来源名称", "URL", "链接", "可信度"}
    for row_index, row in enumerate(block.table_rows, start=1):
        cells = [f"{key}={value}" for key, value in row.items() if value]
        if cells:
            prioritized = [f"{key}={value}" for key, value in row.items() if value and key in important_headers]
            tail = [f"{key}={value}" for key, value in row.items() if value and key not in important_headers]
            merged = prioritized + tail
            lines.append(f"第{row_index}行: " + "；".join(merged[:12]))
    rendered = "\n".join(lines).strip()
    return rendered or (block.content_text or "").strip()


def _score_block(block: Any, text: str) -> int:
    score = 0
    if block.block_type == "list_item":
        score += 2
    if block.block_type == "table":
        score += 4
    score += min(len(text) // 80, 4)
    if _DATE_LIKE_RE.search(text):
        score += 1
    for token in _PRIORITY_SECTION_TOKENS:
        if token and token in block.section_path:
            score += 4
    for token in _PRIORITY_TEXT_TOKENS:
        if token and token in text:
            score += 3
    for token in _DISCOURAGED_TEXT_TOKENS:
        if token and token in text:
            score -= 2
    if any(token in text for token in ("受益", "催化", "驱动", "带动", "推动", "提振")):
        score += 2
    return score


def _score_bundle_text(section_path: str, text: str) -> int:
    score = 12
    score += min(len(text) // 120, 8)
    if _DATE_LIKE_RE.search(text):
        score += 2
    if _extract_source_name(text):
        score += 4
    if _extract_source_url(text):
        score += 6
    for token in _PRIORITY_SECTION_TOKENS:
        if token and token in section_path:
            score += 4
    for token in _PRIORITY_TEXT_TOKENS:
        if token and token in text:
            score += 3
    return score


def _call_simple_llm(payload: str, kb_settings: EventKBSettings, *, system_prompt: str) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if kb_settings.llm_extract_api_key:
        headers["Authorization"] = f"Bearer {kb_settings.llm_extract_api_key}"
    attempts = [
        payload,
        (
            payload
            + "\n\n重要补充：你上一次的返回未被系统识别为合法 JSON。"
            + "这一次只能返回一个 JSON 对象，不要输出解释，不要输出代码块标记，不要省略最外层花括号。"
        ),
    ]
    last_error: ValueError | None = None
    for user_payload in attempts:
        response = requests.post(
            kb_settings.llm_extract_base_url.rstrip("/") + "/chat/completions",
            headers=headers,
            json={
                "model": kb_settings.llm_extract_model,
                "temperature": kb_settings.llm_extract_temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
            },
            timeout=kb_settings.llm_extract_timeout,
        )
        response.raise_for_status()
        data = response.json()
        message = ((data.get("choices") or [{}])[0].get("message") or {})
        content = _coerce_message_content(message.get("content"))
        try:
            return _parse_json_content(content)
        except ValueError as exc:
            last_error = ValueError(f"{exc}. Raw response snippet: {_shorten_text(content)}")
    raise last_error or ValueError("No JSON object found in simple LLM response")


def _parse_json_content(content: str) -> dict[str, Any]:
    stripped = content.strip()
    candidates: list[str] = []
    if stripped:
        candidates.append(stripped)
    match = _JSON_BLOCK_RE.search(stripped)
    if match:
        candidates.append(match.group(1).strip())
    fragment = _extract_first_json_fragment(stripped)
    if fragment:
        candidates.append(fragment)
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            continue
        return parsed if isinstance(parsed, dict) else {"events": parsed}
    raise ValueError("No JSON object found in simple LLM response")


def _coerce_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
                continue
            inner_content = item.get("content")
            if isinstance(inner_content, str) and inner_content.strip():
                parts.append(inner_content)
        return "\n".join(parts).strip()
    return str(content or "").strip()


def _extract_first_json_fragment(content: str) -> str:
    for index, ch in enumerate(content):
        if ch not in "{[":
            continue
        fragment = _extract_balanced_json_fragment(content, index)
        if fragment:
            return fragment
    return ""


def _extract_balanced_json_fragment(content: str, start_index: int) -> str:
    stack: list[str] = []
    in_string = False
    escaped = False
    for index in range(start_index, len(content)):
        ch = content[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            stack.append(ch)
            continue
        if ch not in "}]":
            continue
        if not stack:
            return ""
        opening = stack.pop()
        if (opening == "{" and ch != "}") or (opening == "[" and ch != "]"):
            return ""
        if not stack:
            return content[start_index:index + 1]
    return ""


def _shorten_text(content: str, max_length: int = 280) -> str:
    normalized = re.sub(r"\s+", " ", str(content or "")).strip()
    if len(normalized) <= max_length:
        return normalized
    return normalized[:max_length] + "..."


def _parse_simple_response(
    payload: dict[str, Any],
    primary_stock_code: str,
    primary_stock_name: str,
) -> tuple[list[SimpleEventCandidate], SimpleReportSummary]:
    events: list[SimpleEventCandidate] = []
    for item in payload.get("events", []):
        event_name = _clean_text(str(item.get("event_name", "")))
        event_content = _clean_text(str(item.get("event_content", "")))
        if not event_name or not event_content:
            continue
        affected_stocks = _parse_affected_stocks(
            item.get("affected_stocks"),
            primary_stock_code=primary_stock_code,
            primary_stock_name=primary_stock_name,
        )
        events.append(
            SimpleEventCandidate(
                event_name=event_name,
                event_time_text=_clean_text(str(item.get("event_time_text", ""))),
                event_content=event_content,
                event_scope=_clean_event_scope(str(item.get("event_scope", ""))),
                scope_reason=_clean_text(str(item.get("scope_reason", ""))),
                source_name=_clean_text(str(item.get("source_name", ""))),
                source_url=_clean_text(str(item.get("source_url", ""))),
                affected_stocks=affected_stocks,
                affected_industries=_parse_string_values(item.get("affected_industries")),
                affected_themes=_parse_string_values(item.get("affected_themes")),
                anchor_block_id=_clean_text(str(item.get("anchor_block_id", ""))),
                evidence_text=_clean_text(str(item.get("evidence_text", event_content))) or event_content,
                confidence_score=_float_or_none(item.get("confidence_score")),
                needs_review=bool(item.get("needs_review", False)),
                review_reason=_clean_text(str(item.get("review_reason", ""))),
            )
        )
    report_summary = SimpleReportSummary(
        core_logic=_clean_summary_text(str(payload.get("core_logic", ""))),
        risk_summary=_clean_summary_text(str(payload.get("risk_summary", ""))),
    )
    return events[:_MAX_SIMPLE_EVENTS], report_summary


def _parse_simple_events(
    payload: dict[str, Any],
    *,
    field_name: str,
    primary_stock_code: str,
    primary_stock_name: str,
) -> list[SimpleEventCandidate]:
    events: list[SimpleEventCandidate] = []
    for item in payload.get(field_name, []):
        event_name = _clean_text(str(item.get("event_name", "")))
        event_content = _clean_text(str(item.get("event_content", "")))
        if not event_name or not event_content:
            continue
        affected_stocks = _parse_affected_stocks(
            item.get("affected_stocks"),
            primary_stock_code=primary_stock_code,
            primary_stock_name=primary_stock_name,
        )
        events.append(
            SimpleEventCandidate(
                event_name=event_name,
                event_time_text=_clean_text(str(item.get("event_time_text", ""))),
                event_content=event_content,
                event_scope=_clean_event_scope(str(item.get("event_scope", ""))),
                scope_reason=_clean_text(str(item.get("scope_reason", ""))),
                source_name=_clean_text(str(item.get("source_name", ""))),
                source_url=_clean_text(str(item.get("source_url", ""))),
                affected_stocks=affected_stocks,
                affected_industries=_parse_string_values(item.get("affected_industries")),
                affected_themes=_parse_string_values(item.get("affected_themes")),
                anchor_block_id=_clean_text(str(item.get("anchor_block_id", ""))),
                evidence_text=_clean_text(str(item.get("evidence_text", event_content))) or event_content,
                confidence_score=_float_or_none(item.get("confidence_score")),
                needs_review=bool(item.get("needs_review", False)),
                review_reason=_clean_text(str(item.get("review_reason", ""))),
            )
        )
    return events


def _review_missed_events(
    *,
    blocks: list[dict[str, str]],
    report_date: str,
    primary_stock_code: str,
    primary_stock_name: str,
    existing_events: list[SimpleEventCandidate],
    kb_settings: EventKBSettings,
) -> list[SimpleEventCandidate]:
    payload = json.dumps(
        {
            "report_date": report_date,
            "primary_stock_code": primary_stock_code,
            "primary_stock_name": primary_stock_name,
            "existing_events": [item.to_dict() for item in existing_events],
            "blocks": blocks,
        },
        ensure_ascii=False,
        indent=2,
    )
    parsed = _call_simple_llm(payload, kb_settings, system_prompt=_SIMPLE_REVIEW_PROMPT)
    return _parse_simple_events(
        parsed,
        field_name="missed_events",
        primary_stock_code=primary_stock_code,
        primary_stock_name=primary_stock_name,
    )


def _merge_simple_events(events: list[SimpleEventCandidate]) -> list[SimpleEventCandidate]:
    deduped: dict[str, SimpleEventCandidate] = {}
    for event in events:
        key = _simple_event_key(event)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = event
            continue
        deduped[key] = _pick_better_simple_event(existing, event)
    return list(deduped.values())


def _backfill_source_metadata(
    events: list[SimpleEventCandidate],
    *,
    blocks: list[dict[str, str]],
) -> list[SimpleEventCandidate]:
    block_map = {
        str(block.get("block_id") or "").strip(): block
        for block in blocks
        if str(block.get("block_id") or "").strip()
    }
    updated_events: list[SimpleEventCandidate] = []
    for event in events:
        source_name = event.source_name
        source_url = event.source_url
        anchor_block_id = event.anchor_block_id

        candidates: list[dict[str, str]] = []
        if anchor_block_id and anchor_block_id in block_map:
            candidates.append(block_map[anchor_block_id])
        if not candidates:
            matched = _find_matching_block(event, blocks)
            if matched:
                candidates.append(matched)
                anchor_block_id = anchor_block_id or str(matched.get("block_id") or "")

        for block in candidates:
            text = str(block.get("content_text") or "")
            if not source_name:
                source_name = str(block.get("source_name") or "") or _extract_source_name(text)
            if not source_url:
                source_url = str(block.get("source_url") or "") or _extract_source_url(text)

        updated_events.append(
            replace(
                event,
                source_name=source_name,
                source_url=source_url,
                anchor_block_id=anchor_block_id,
            )
        )
    return updated_events


def _simple_event_key(event: SimpleEventCandidate) -> str:
    if event.canonical_event_key:
        return event.canonical_event_key
    title = re.sub(r"[\s\u3000\"'“”‘’（）()，,。:：;；、】【\\/-]+", "", event.event_name.lower())
    event_time = re.sub(r"\s+", "", event.event_time_text.lower())
    return f"{title}|{event_time}"


def _pick_better_simple_event(left: SimpleEventCandidate, right: SimpleEventCandidate) -> SimpleEventCandidate:
    def score(item: SimpleEventCandidate) -> tuple[int, int, int, int, int, int, int, int]:
        return (
            len(item.affected_stocks),
            len(item.affected_industries),
            len(item.affected_themes),
            1 if item.anchor_block_id else 0,
            1 if item.source_url else 0,
            1 if item.source_name else 0,
            1 if item.event_scope else 0,
            len(item.evidence_text or ""),
            len(item.event_content or ""),
        )

    return right if score(right) > score(left) else left


def _find_matching_block(event: SimpleEventCandidate, blocks: list[dict[str, str]]) -> dict[str, str] | None:
    candidates = [
        _clean_text(event.evidence_text),
        _clean_text(event.event_content),
        _clean_text(event.event_name),
    ]
    for candidate_text in candidates:
        if len(candidate_text) < 6:
            continue
        normalized_target = re.sub(r"\s+", "", candidate_text)
        for block in blocks:
            block_text = _clean_text(str(block.get("content_text") or ""))
            if not block_text:
                continue
            normalized_block = re.sub(r"\s+", "", block_text)
            if normalized_target in normalized_block or normalized_block in normalized_target:
                return block
    return None


def _resolve_adjacent_source_metadata(target_block: Any, all_blocks: list[Any]) -> tuple[str, str]:
    source_name = ""
    source_url = ""
    same_section_blocks = [
        block
        for block in all_blocks
        if block.block_type in {"paragraph", "list_item", "table"} and block.section_path == target_block.section_path
    ]
    same_section_blocks.sort(key=lambda item: (item.source_line_start, item.source_line_end))
    anchor_index = next(
        (
            index
            for index, block in enumerate(same_section_blocks)
            if block.block_id == target_block.block_id
        ),
        -1,
    )
    if anchor_index < 0:
        return source_name, source_url

    ordered_indexes = [anchor_index]
    for offset in (1, 2, -1, -2):
        candidate_index = anchor_index + offset
        if 0 <= candidate_index < len(same_section_blocks):
            ordered_indexes.append(candidate_index)

    seen_indexes: set[int] = set()
    for index in ordered_indexes:
        if index in seen_indexes:
            continue
        seen_indexes.add(index)
        block = same_section_blocks[index]
        if abs(block.source_line_start - target_block.source_line_end) > 12 and index != anchor_index:
            continue
        text = _render_block_text(block)
        if not source_name:
            source_name = _extract_source_name(text)
        if not source_url:
            source_url = _extract_source_url(text)
        if source_name and source_url:
            break
    return source_name, source_url


def _parse_affected_stocks(
    value: object,
    *,
    primary_stock_code: str,
    primary_stock_name: str,
) -> list[SimpleAffectedStock]:
    items = value if isinstance(value, list) else []
    stocks: list[SimpleAffectedStock] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        stock_code = _clean_text(str(item.get("stock_code", "")))
        stock_name = _clean_text(str(item.get("stock_name", "")))
        key = stock_code or stock_name
        if not key or key in seen:
            continue
        stocks.append(SimpleAffectedStock(stock_code=stock_code, stock_name=stock_name))
        seen.add(key)
    if primary_stock_code and all(item.stock_code != primary_stock_code for item in stocks):
        stocks.insert(0, SimpleAffectedStock(stock_code=primary_stock_code, stock_name=primary_stock_name))
    return stocks


def _clean_text(text: str) -> str:
    cleaned = (text or "").replace("**", " ").replace("__", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _clean_summary_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").replace("\r\n", "\n").split("\n")]
    cleaned_lines: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if cleaned_lines and not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
            continue
        cleaned_lines.append(line)
        previous_blank = False
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()
    return "\n".join(cleaned_lines).strip()


def _extract_source_name(text: str) -> str:
    for line in str(text or "").splitlines():
        match = _SOURCE_LINE_RE.match(line.strip())
        if match:
            return _clean_text(match.group(1))
    return ""


def _extract_source_url(text: str) -> str:
    for line in str(text or "").splitlines():
        match = _URL_LINE_RE.match(line.strip())
        if match:
            return _clean_text(match.group(1))
    return ""


def _clean_event_scope(value: str) -> str:
    normalized = _clean_text(value).lower()
    if normalized in {"stock", "industry", "mixed", "macro"}:
        return normalized
    return ""


def _parse_string_values(value: object) -> list[str]:
    raw_items = value if isinstance(value, list) else []
    items: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        text = _clean_text(str(raw))
        normalized = text.lower()
        if not text or normalized in seen:
            continue
        items.append(text)
        seen.add(normalized)
    return items


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

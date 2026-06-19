"""Map upstream Chinese event-type strings to a stable English enum.

The English ids (left side never visible to end-users) are what we filter
and aggregate by. The Chinese names that come back from the upstream API
are stored as ``event_name`` so the UI can keep showing the original
phrasing.

Adding a new mapping: pick the most specific match, fall back to ``other``
when uncertain — ``other`` rows are still useful, they just don't get
specialized handling. Never silently drop an upstream row because we can't
classify it.
"""

from __future__ import annotations

# Canonical event types — keep this tuple in sync with the union of values
# below. Used for the API ``filters/meta`` payload.
EVENT_TYPE_VALUES: tuple[str, ...] = (
    "unlock",                # 限售解禁
    "shareholders_meeting",  # 股东大会
    "dividend",              # 分红派息
    "rights_issue",          # 配股
    "secondary_offering",    # 增发
    "ipo_subscribe",         # 新股申购
    "ipo_listing",           # 新股上市
    "buyback",               # 回购
    "name_change",           # 更名
    "suspend",               # 停牌
    "resume",                # 复牌
    "earnings_forecast",     # 业绩预告
    "earnings_express",      # 业绩快报
    "earnings_disclose",     # 财报预约披露
    "macro_data",            # 宏观数据发布
    "policy_meeting",        # 政策性会议
    "industry_event",        # 行业活动 / 展会
    "other",
)


# Map fragments of the upstream Chinese event-type string to the canonical
# enum. Match is "first substring hit wins" — order matters, more specific
# strings before more generic ones.
#
# Tip: to debug a miss, run
#     `python -m eventradar.normalize.event_type_map "原始事件类型"`
# (CLI hook lives at the bottom of this file).
_RAW_TO_TYPE: tuple[tuple[str, str], ...] = (
    ("限售", "unlock"),
    ("解禁", "unlock"),
    ("股东大会", "shareholders_meeting"),
    ("股权登记", "dividend"),
    ("分红", "dividend"),
    ("派息", "dividend"),
    ("除权除息", "dividend"),
    ("配股", "rights_issue"),
    ("增发", "secondary_offering"),
    ("定增", "secondary_offering"),
    ("网上申购", "ipo_subscribe"),
    ("网上发行", "ipo_subscribe"),
    ("申购日", "ipo_subscribe"),
    ("上市日", "ipo_listing"),
    ("发行日", "ipo_subscribe"),
    ("回购", "buyback"),
    ("更名", "name_change"),
    ("停牌", "suspend"),
    ("复牌", "resume"),
    ("业绩预告", "earnings_forecast"),
    ("业绩快报", "earnings_express"),
    ("预约披露", "earnings_disclose"),
    ("年报披露", "earnings_disclose"),
    ("季报披露", "earnings_disclose"),
    ("宏观", "macro_data"),
    ("会议", "policy_meeting"),
    ("展会", "industry_event"),
    ("发布会", "industry_event"),
)


def map_event_type(raw: str | None) -> str:
    """Translate an upstream event-type string to the canonical enum.

    Always returns a value in :data:`EVENT_TYPE_VALUES`; unknown strings
    fall back to ``"other"``.
    """
    if not raw:
        return "other"
    text = str(raw).strip()
    for needle, mapped in _RAW_TO_TYPE:
        if needle in text:
            return mapped
    return "other"


if __name__ == "__main__":  # pragma: no cover — debugging hook
    import sys

    for arg in sys.argv[1:]:
        print(f"{arg!r} -> {map_event_type(arg)}")

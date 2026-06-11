from __future__ import annotations

from datetime import date
from typing import Optional

from dateutil.parser import isoparse


def parse_int(value: Optional[str], *, default: Optional[int] = None, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    if value is None or value == "":
        if default is None:
            raise ValueError("缺少必要参数")
        return default
    try:
        v = int(value)
    except Exception:
        raise ValueError("参数必须为整数")
    if minimum is not None and v < minimum:
        raise ValueError(f"参数必须 ≥ {minimum}")
    if maximum is not None and v > maximum:
        raise ValueError(f"参数必须 ≤ {maximum}")
    return v


def parse_date(value: Optional[str], *, required: bool = False) -> Optional[str]:
    if value is None or value == "":
        if required:
            raise ValueError("缺少日期参数")
        return None
    try:
        d: date = isoparse(value).date()
    except Exception:
        raise ValueError("日期格式必须为 YYYY-MM-DD")
    return d.isoformat()


def parse_bool(value: Optional[str], *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    v = str(value).strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError("布尔参数必须为 true/false 或 1/0")


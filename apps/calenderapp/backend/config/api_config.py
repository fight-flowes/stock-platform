from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class APIConstants:
    DEFAULT_PAGE: int = 1
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 200

    ERROR_CODES: Dict[str, int] = {
        "VALIDATION_ERROR": 40001,
        "UNAUTHORIZED": 40101,
        "NOT_FOUND": 40401,
        "INTERNAL_ERROR": 50001,
    }


class APIResponse:
    @staticmethod
    def success(data: Any = None, message: str = "Success", code: int = 200) -> Dict[str, Any]:
        return {"code": code, "message": message, "data": data, "timestamp": _now_iso()}

    @staticmethod
    def error(
        message: str,
        code: int,
        details: Optional[Dict[str, Any]] = None,
        http_status: int = 400,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"code": code, "message": message, "data": None, "timestamp": _now_iso()}
        if details:
            payload["details"] = details
        payload["http_status"] = http_status
        return payload

    @staticmethod
    def paginated(
        data: Any,
        total: int,
        page: int,
        page_size: int,
        extra: Optional[Dict[str, Any]] = None,
        message: str = "Success",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "code": 200,
            "message": message,
            "data": {"items": data, "total": total, "page": page, "page_size": page_size},
            "timestamp": _now_iso(),
        }
        if extra:
            payload["data"].update(extra)
        return payload


class EventTypes:
    # 原有类型
    EARNINGS = "earnings"
    DIVIDEND = "dividend"
    SHAREHOLDER_MEETING = "shareholder_meeting"
    LISTING_STATUS = "listing_status"
    FINANCING = "financing"
    M_AND_A = "m_and_a"
    REGULATORY = "regulatory"
    OTHER = "other"
    
    # 新增类型（来自 event-extractor skill）
    POLICY = "policy"           # 政策利好
    ANNOUNCEMENT = "announcement"  # 公司公告
    INDUSTRY = "industry"       # 行业动态
    FUND_FLOW = "fund_flow"     # 资金动向

    @classmethod
    def all(cls) -> Dict[str, str]:
        return {
            cls.EARNINGS: "财报发布",
            cls.DIVIDEND: "分红派息",
            cls.SHAREHOLDER_MEETING: "股东大会",
            cls.LISTING_STATUS: "上市/退市",
            cls.FINANCING: "融资事件",
            cls.M_AND_A: "并购重组",
            cls.REGULATORY: "监管事件",
            cls.POLICY: "政策利好",      # 新增
            cls.ANNOUNCEMENT: "公司公告",  # 新增
            cls.INDUSTRY: "行业动态",     # 新增
            cls.FUND_FLOW: "资金动向",    # 新增
            cls.OTHER: "其他事件",
        }

"""
涨停股分析报告模型
"""
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, PGSCHEMA


class LimitUpAnalysis(Base):
    """涨停股分析报告表"""
    __tablename__ = "limit_up_analysis"
    __table_args__ = {"schema": PGSCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 关联的涨停记录
    limit_up_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    stock_name: Mapped[str] = mapped_column(String(128), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # 涨停原因分析结果
    primary_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 主要原因
    primary_reason_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    secondary_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 次要原因
    secondary_reason_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tertiary_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 第三原因
    tertiary_reason_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    
    # 事件驱动详情
    events: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 相关事件列表，JSON数组
    main_event: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # 主要事件
    event_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 事件来源
    event_impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 事件影响分析
    event_time: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 事件时间
    
    # 概念催化
    trigger_concepts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 触发概念，JSON数组
    concept_news: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 概念相关新闻
    
    # 资金动向分析
    fund_character: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 资金特征
    institution_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 机构分析
    hot_money_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 游资分析
    lhb_seats: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 龙虎榜席位，JSON数组
    
    # 技术特征
    kline_pattern: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # K线形态
    volume_price: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 量价关系
    seal_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # 封板强度评分
    
    # 公司画像
    main_business: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 主营业务
    core_concepts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 核心概念，JSON数组
    industry: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 所属行业
    
    # 综合评估
    strength_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 强度评级 1-5星
    is_dragon: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # 是否龙头
    dragon_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 龙头类型：空间龙/板块龙
    
    # 相关新闻
    related_news: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 相关新闻，JSON数组
    
    # 完整报告
    full_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 完整分析报告，Markdown格式
    
    # 元数据
    analysis_source: Mapped[str] = mapped_column(String(32), nullable=False, default='minio-stockinfo')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="NOW()", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="NOW()",
        onupdate="NOW()",
        nullable=False,
    )

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "limit_up_id": self.limit_up_id,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "analysis_date": self.analysis_date.isoformat(),
            "primary_reason": self.primary_reason,
            "primary_reason_weight": self.primary_reason_weight,
            "secondary_reason": self.secondary_reason,
            "secondary_reason_weight": self.secondary_reason_weight,
            "tertiary_reason": self.tertiary_reason,
            "tertiary_reason_weight": self.tertiary_reason_weight,
            "events": json.loads(self.events) if self.events else [],
            "main_event": self.main_event,
            "event_source": self.event_source,
            "event_impact": self.event_impact,
            "event_time": self.event_time,
            "trigger_concepts": json.loads(self.trigger_concepts) if self.trigger_concepts else [],
            "concept_news": self.concept_news,
            "fund_character": self.fund_character,
            "institution_analysis": self.institution_analysis,
            "hot_money_analysis": self.hot_money_analysis,
            "lhb_seats": json.loads(self.lhb_seats) if self.lhb_seats else [],
            "kline_pattern": self.kline_pattern,
            "volume_price": self.volume_price,
            "seal_strength": self.seal_strength,
            "main_business": self.main_business,
            "core_concepts": json.loads(self.core_concepts) if self.core_concepts else [],
            "industry": self.industry,
            "strength_rating": self.strength_rating,
            "is_dragon": self.is_dragon,
            "dragon_type": self.dragon_type,
            "related_news": json.loads(self.related_news) if self.related_news else [],
            "full_report": self.full_report,
            "analysis_source": self.analysis_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

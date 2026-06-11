"""
Tushare 涨停数据同步服务
直接从 Tushare API 获取涨停数据并入库
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Dict, List, Optional, Any
from sqlalchemy import select, and_

from app.db import session_scope
from app.models.limit_up_stock import LimitUpStock
from app.models.stock import Stock
from app.config import get_tushare_pro


class TushareSyncService:
    """Tushare 数据同步服务"""

    _pro = None

    @classmethod
    def _get_pro(cls):
        """获取 Tushare API 实例"""
        if cls._pro is None:
            cls._pro = get_tushare_pro()
        return cls._pro

    @classmethod
    def sync_limit_up(cls, trade_date: str) -> Dict[str, Any]:
        """
        从 Tushare 同步涨停数据
        
        Args:
            trade_date: 交易日期 (YYYY-MM-DD 或 YYYYMMDD)
        
        Returns:
            同步结果统计
        """
        # 统一日期格式
        if '-' in trade_date:
            date_str = trade_date.replace('-', '')
            date_obj = datetime.strptime(trade_date, '%Y-%m-%d').date()
        else:
            date_str = trade_date
            date_obj = datetime.strptime(trade_date, '%Y%m%d').date()

        pro = cls._get_pro()

        # 1. 获取涨停股列表（包含涨停U和炸板Z）
        df_list = []
        for limit_type in ['U', 'Z']:
            try:
                df = pro.limit_list_d(trade_date=date_str, limit_type=limit_type)
                if df is not None and not df.empty:
                    df['limit_type_code'] = limit_type
                    df_list.append(df)
            except Exception:
                pass
        
        if not df_list:
            return {
                'success': True,
                'trade_date': trade_date,
                'total': 0,
                'created': 0,
                'updated': 0,
                'message': '当日无涨停数据'
            }
        
        import pandas as pd
        df_limit = pd.concat(df_list, ignore_index=True) if len(df_list) > 1 else df_list[0]

        # 2. 过滤 ST 股票
        try:
            df_basic = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
            st_codes = df_basic[df_basic['name'].str.contains('ST|退|*ST', na=False, regex=True)]['ts_code'].tolist()
            df_limit = df_limit[~df_limit['ts_code'].isin(st_codes)]
        except Exception:
            pass  # 如果获取基本信息失败，不过滤

        # 3. 获取龙虎榜数据（如果有）
        lhb_data = {}
        try:
            df_lhb = pro.top_inst(trade_date=date_str)
            if df_lhb is not None and not df_lhb.empty:
                for _, row in df_lhb.iterrows():
                    ts_code = row['ts_code']
                    if ts_code not in lhb_data:
                        lhb_data[ts_code] = {
                            'institution_net': 0,
                            'hot_money_net': 0,
                            'north_net': 0
                        }
                    
                    # 判断席位类型
                    exalter = str(row.get('exalter', ''))
                    net_buy = float(row.get('net_buy', 0) or 0)
                    
                    if '机构专用' in exalter:
                        lhb_data[ts_code]['institution_net'] += net_buy
                    elif '深股通' in exalter or '沪股通' in exalter:
                        lhb_data[ts_code]['north_net'] += net_buy
                    else:
                        lhb_data[ts_code]['hot_money_net'] += net_buy
        except Exception:
            pass

        # 4. 入库
        created = 0
        updated = 0
        errors = []

        with session_scope() as session:
            for _, row in df_limit.iterrows():
                try:
                    ts_code = row['ts_code']
                    stock_name = row['name']
                    
                    # 检查是否已存在
                    existing = session.execute(
                        select(LimitUpStock).where(and_(
                            LimitUpStock.stock_code == ts_code,
                            LimitUpStock.limit_up_date == date_obj
                        ))
                    ).scalars().first()

                    # 解析数据
                    consecutive_days = int(row.get('limit_times', 1) or 1)
                    close = float(row.get('close', 0) or 0)  # 收盘价
                    seal_amount = float(row.get('fd_amount', 0) or 0)
                    float_mv = float(row.get('float_mv', 0) or 0)  # 流通市值
                    first_time = str(row.get('first_time', '')) or None
                    last_time = str(row.get('last_time', '')) or None
                    open_count = int(row.get('open_times', 0) or 0)
                    turnover_rate = float(row.get('turnover_ratio', 0) or 0)
                    industry = row.get('industry') or None
                    limit_type_code = str(row.get('limit_type_code', 'U') or 'U')

                    # 获取完整行业名称
                    if industry:
                        from app.utils.industry_map import get_full_industry_name
                        industry = get_full_industry_name(industry)

                    # 计算封单比 = 封单金额 / 流通市值 × 100%
                    seal_ratio = 0
                    if float_mv > 0 and seal_amount > 0:
                        seal_ratio = round((seal_amount / float_mv) * 100, 2)

                    # 获取龙虎榜数据
                    lhb = lhb_data.get(ts_code, {})

                    # 计算强度
                    from app.services.limit_up_service import _calculate_strength, _parse_time
                    first_time_obj = _parse_time(first_time) if first_time else None
                    strength_level, strength_score = _calculate_strength(
                        first_time_obj,
                        consecutive_days,
                        seal_amount,
                        open_count,
                        lhb.get('institution_net', 0),
                        lhb.get('hot_money_net', 0)
                    )
                    
                    # 判断涨停类型
                    if limit_type_code == 'Z':
                        limit_up_type = 'broken_board'  # 炸板
                    elif consecutive_days >= 2:
                        limit_up_type = 'multi_board'   # 连板
                    else:
                        limit_up_type = 'first_board'   # 首板

                    if existing:
                        # 更新
                        existing.stock_name = stock_name
                        existing.consecutive_days = consecutive_days
                        existing.close = close  # 更新收盘价
                        existing.seal_amount = seal_amount
                        existing.seal_ratio = seal_ratio
                        existing.first_limit_time = first_time_obj
                        existing.last_limit_time = _parse_time(last_time) if last_time else None
                        existing.open_count = open_count
                        existing.turnover_rate = turnover_rate
                        existing.industry = industry
                        existing.limit_up_type = limit_up_type
                        existing.institution_net_buy = lhb.get('institution_net', 0)
                        existing.hot_money_net_buy = lhb.get('hot_money_net', 0)
                        existing.north_net_buy = lhb.get('north_net', 0)
                        existing.strength_level = strength_level
                        existing.strength_score = strength_score
                        existing.source = 'tushare'
                        updated += 1
                    else:
                        # 创建
                        limit_up = LimitUpStock(
                            stock_code=ts_code,
                            stock_name=stock_name,
                            limit_up_date=date_obj,
                            consecutive_days=consecutive_days,
                            limit_up_type=limit_up_type,
                            close=close,  # 添加收盘价
                            seal_amount=seal_amount,
                            seal_ratio=seal_ratio,
                            first_limit_time=first_time_obj,
                            last_limit_time=_parse_time(last_time) if last_time else None,
                            open_count=open_count,
                            turnover_rate=turnover_rate,
                            industry=industry,
                            concept_tags=[],
                            institution_net_buy=lhb.get('institution_net', 0),
                            hot_money_net_buy=lhb.get('hot_money_net', 0),
                            north_net_buy=lhb.get('north_net', 0),
                            total_net_buy=sum(lhb.values()),
                            strength_level=strength_level,
                            strength_score=strength_score,
                            is_dragon_head=False,
                            dragon_rank=0,
                            source='tushare'
                        )
                        session.add(limit_up)
                        created += 1

                    # 同步股票基本信息
                    stock_existing = session.execute(
                        select(Stock).where(Stock.code == ts_code)
                    ).scalars().first()
                    
                    if not stock_existing:
                        session.add(Stock(
                            code=ts_code,
                            name=stock_name,
                            exchange=ts_code.split('.')[1] if '.' in ts_code else None
                        ))

                except Exception as e:
                    errors.append({
                        'stock_code': row.get('ts_code', ''),
                        'error': str(e)
                    })

        return {
            'success': True,
            'trade_date': trade_date,
            'total': len(df_limit),
            'created': created,
            'updated': updated,
            'errors': errors[:20]
        }

    @classmethod
    def get_trade_calendar(cls, start_date: str, end_date: str) -> List[str]:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        
        Returns:
            交易日列表
        """
        pro = cls._get_pro()
        
        try:
            df = pro.trade_cal(
                exchange='SSE',
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                is_open='1'
            )
            if df is not None and not df.empty:
                return [d for d in df['cal_date'].tolist()]
        except Exception:
            pass
        
        return []
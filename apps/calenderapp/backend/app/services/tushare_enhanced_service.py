"""
Tushare 增强数据同步服务
提供涨停、概念板块、行业分类等数据同步
"""
from __future__ import annotations

import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import select, and_, text, update
from sqlalchemy.dialects.postgresql import insert

from app.db import session_scope, engine
from app.models.limit_up_stock import LimitUpStock
from app.models.stock import Stock
from app.config import get_tushare_pro


class TushareEnhancedService:
    """Tushare 增强数据同步服务"""

    _pro = None

    @classmethod
    def _get_pro(cls):
        """获取 Tushare API 实例"""
        if cls._pro is None:
            cls._pro = get_tushare_pro()
        return cls._pro

    # =========================================================================
    # 涨停数据同步
    # =========================================================================

    @classmethod
    def sync_limit_up_full(cls, trade_date: str) -> Dict[str, Any]:
        """
        完整涨停数据同步（包含龙虎榜、概念板块）
        
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
        results = {
            'trade_date': trade_date,
            'limit_up': 0,
            'lhb': 0,
            'concepts': 0,
            'errors': []
        }

        # 1. 同步涨停列表
        try:
            limit_result = cls._sync_limit_list(pro, date_str, date_obj)
            results['limit_up'] = limit_result['created'] + limit_result['updated']
            results['limit_up_created'] = limit_result['created']
            results['limit_up_updated'] = limit_result['updated']
        except Exception as e:
            results['errors'].append(f"涨停数据同步失败: {str(e)}")

        # 2. 同步龙虎榜数据
        try:
            lhb_result = cls._sync_lhb_data(pro, date_str, date_obj)
            results['lhb'] = lhb_result['updated']
        except Exception as e:
            results['errors'].append(f"龙虎榜数据同步失败: {str(e)}")

        # 3. 同步概念板块
        try:
            concept_result = cls._sync_concept_data(pro, date_str, date_obj)
            results['concepts'] = concept_result['updated']
        except Exception as e:
            results['errors'].append(f"概念板块同步失败: {str(e)}")

        # 4. 自动识别龙头
        try:
            dragon_result = cls._auto_identify_dragon(date_obj)
            results['dragons'] = dragon_result['count']
        except Exception as e:
            results['errors'].append(f"龙头识别失败: {str(e)}")

        results['success'] = len(results['errors']) == 0
        return results

    @classmethod
    def _sync_limit_list(cls, pro, date_str: str, date_obj: date, target_codes: Optional[set[str]] = None) -> Dict:
        """同步涨停列表"""
        # 获取涨停数据 (U=涨停, Z=炸板)
        df_list = []
        
        for limit_type in ['U', 'Z']:
            try:
                df = pro.limit_list_d(trade_date=date_str, limit_type=limit_type)
                if df is not None and not df.empty:
                    df['limit_type_code'] = limit_type  # 标记类型
                    df_list.append(df)
            except Exception:
                pass
        
        if not df_list:
            return {'created': 0, 'updated': 0}
        
        import pandas as pd
        df = pd.concat(df_list, ignore_index=True) if len(df_list) > 1 else df_list[0]

        # 过滤 ST
        try:
            df_basic = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
            st_codes = df_basic[df_basic['name'].str.contains('ST|退|\\*ST', na=False, regex=True)]['ts_code'].tolist()
            df = df[~df['ts_code'].isin(st_codes)]
        except Exception:
            pass

        created = 0
        updated = 0

        with session_scope() as session:
            for _, row in df.iterrows():
                try:
                    ts_code = row['ts_code']
                    if target_codes and ts_code not in target_codes:
                        continue
                    stock_name = row['name']
                    
                    existing = session.execute(
                        select(LimitUpStock).where(and_(
                            LimitUpStock.stock_code == ts_code,
                            LimitUpStock.limit_up_date == date_obj
                        ))
                    ).scalars().first()

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
                    
                    # 判断涨停类型
                    if limit_type_code == 'Z':
                        limit_up_type = 'broken_board'  # 炸板
                    elif consecutive_days >= 2:
                        limit_up_type = 'multi_board'   # 连板
                    else:
                        limit_up_type = 'first_board'   # 首板

                    # 解析时间
                    from app.services.limit_up_service import _parse_time, _calculate_strength
                    first_time_obj = _parse_time(first_time) if first_time else None
                    last_time_obj = _parse_time(last_time) if last_time else None

                    # 计算强度（先不带资金数据）
                    strength_level, strength_score = _calculate_strength(
                        first_time_obj, consecutive_days, seal_amount, open_count, 0, 0
                    )

                    if existing:
                        existing.stock_name = stock_name
                        existing.consecutive_days = consecutive_days
                        existing.close = close  # 更新收盘价
                        existing.seal_amount = seal_amount
                        existing.seal_ratio = seal_ratio
                        existing.first_limit_time = first_time_obj
                        existing.last_limit_time = last_time_obj
                        existing.open_count = open_count
                        existing.turnover_rate = turnover_rate
                        existing.industry = industry
                        existing.limit_up_type = limit_up_type
                        existing.strength_level = strength_level
                        existing.strength_score = strength_score
                        existing.source = 'tushare'
                        updated += 1
                    else:
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
                            last_limit_time=last_time_obj,
                            open_count=open_count,
                            turnover_rate=turnover_rate,
                            industry=industry,
                            concept_tags=[],
                            strength_level=strength_level,
                            strength_score=strength_score,
                            source='tushare'
                        )
                        session.add(limit_up)
                        created += 1

                    # 同步股票基础信息
                    stock_existing = session.execute(
                        select(Stock).where(Stock.code == ts_code)
                    ).scalars().first()
                    
                    if not stock_existing:
                        exchange = ts_code.split('.')[1] if '.' in ts_code else None
                        session.add(Stock(code=ts_code, name=stock_name, exchange=exchange))

                except Exception as e:
                    pass

        # 批量获取量比数据（daily_basic 不支持批量查询，逐个获取）
        try:
            # 获取当日所有涨停股代码
            with session_scope() as session:
                limit_up_stocks = session.execute(
                    select(LimitUpStock.stock_code).where(LimitUpStock.limit_up_date == date_obj)
                ).scalars().all()
            
            if limit_up_stocks:
                if target_codes:
                    limit_up_stocks = [code for code in limit_up_stocks if code in target_codes]
                volume_ratio_updates = []
                # 逐个获取量比数据（限制最多50个，避免API调用过多）
                for ts_code in limit_up_stocks[:50]:
                    try:
                        df_basic = pro.daily_basic(
                            ts_code=ts_code,
                            start_date=date_str,
                            end_date=date_str,
                            fields='ts_code,volume_ratio'
                        )
                        
                        if df_basic is not None and not df_basic.empty:
                            volume_ratio = float(df_basic.iloc[0]['volume_ratio']) if pd.notna(df_basic.iloc[0]['volume_ratio']) else None
                            if volume_ratio:
                                volume_ratio_updates.append((ts_code, volume_ratio))
                    except Exception:
                        pass
                
                # 批量更新
                if volume_ratio_updates:
                    with session_scope() as session:
                        for ts_code, volume_ratio in volume_ratio_updates:
                            session.execute(
                                update(LimitUpStock)
                                .where(and_(
                                    LimitUpStock.stock_code == ts_code,
                                    LimitUpStock.limit_up_date == date_obj
                                ))
                                .values(volume_ratio=volume_ratio)
                            )
        except Exception as e:
            print(f"获取量比数据失败: {str(e)}")

        return {'created': created, 'updated': updated}

    @classmethod
    def _sync_lhb_data(cls, pro, date_str: str, date_obj: date, target_codes: Optional[set[str]] = None) -> Dict:
        """同步龙虎榜数据"""
        # 获取龙虎榜机构数据
        df_inst = pro.top_inst(trade_date=date_str)
        
        if df_inst is None or df_inst.empty:
            return {'updated': 0}

        # 汇总每只股票的资金数据
        stock_funds = {}
        
        for _, row in df_inst.iterrows():
            ts_code = row['ts_code']
            if target_codes and ts_code not in target_codes:
                continue
            exalter = str(row.get('exalter', ''))
            net_buy = float(row.get('net_buy', 0) or 0)
            
            if ts_code not in stock_funds:
                stock_funds[ts_code] = {
                    'institution_net': 0,
                    'hot_money_net': 0,
                    'north_net': 0
                }
            
            if '机构专用' in exalter:
                stock_funds[ts_code]['institution_net'] += net_buy
            elif '深股通' in exalter or '沪股通' in exalter or '京股通' in exalter:
                stock_funds[ts_code]['north_net'] += net_buy
            else:
                stock_funds[ts_code]['hot_money_net'] += net_buy

        # 更新到涨停表
        updated = 0
        with session_scope() as session:
            for ts_code, funds in stock_funds.items():
                existing = session.execute(
                    select(LimitUpStock).where(and_(
                        LimitUpStock.stock_code == ts_code,
                        LimitUpStock.limit_up_date == date_obj
                    ))
                ).scalars().first()

                if existing:
                    existing.institution_net_buy = funds['institution_net']
                    existing.hot_money_net_buy = funds['hot_money_net']
                    existing.north_net_buy = funds['north_net']
                    existing.total_net_buy = sum(funds.values())
                    
                    # 重新计算强度
                    from app.services.limit_up_service import _calculate_strength
                    existing.strength_level, existing.strength_score = _calculate_strength(
                        existing.first_limit_time,
                        existing.consecutive_days,
                        existing.seal_amount,
                        existing.open_count,
                        funds['institution_net'],
                        funds['hot_money_net']
                    )
                    updated += 1

        return {'updated': updated}

    @classmethod
    def _sync_concept_data(cls, pro, date_str: str, date_obj: date, target_codes: Optional[set[str]] = None) -> Dict:
        """同步概念板块数据"""
        # 获取当日涨停股的概念板块
        try:
            # 获取概念板块成分
            df_concept = pro.concept_detail(src='ts')
        except Exception:
            return {'updated': 0}

        if df_concept is None or df_concept.empty:
            return {'updated': 0}

        # 构建股票-概念映射
        stock_concepts = {}
        for _, row in df_concept.iterrows():
            ts_code = row.get('ts_code')
            concept_name = row.get('concept_name')
            if target_codes and ts_code not in target_codes:
                continue
            if ts_code and concept_name:
                if ts_code not in stock_concepts:
                    stock_concepts[ts_code] = []
                if concept_name not in stock_concepts[ts_code]:
                    stock_concepts[ts_code].append(concept_name)

        # 更新到涨停表
        updated = 0
        with session_scope() as session:
            for ts_code, concepts in stock_concepts.items():
                existing = session.execute(
                    select(LimitUpStock).where(and_(
                        LimitUpStock.stock_code == ts_code,
                        LimitUpStock.limit_up_date == date_obj
                    ))
                ).scalars().first()

                if existing and concepts:
                    existing.concept_tags = concepts[:10]  # 最多保存10个概念
                    updated += 1

        return {'updated': updated}

    @classmethod
    def _auto_identify_dragon(cls, date_obj: date) -> Dict:
        """自动识别龙头股"""
        with session_scope() as session:
            # 获取当日所有涨停股，按连板数和强度排序
            items = session.execute(
                select(LimitUpStock)
                .where(LimitUpStock.limit_up_date == date_obj)
                .order_by(
                    LimitUpStock.consecutive_days.desc(),
                    LimitUpStock.strength_score.desc(),
                    LimitUpStock.seal_amount.desc()
                )
            ).scalars().all()

            if not items:
                return {'count': 0}

            # 识别龙头
            dragons = []
            industries = set()
            
            for item in items:
                # 最高连板的作为总龙头
                if len(dragons) == 0 and item.consecutive_days >= 3:
                    item.is_dragon_head = True
                    item.dragon_rank = 1
                    dragons.append(item)
                    if item.industry:
                        industries.add(item.industry)
                
                # 每个行业最高连板的作为板块龙头
                elif item.industry and item.industry not in industries and item.consecutive_days >= 2:
                    item.is_dragon_head = True
                    item.dragon_rank = len(dragons) + 1
                    dragons.append(item)
                    industries.add(item.industry)
                
                else:
                    item.is_dragon_head = False
                    item.dragon_rank = 0

            return {'count': len(dragons)}

    # =========================================================================
    # 批量同步
    # =========================================================================

    @classmethod
    def sync_date_range(cls, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        批量同步日期范围内的数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        
        Returns:
            同步结果汇总
        """
        pro = cls._get_pro()
        
        # 获取交易日历
        df_cal = pro.trade_cal(
            exchange='SSE',
            start_date=start_date.replace('-', ''),
            end_date=end_date.replace('-', ''),
            is_open='1'
        )
        
        if df_cal is None or df_cal.empty:
            return {'success': False, 'message': '无交易日数据'}

        trade_dates = df_cal['cal_date'].tolist()
        
        results = {
            'total_dates': len(trade_dates),
            'success_count': 0,
            'failed_count': 0,
            'total_created': 0,
            'total_updated': 0,
            'errors': []
        }

        for date_str in trade_dates:
            try:
                date_obj = datetime.strptime(date_str, '%Y%m%d').date()
                result = cls._sync_limit_list(pro, date_str, date_obj)
                results['total_created'] += result.get('created', 0)
                results['total_updated'] += result.get('updated', 0)
                results['success_count'] += 1
            except Exception as e:
                results['failed_count'] += 1
                results['errors'].append(f"{date_str}: {str(e)}")

        results['success'] = results['failed_count'] == 0
        return results

    @classmethod
    def refresh_selected_limit_ups(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        自动刷新选中的涨停记录完整数据。
        会从 Tushare 重新拉取所选日期的涨停、龙虎榜、概念数据，并重算龙头标记。
        """
        if not items:
            raise ValueError("请至少选择一条涨停记录")

        grouped: Dict[date, set[str]] = {}
        item_refs: List[Dict[str, Any]] = []
        for item in items:
            item_id = item.get("id")
            stock_code = item.get("stock_code")
            limit_up_date = item.get("limit_up_date")
            if not item_id or not stock_code or not limit_up_date:
                raise ValueError("批量更新参数缺少 id、stock_code 或 limit_up_date")
            date_obj = datetime.strptime(limit_up_date, "%Y-%m-%d").date()
            grouped.setdefault(date_obj, set()).add(stock_code)
            item_refs.append({"id": int(item_id), "limit_up_date": limit_up_date})

        pro = cls._get_pro()
        results = {
            "updated": 0,
            "dates": len(grouped),
            "errors": [],
            "items": [],
        }

        for date_obj, codes in grouped.items():
            date_str = date_obj.strftime("%Y%m%d")
            try:
                cls._sync_limit_list(pro, date_str, date_obj, target_codes=codes)
            except Exception as e:
                results["errors"].append(f"{date_obj}: 涨停数据刷新失败: {str(e)}")
            try:
                cls._sync_lhb_data(pro, date_str, date_obj, target_codes=codes)
            except Exception as e:
                results["errors"].append(f"{date_obj}: 龙虎榜刷新失败: {str(e)}")
            try:
                cls._sync_concept_data(pro, date_str, date_obj, target_codes=codes)
            except Exception as e:
                results["errors"].append(f"{date_obj}: 概念刷新失败: {str(e)}")
            try:
                cls._auto_identify_dragon(date_obj)
            except Exception as e:
                results["errors"].append(f"{date_obj}: 龙头重算失败: {str(e)}")

        with session_scope() as session:
            refreshed_items = []
            for ref in item_refs:
                obj = session.execute(
                    select(LimitUpStock).where(
                        and_(
                            LimitUpStock.id == ref["id"],
                            LimitUpStock.limit_up_date == datetime.strptime(ref["limit_up_date"], "%Y-%m-%d").date(),
                        )
                    )
                ).scalars().first()
                if obj:
                    refreshed_items.append(obj.to_dict())

        results["updated"] = len(refreshed_items)
        results["items"] = refreshed_items
        results["success"] = len(results["errors"]) == 0
        return results

    # =========================================================================
    # 数据查询接口
    # =========================================================================

    @classmethod
    def get_limit_up_reasons(cls, stock_code: str, days: int = 30) -> List[Dict]:
        """
        获取股票涨停原因（从新闻/公告）
        
        Args:
            stock_code: 股票代码
            days: 查询天数
        
        Returns:
            涨停原因列表
        """
        pro = cls._get_pro()
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
        try:
            # 获取公告数据
            df_ann = pro.anns(ts_code=stock_code, start_date=start_date, end_date=end_date)
            
            if df_ann is not None and not df_ann.empty:
                reasons = []
                for _, row in df_ann.iterrows():
                    if '涨停' in str(row.get('title', '')) or '涨幅' in str(row.get('title', '')):
                        reasons.append({
                            'date': row.get('ann_date'),
                            'title': row.get('title'),
                            'type': row.get('ann_type')
                        })
                return reasons[:10]
        except Exception:
            pass
        
        return []

    @classmethod
    def get_hot_concepts(cls, trade_date: str) -> List[Dict]:
        """
        获取热门概念板块
        
        Args:
            trade_date: 交易日期
        
        Returns:
            热门概念列表
        """
        pro = cls._get_pro()
        date_str = trade_date.replace('-', '') if '-' in trade_date else trade_date
        
        try:
            # 获取概念板块涨跌幅
            df = pro.concept_daily(trade_date=date_str)
            
            if df is not None and not df.empty:
                # 按涨跌幅排序
                df = df.sort_values('pct_chg', ascending=False)
                
                concepts = []
                for _, row in df.head(20).iterrows():
                    concepts.append({
                        'code': row.get('ts_code'),
                        'name': row.get('name'),
                        'pct_chg': float(row.get('pct_chg', 0) or 0),
                        'amount': float(row.get('amount', 0) or 0)
                    })
                return concepts
        except Exception:
            pass
        
        return []

    @classmethod
    def get_stock_concepts(cls, stock_code: str) -> List[str]:
        """
        获取股票所属概念
        
        Args:
            stock_code: 股票代码
        
        Returns:
            概念列表
        """
        pro = cls._get_pro()
        
        try:
            df = pro.concept_detail(ts_code=stock_code, src='ts')
            
            if df is not None and not df.empty:
                return df['concept_name'].tolist()[:10]
        except Exception:
            pass
        
        return []

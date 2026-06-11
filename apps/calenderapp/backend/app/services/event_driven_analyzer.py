"""
事件驱动分析服务
从真实数据源获取事件信息
"""
import json
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any

from app.config import get_tushare_pro


class EventDrivenAnalyzer:
    """事件驱动分析器 - 从真实数据源获取事件"""

    _pro = None

    @classmethod
    def _get_pro(cls):
        """获取 Tushare API 实例"""
        if cls._pro is None:
            cls._pro = get_tushare_pro()
        return cls._pro

    @classmethod
    def fetch_real_events(cls, stock_code: str, stock_name: str, 
                          analysis_date: date) -> List[Dict[str, Any]]:
        """
        获取真实事件驱动因素
        
        Args:
            stock_code: 股票代码（如 002471.SZ）
            stock_name: 股票名称
            analysis_date: 分析日期
        
        Returns:
            事件列表，每个事件包含：
            - event: 事件内容
            - source: 事件来源
            - time: 事件时间
            - impact: 影响分析
            - url: 来源链接
            - type: 事件类型
        """
        events = []
        date_str = analysis_date.strftime('%Y%m%d')
        
        # 1. 获取个股新闻
        news_events = cls._fetch_stock_news(stock_code, stock_name, date_str)
        events.extend(news_events)
        
        # 2. 获取公司公告
        ann_events = cls._fetch_announcements(stock_code, date_str)
        events.extend(ann_events)
        
        # 3. 获取行业/概念事件
        concept_events = cls._fetch_concept_events(stock_name, date_str)
        events.extend(concept_events)
        
        # 4. 获取龙虎榜资金事件
        fund_events = cls._fetch_fund_events(stock_code, stock_name, date_str)
        events.extend(fund_events)
        
        # 按时间排序，最新的在前
        events.sort(key=lambda x: x.get('time', ''), reverse=True)
        
        return events

    @classmethod
    def _fetch_stock_news(cls, stock_code: str, stock_name: str, 
                          date_str: str) -> List[Dict]:
        """获取个股相关新闻"""
        events = []
        pro = cls._get_pro()
        
        try:
            # 方法1：个股新闻
            df = pro.news(
                src='sina',
                start_date=date_str,
                end_date=date_str
            )
            
            if df is not None and not df.empty:
                # 过滤与该股票相关的新闻
                for _, row in df.head(10).iterrows():
                    title = row.get('title', '')
                    content = row.get('content', '')
                    
                    # 检查是否与股票相关
                    if stock_name in title or stock_name in content or stock_code[:6] in title:
                        events.append({
                            'event': title,
                            'source': '财经新闻',
                            'time': str(row.get('pub_time', date_str)),
                            'impact': cls._extract_impact(title, content),
                            'url': row.get('url', ''),
                            'type': 'news'
                        })
        except Exception as e:
            print(f"获取新闻失败: {e}")
        
        # 方法2：尝试获取个股特定新闻
        try:
            df = pro.news_content(
                ts_code=stock_code,
                start_date=date_str,
                end_date=date_str
            )
            
            if df is not None and not df.empty:
                for _, row in df.head(5).iterrows():
                    events.append({
                        'event': row.get('title', ''),
                        'source': '个股新闻',
                        'time': str(row.get('pub_time', date_str)),
                        'impact': cls._extract_impact(
                            row.get('title', ''), 
                            row.get('content', '')
                        ),
                        'url': row.get('url', ''),
                        'type': 'stock_news'
                    })
        except Exception:
            pass
        
        return events

    @classmethod
    def _fetch_announcements(cls, stock_code: str, date_str: str) -> List[Dict]:
        """获取公司公告"""
        events = []
        pro = cls._get_pro()
        
        try:
            df = pro.anns(
                ts_code=stock_code,
                start_date=date_str,
                end_date=date_str
            )
            
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get('title', '')
                    ann_type = row.get('ann_type', '')
                    
                    # 公告类型映射
                    type_map = {
                        '业绩预告': '业绩利好',
                        '业绩快报': '业绩数据',
                        '重大事项': '重大事件',
                        '重组': '资产重组',
                        '股权': '股权变动',
                        '融资': '融资事件',
                    }
                    
                    impact_type = type_map.get(ann_type, '公司公告')
                    
                    events.append({
                        'event': title,
                        'source': '公司公告',
                        'time': str(row.get('ann_date', date_str)),
                        'impact': f"{impact_type}：{title}",
                        'url': f"https://tushare.pro/news/{row.get('ann_code', '')}",
                        'type': 'announcement'
                    })
        except Exception as e:
            print(f"获取公告失败: {e}")
        
        return events

    @classmethod
    def _fetch_concept_events(cls, stock_name: str, date_str: str) -> List[Dict]:
        """获取概念/行业事件"""
        events = []
        pro = cls._get_pro()
        
        try:
            # 获取当日热点概念
            df = pro.concept_daily(trade_date=date_str)
            
            if df is not None and not df.empty:
                # 取涨幅最大的概念
                hot_concepts = df.nlargest(5, 'pct_chg')
                
                for _, row in hot_concepts.iterrows():
                    concept_name = row.get('name', '')
                    pct_chg = row.get('pct_chg', 0)
                    
                    events.append({
                        'event': f"概念板块【{concept_name}】大涨{pct_chg:.2f}%",
                        'source': '板块行情',
                        'time': date_str,
                        'impact': f"{concept_name}概念板块集体走强，相关个股受益",
                        'url': '',
                        'type': 'concept'
                    })
        except Exception:
            pass
        
        return events

    @classmethod
    def _fetch_fund_events(cls, stock_code: str, stock_name: str, 
                           date_str: str) -> List[Dict]:
        """获取资金动向事件"""
        events = []
        pro = cls._get_pro()
        
        try:
            # 龙虎榜数据
            df = pro.top_inst(trade_date=date_str)
            
            if df is not None and not df.empty:
                stock_df = df[df['ts_code'] == stock_code]
                
                if not stock_df.empty:
                    for _, row in stock_df.iterrows():
                        exalter = row.get('exalter', '')
                        net_buy = row.get('net_buy', 0)
                        
                        if '机构专用' in exalter:
                            events.append({
                                'event': f"机构专用席位净买入{abs(net_buy)/10000:.0f}万元",
                                'source': '龙虎榜',
                                'time': date_str,
                                'impact': f"机构资金介入，显示专业投资者看好",
                                'url': '',
                                'type': 'institution'
                            })
                        elif '沪股通' in exalter or '深股通' in exalter:
                            events.append({
                                'event': f"北向资金净买入{abs(net_buy)/10000:.0f}万元",
                                'source': '龙虎榜',
                                'time': date_str,
                                'impact': f"外资看好，北向资金持续流入",
                                'url': '',
                                'type': 'north'
                            })
                        else:
                            # 游资席位
                            if net_buy > 0:
                                events.append({
                                    'event': f"游资【{exalter}】净买入{net_buy/10000:.0f}万元",
                                    'source': '龙虎榜',
                                    'time': date_str,
                                    'impact': f"知名游资入场，短线资金活跃",
                                    'url': '',
                                    'type': 'hot_money'
                                })
        except Exception:
            pass
        
        return events

    @classmethod
    def _extract_impact(cls, title: str, content: str) -> str:
        """从标题和内容提取影响分析"""
        text = f"{title} {content}"
        
        # 关键词匹配
        impact_patterns = [
            ('涨停', '触发涨停板'),
            ('利好', '利好消息驱动'),
            ('业绩大增', '业绩超预期'),
            ('中标', '新签订单'),
            ('重组', '资产重组预期'),
            ('政策', '政策利好'),
            ('突破', '技术突破'),
            ('订单', '订单增加'),
            ('合作', '战略合作'),
            ('并购', '并购预期'),
        ]
        
        for keyword, impact in impact_patterns:
            if keyword in text:
                return impact
        
        return "需进一步分析"

    @classmethod
    def get_main_event(cls, events: List[Dict]) -> Optional[Dict]:
        """从事件列表中提取主要事件"""
        if not events:
            return None
        
        # 优先级：公告 > 新闻 > 龙虎榜 > 概念
        type_priority = {
            'announcement': 1,
            'stock_news': 2,
            'news': 3,
            'institution': 4,
            'hot_money': 5,
            'north': 6,
            'concept': 7,
        }
        
        sorted_events = sorted(
            events, 
            key=lambda x: type_priority.get(x.get('type', ''), 99)
        )
        
        return sorted_events[0] if sorted_events else None


if __name__ == "__main__":
    # 测试
    events = EventDrivenAnalyzer.fetch_real_events(
        stock_code='002471.SZ',
        stock_name='中超控股',
        analysis_date=date(2026, 4, 2)
    )
    
    print(f"\n=== 获取到 {len(events)} 个事件 ===\n")
    for i, evt in enumerate(events, 1):
        print(f"{i}. [{evt['source']}] {evt['event']}")
        print(f"   时间: {evt['time']}")
        print(f"   影响: {evt['impact']}")
        print()
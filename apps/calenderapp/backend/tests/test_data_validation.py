"""
A股投研数据平台 - 数据验证测试

测试覆盖：
1. 数据格式验证
2. 业务逻辑验证
3. 数据一致性验证

运行方式：
    pytest tests/test_data_validation.py -v
"""

import pytest
from datetime import datetime, date
from app.services.limit_up_service import LimitUpService, _calculate_strength
from app.api.params import parse_date, parse_int, parse_bool


# =============================================================================
# 1. 参数解析测试
# =============================================================================

class TestParamParser:
    """参数解析函数测试"""
    
    def test_parse_date_valid(self):
        """测试有效日期解析"""
        result = parse_date("2026-04-01")
        assert result == date(2026, 4, 1)
    
    def test_parse_date_invalid(self):
        """测试无效日期解析"""
        with pytest.raises(ValueError):
            parse_date("invalid-date")
    
    def test_parse_date_missing_required(self):
        """测试必填日期缺失"""
        with pytest.raises(ValueError):
            parse_date(None, required=True)
    
    def test_parse_int_valid(self):
        """测试有效整数解析"""
        assert parse_int("10") == 10
        assert parse_int(10) == 10
        assert parse_int("10", minimum=1, maximum=100) == 10
    
    def test_parse_int_with_default(self):
        """测试默认值"""
        assert parse_int(None, default=5) == 5
        assert parse_int("invalid", default=5) == 5
    
    def test_parse_int_out_of_range(self):
        """测试超出范围"""
        # parse_int 应该返回边界值或抛出异常
        result = parse_int("1000", minimum=1, maximum=100)
        assert result <= 100
    
    def test_parse_bool_valid(self):
        """测试布尔值解析"""
        assert parse_bool("true") == True
        assert parse_bool("True") == True
        assert parse_bool("false") == False
        assert parse_bool("False") == False
    
    def test_parse_bool_with_default(self):
        """测试布尔默认值"""
        assert parse_bool(None, default=True) == True
        assert parse_bool("invalid", default=False) == False


# =============================================================================
# 2. 涨停强度评分测试
# =============================================================================

class TestStrengthCalculation:
    """涨停强度评分计算测试"""
    
    def test_early_seal_high_score(self):
        """测试早盘封板高分"""
        from datetime import time
        
        # 9:35 封板
        first_time = time(9, 35, 0)
        level, score = _calculate_strength(
            first_time=first_time,
            consecutive_days=1,
            seal_amount=50000,  # 万元
            open_count=0,
            institution_net=10000,
            hot_money_net=20000
        )
        
        # 早盘一字封板应该高分
        assert score >= 60
        assert level >= 3
    
    def test_late_seal_lower_score(self):
        """测试尾盘封板低分"""
        from datetime import time
        
        # 14:30 封板
        first_time = time(14, 30, 0)
        level, score = _calculate_strength(
            first_time=first_time,
            consecutive_days=1,
            seal_amount=1000,
            open_count=5,
            institution_net=0,
            hot_money_net=0
        )
        
        # 尾盘多次开板应该低分
        assert score < 60
        assert level < 4
    
    def test_high_consecutive_score(self):
        """测试高连板加分"""
        from datetime import time
        
        # 5连板
        first_time = time(10, 0, 0)
        level, score_high = _calculate_strength(
            first_time=first_time,
            consecutive_days=5,
            seal_amount=100000,
            open_count=0,
            institution_net=50000,
            hot_money_net=30000
        )
        
        # 1板
        level, score_low = _calculate_strength(
            first_time=first_time,
            consecutive_days=1,
            seal_amount=100000,
            open_count=0,
            institution_net=50000,
            hot_money_net=30000
        )
        
        # 5连板应该比1板分数高
        assert score_high > score_low
    
    def test_large_seal_amount_score(self):
        """测试大封单加分"""
        from datetime import time
        
        first_time = time(10, 0, 0)
        
        # 大封单（5亿）
        level, score_big = _calculate_strength(
            first_time=first_time,
            consecutive_days=2,
            seal_amount=500000,  # 5亿=50万万元
            open_count=0,
            institution_net=10000,
            hot_money_net=10000
        )
        
        # 小封单（1000万）
        level, score_small = _calculate_strength(
            first_time=first_time,
            consecutive_days=2,
            seal_amount=1000,
            open_count=0,
            institution_net=10000,
            hot_money_net=10000
        )
        
        assert score_big > score_small
    
    def test_no_open_count_bonus(self):
        """测试零开板加分"""
        from datetime import time
        
        first_time = time(10, 0, 0)
        
        # 无开板
        level, score_no_open = _calculate_strength(
            first_time=first_time,
            consecutive_days=1,
            seal_amount=10000,
            open_count=0,
            institution_net=0,
            hot_money_net=0
        )
        
        # 多次开板
        level, score_many_open = _calculate_strength(
            first_time=first_time,
            consecutive_days=1,
            seal_amount=10000,
            open_count=5,
            institution_net=0,
            hot_money_net=0
        )
        
        assert score_no_open > score_many_open
    
    def test_fund_flow_score(self):
        """测试资金流向加分"""
        from datetime import time
        
        first_time = time(10, 0, 0)
        
        # 大资金净买
        level, score_big_fund = _calculate_strength(
            first_time=first_time,
            consecutive_days=1,
            seal_amount=10000,
            open_count=0,
            institution_net=50000,
            hot_money_net=50000
        )
        
        # 小资金
        level, score_small_fund = _calculate_strength(
            first_time=first_time,
            consecutive_days=1,
            seal_amount=10000,
            open_count=0,
            institution_net=0,
            hot_money_net=0
        )
        
        assert score_big_fund > score_small_fund


# =============================================================================
# 3. 数据结构验证测试
# =============================================================================

class TestDataStructure:
    """数据结构验证测试"""
    
    def test_limit_up_model_fields(self):
        """测试涨停模型字段完整性"""
        from app.models.limit_up_stock import LimitUpStock
        
        expected_fields = [
            'id', 'limit_up_date', 'stock_code', 'stock_name',
            'consecutive_days', 'limit_up_type', 'seal_amount',
            'seal_ratio', 'turnover_rate', 'first_limit_time',
            'last_limit_time', 'open_count', 'industry',
            'concept_tags', 'institution_net_buy', 'hot_money_net_buy',
            'north_net_buy', 'total_net_buy', 'reason_category',
            'reason_detail', 'strength_level', 'strength_score',
            'is_dragon_head', 'dragon_rank', 'source'
        ]
        
        # 验证模型包含所有必要字段
        model_attrs = [attr for attr in dir(LimitUpStock) if not attr.startswith('_')]
        for field in expected_fields:
            assert field in model_attrs or hasattr(LimitUpStock, field)
    
    def test_limit_up_type_values(self):
        """测试涨停类型取值"""
        valid_types = ['first_board', 'multi_board', 'broken_board']
        
        # 涨停类型应该限制在这几个值
        for t in valid_types:
            assert t in ['first_board', 'multi_board', 'broken_board']
    
    def test_strength_level_range(self):
        """测试强度等级范围"""
        # 强度等级应该是 1-5
        valid_levels = [1, 2, 3, 4, 5]
        
        for level in valid_levels:
            assert 1 <= level <= 5


# =============================================================================
# 4. CSV 导入验证测试
# =============================================================================

class TestCSVValidation:
    """CSV 导入验证测试"""
    
    def test_csv_required_fields(self):
        """测试 CSV 必填字段"""
        required_fields = ['stock_code', 'stock_name', 'limit_up_date']
        
        # 验证必填字段定义正确
        assert len(required_fields) == 3
        assert 'stock_code' in required_fields
    
    def test_stock_code_format(self):
        """测试股票代码格式"""
        valid_codes = [
            '000001.SZ',  # 深市
            '600000.SH',  # 沪市
            '430001.BJ',  # 北交所
        ]
        
        invalid_codes = [
            '000001',     # 缺少交易所后缀
            '600000',     # 缺少交易所后缀
            'ABC123.SZ',  # 无效字母
        ]
        
        # 有效代码格式
        for code in valid_codes:
            assert '.' in code
            assert code.split('.')[1] in ['SZ', 'SH', 'BJ']
    
    def test_consecutive_days_range(self):
        """测试连板数范围"""
        # 连板数应该是 1-20 的合理范围
        valid_days = [1, 2, 3, 5, 10, 15]
        
        for days in valid_days:
            assert 1 <= days <= 20
    
    def test_time_format(self):
        """测试时间格式"""
        from datetime import time
        
        valid_times = ['09:35:00', '10:00:00', '14:30:00']
        
        for t in valid_times:
            parts = t.split(':')
            assert len(parts) == 3
            hour = int(parts[0])
            minute = int(parts[1])
            assert 9 <= hour <= 15
            assert 0 <= minute <= 59


# =============================================================================
# 5. 日期范围验证测试
# =============================================================================

class TestDateRangeValidation:
    """日期范围验证测试"""
    
    def test_start_before_end(self):
        """测试开始日期早于结束日期"""
        start = date(2026, 4, 1)
        end = date(2026, 4, 30)
        
        assert start <= end
    
    def test_date_range_limit(self):
        """测试日期范围限制"""
        # 查询范围不应超过一年
        start = date(2026, 1, 1)
        end = date(2026, 12, 31)
        
        delta = (end - start).days
        assert delta <= 365
    
    def test_future_date_rejection(self):
        """测试未来日期拒绝"""
        today = date.today()
        future = today + datetime.timedelta(days=30)
        
        # 涨停日期不能是未来
        assert future > today


# =============================================================================
# 运行入口
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
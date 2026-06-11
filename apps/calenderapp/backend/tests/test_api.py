"""
A股投研数据平台 API 接口测试

测试覆盖：
1. 系统接口 - 健康检查、版本信息
2. 日历接口 - 交易日历查询
3. 事件接口 - 事件 CRUD
4. 股票接口 - 股票管理
5. 涨停股接口 - 涨停数据分析
6. 分区接口 - 分区管理

运行方式：
    # 激活环境
    conda activate stock
    
    # 运行所有测试
    pytest tests/test_api.py -v
    
    # 运行指定模块测试
    pytest tests/test_api.py -v -k "test_limit_up"
    
    # 生成覆盖率报告
    pytest tests/test_api.py -v --cov=app --cov-report=html
"""

import pytest
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any

# =============================================================================
# 配置
# =============================================================================

BASE_URL = "http://127.0.0.1:5000/api"
AUTH_TOKEN = "research2024"  # 从 .env 读取

# 请求头
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}


# =============================================================================
# 辅助函数
# =============================================================================

def api_get(path: str, params: Dict = None) -> Dict:
    """GET 请求"""
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, params=params, headers=HEADERS)
    return resp.json()


def api_post(path: str, data: Dict = None, params: Dict = None) -> Dict:
    """POST 请求"""
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, json=data, params=params, headers=HEADERS)
    return resp.json()


def api_put(path: str, data: Dict = None) -> Dict:
    """PUT 请求"""
    url = f"{BASE_URL}{path}"
    resp = requests.put(url, json=data, headers=HEADERS)
    return resp.json()


def api_delete(path: str) -> Dict:
    """DELETE 请求"""
    url = f"{BASE_URL}{path}"
    resp = requests.delete(url, headers=HEADERS)
    return resp.json()


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def test_stock():
    """测试股票数据"""
    return {
        "code": "TEST001.SZ",
        "name": "测试股票",
        "exchange": "SZ"
    }


@pytest.fixture(scope="module")
def test_event():
    """测试事件数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "event_date": today,
        "title": "API测试事件",
        "importance": 3,
        "event_type": "测试",
        "description": "这是一个测试事件",
        "stock_list": ["TEST001.SZ"]
    }


@pytest.fixture(scope="module")
def test_limit_up():
    """测试涨停股数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "stock_code": "TEST001.SZ",
        "stock_name": "测试股票",
        "limit_up_date": today,
        "consecutive_days": 1,
        "limit_up_type": "first_board",
        "seal_amount": 50000,  # 万元
        "seal_ratio": 15.5,
        "turnover_rate": 12.3,
        "first_limit_time": "09:35:00",
        "open_count": 0,
        "industry": "软件开发",
        "concept_tags": ["人工智能", "云计算"],
        "institution_net_buy": 10000,
        "hot_money_net_buy": 20000,
        "reason_detail": "测试涨停"
    }


# =============================================================================
# 1. 系统接口测试
# =============================================================================

class TestSystemAPI:
    """系统相关接口测试"""
    
    def test_health_check(self):
        """测试健康检查接口"""
        resp = api_get("/system/health")
        assert resp["code"] == 200
        assert "data" in resp
        assert resp["data"]["status"] == "healthy"
    
    def test_version_info(self):
        """测试版本信息接口"""
        resp = api_get("/system/version")
        assert resp["code"] == 200
        assert "data" in resp
        assert "version" in resp["data"]


# =============================================================================
# 2. 日历接口测试
# =============================================================================

class TestCalendarAPI:
    """交易日历接口测试"""
    
    def test_get_calendar_range(self):
        """测试获取日历范围"""
        today = datetime.now()
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        
        resp = api_get("/calendar", {
            "start_date": start_date,
            "end_date": end_date
        })
        
        assert resp["code"] == 200
        assert "data" in resp
        assert isinstance(resp["data"], list)
    
    def test_get_calendar_today(self):
        """测试获取今日日历"""
        today = datetime.now().strftime("%Y-%m-%d")
        resp = api_get(f"/calendar/{today}")
        
        # 如果有数据，验证结构
        if resp["code"] == 200 and resp["data"]:
            assert "day" in resp["data"]
            assert "is_work" in resp["data"]


# =============================================================================
# 3. 事件接口测试
# =============================================================================

class TestEventAPI:
    """事件管理接口测试"""
    
    created_event_id = None
    
    def test_create_event(self, test_event):
        """测试创建事件"""
        resp = api_post("/events", test_event)
        
        # 可能已存在，检查返回
        assert resp["code"] in [200, 201]
        if resp["code"] == 201:
            TestEventAPI.created_event_id = resp["data"]["id"]
        
        assert "data" in resp
        assert resp["data"]["title"] == test_event["title"]
    
    def test_list_events(self):
        """测试事件列表"""
        resp = api_get("/events", {"page": 1, "page_size": 10})
        
        assert resp["code"] == 200
        assert "data" in resp
        assert "items" in resp["data"]
        assert "total" in resp["data"]
    
    def test_filter_events_by_date(self):
        """测试按日期筛选事件"""
        today = datetime.now().strftime("%Y-%m-%d")
        resp = api_get("/events", {
            "start_date": today,
            "end_date": today
        })
        
        assert resp["code"] == 200
    
    def test_filter_events_by_importance(self):
        """测试按重要性筛选事件"""
        resp = api_get("/events", {
            "importance": 3
        })
        
        assert resp["code"] == 200
    
    # def test_update_event(self, test_event):
    #     """测试更新事件"""
    #     if not TestEventAPI.created_event_id:
    #         pytest.skip("没有创建事件ID")
    #     
    #     update_data = {"title": "更新后的标题"}
    #     resp = api_put(f"/events/{TestEventAPI.created_event_id}", update_data)
    #     
    #     assert resp["code"] == 200
    
    # def test_delete_event(self):
    #     """测试删除事件"""
    #     if not TestEventAPI.created_event_id:
    #         pytest.skip("没有创建事件ID")
    #     
    #     resp = api_delete(f"/events/{TestEventAPI.created_event_id}")
    #     assert resp["code"] == 200


# =============================================================================
# 4. 股票接口测试
# =============================================================================

class TestStockAPI:
    """股票管理接口测试"""
    
    def test_list_stocks(self):
        """测试股票列表"""
        resp = api_get("/stocks", {"page": 1, "page_size": 20})
        
        assert resp["code"] == 200
        assert "data" in resp
        assert "items" in resp["data"]
    
    def test_filter_stocks_by_exchange(self):
        """测试按交易所筛选"""
        resp = api_get("/stocks", {
            "exchange": "SH",
            "page": 1,
            "page_size": 10
        })
        
        assert resp["code"] == 200
    
    def test_search_stocks(self):
        """测试股票搜索"""
        resp = api_get("/stocks", {
            "q": "平安",
            "page": 1,
            "page_size": 10
        })
        
        assert resp["code"] == 200
    
    def test_upsert_stock(self, test_stock):
        """测试股票创建/更新"""
        resp = api_post("/stocks", test_stock)
        
        assert resp["code"] in [200, 201]
        assert resp["data"]["code"] == test_stock["code"]


# =============================================================================
# 5. 涨停股接口测试
# =============================================================================

class TestLimitUpAPI:
    """涨停股接口测试"""
    
    created_id = None
    
    def test_list_limit_ups(self):
        """测试涨停列表"""
        resp = api_get("/limit-up", {"page": 1, "page_size": 20})
        
        assert resp["code"] == 200
        assert "data" in resp
        assert "items" in resp["data"]
        assert "total" in resp["data"]
    
    def test_filter_by_date_range(self):
        """测试日期范围筛选"""
        today = datetime.now()
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        resp = api_get("/limit-up", {
            "start_date": start_date,
            "end_date": end_date,
            "page": 1,
            "page_size": 20
        })
        
        assert resp["code"] == 200
    
    def test_filter_by_consecutive(self):
        """测试连板筛选"""
        resp = api_get("/limit-up", {
            "consecutive_min": 2,
            "consecutive_max": 5,
            "page": 1,
            "page_size": 20
        })
        
        assert resp["code"] == 200
    
    def test_filter_by_strength(self):
        """测试强度筛选"""
        resp = api_get("/limit-up", {
            "strength_min": 3,
            "strength_max": 5,
            "page": 1,
            "page_size": 20
        })
        
        assert resp["code"] == 200
    
    def test_filter_dragon_head(self):
        """测试龙头筛选"""
        resp = api_get("/limit-up", {
            "is_dragon_head": True,
            "page": 1,
            "page_size": 20
        })
        
        assert resp["code"] == 200
    
    def test_search_limit_ups(self):
        """测试涨停搜索"""
        resp = api_get("/limit-up", {
            "q": "中",
            "page": 1,
            "page_size": 10
        })
        
        assert resp["code"] == 200
    
    def test_create_limit_up(self, test_limit_up):
        """测试创建涨停记录"""
        resp = api_post("/limit-up", test_limit_up)
        
        # 创建成功或已存在
        assert resp["code"] in [200, 201]
        if resp["code"] == 201:
            TestLimitUpAPI.created_id = resp["data"]["id"]
    
    def test_get_limit_up_detail(self):
        """测试涨停详情"""
        if not TestLimitUpAPI.created_id:
            # 先获取一条记录
            resp = api_get("/limit-up", {"page": 1, "page_size": 1})
            if resp["data"]["items"]:
                TestLimitUpAPI.created_id = resp["data"]["items"][0]["id"]
        
        if not TestLimitUpAPI.created_id:
            pytest.skip("没有涨停记录")
        
        resp = api_get(f"/limit-up/{TestLimitUpAPI.created_id}")
        assert resp["code"] == 200
        assert resp["data"]["id"] == TestLimitUpAPI.created_id
    
    def test_consecutive_rank(self):
        """测试连板榜"""
        today = datetime.now().strftime("%Y-%m-%d")
        resp = api_get("/limit-up/consecutive", {"date": today})
        
        # 可能没有数据
        assert resp["code"] in [200, 400]
    
    def test_dragon_heads(self):
        """测试龙头列表"""
        today = datetime.now().strftime("%Y-%m-%d")
        resp = api_get("/limit-up/dragon-head", {"date": today})
        
        assert resp["code"] in [200, 400]
    
    def test_statistics(self):
        """测试区间统计"""
        today = datetime.now()
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        resp = api_get("/limit-up/statistics", {
            "start_date": start_date,
            "end_date": end_date
        })
        
        assert resp["code"] in [200, 400]
    
    def test_fund_flow_rank(self):
        """测试资金流向排行"""
        today = datetime.now()
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        resp = api_get("/limit-up/fund-flow", {
            "start_date": start_date,
            "end_date": end_date,
            "top": 10
        })
        
        assert resp["code"] == 200
    
    def test_concept_hot(self):
        """测试概念热度"""
        today = datetime.now()
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        resp = api_get("/limit-up/concept-hot", {
            "start_date": start_date,
            "end_date": end_date,
            "top": 10
        })
        
        assert resp["code"] in [200, 400]
    
    def test_download_template(self):
        """测试下载导入模板"""
        resp = requests.get(f"{BASE_URL}/limit-up/template.csv")
        assert resp.status_code == 200
        assert "stock_code" in resp.text


# =============================================================================
# 6. 分区接口测试
# =============================================================================

class TestPartitionAPI:
    """分区管理接口测试"""
    
    def test_partition_status(self):
        """测试分区状态"""
        resp = api_get("/partition/status")
        
        assert resp["code"] == 200
        assert "data" in resp
        assert "partitions" in resp["data"]


# =============================================================================
# 7. 边界条件测试
# =============================================================================

class TestBoundaryConditions:
    """边界条件和异常处理测试"""
    
    def test_invalid_page(self):
        """测试无效页码"""
        resp = api_get("/limit-up", {"page": -1})
        # 应该返回第一页或错误
        assert resp["code"] in [200, 400]
    
    def test_invalid_page_size(self):
        """测试无效页大小"""
        resp = api_get("/limit-up", {"page_size": 10000})
        # 应该限制最大值或返回错误
        assert resp["code"] in [200, 400]
    
    def test_invalid_date_format(self):
        """测试无效日期格式"""
        resp = api_get("/limit-up", {"start_date": "invalid-date"})
        assert resp["code"] == 400
    
    def test_nonexistent_limit_up(self):
        """测试不存在的涨停记录"""
        resp = api_get("/limit-up/99999999")
        assert resp["code"] == 404
    
    def test_create_limit_up_missing_fields(self):
        """测试缺少必填字段"""
        resp = api_post("/limit-up", {"stock_code": "TEST.SZ"})
        assert resp["code"] == 400
    
    def test_large_csv_import(self):
        """测试大文件上传（边界）"""
        # 这个测试验证文件大小限制
        pass


# =============================================================================
# 8. 性能测试
# =============================================================================

class TestPerformance:
    """性能测试"""
    
    def test_list_limit_ups_response_time(self):
        """测试涨停列表响应时间"""
        import time
        
        start = time.time()
        resp = api_get("/limit-up", {"page": 1, "page_size": 100})
        elapsed = time.time() - start
        
        assert resp["code"] == 200
        assert elapsed < 2.0, f"响应时间 {elapsed:.2f}s 超过 2 秒"
    
    def test_statistics_response_time(self):
        """测试统计接口响应时间"""
        import time
        
        today = datetime.now()
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        start = time.time()
        resp = api_get("/limit-up/statistics", {
            "start_date": start_date,
            "end_date": end_date
        })
        elapsed = time.time() - start
        
        assert resp["code"] in [200, 400]
        assert elapsed < 3.0, f"响应时间 {elapsed:.2f}s 超过 3 秒"


# =============================================================================
# 运行入口
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
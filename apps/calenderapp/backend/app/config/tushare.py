"""
Tushare API 配置模块
统一管理 Tushare Token 和 API URL
"""
import os

# 从环境变量读取配置
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
TUSHARE_API_URL = os.environ.get("TUSHARE_API_URL", "https://api.tushare.pro")


def get_tushare_pro():
    """
    获取 Tushare API 实例（懒加载）
    
    Returns:
        tushare.pro_api 实例
    """
    import tushare as ts
    
    if not TUSHARE_TOKEN:
        raise ValueError("TUSHARE_TOKEN 未配置，请检查 .env 文件")
    
    pro = ts.pro_api(TUSHARE_TOKEN)
    pro._DataApi__token = TUSHARE_TOKEN
    pro._DataApi__http_url = TUSHARE_API_URL
    
    return pro
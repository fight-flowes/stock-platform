"""
日志配置模块

提供结构化日志支持，包含：
- JSON 格式输出
- 请求 ID 追踪
- 日志级别控制
"""

import logging
import sys
from datetime import datetime
from functools import wraps
from flask import request, g
import uuid
import json


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # 添加额外字段
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        if hasattr(record, 'stock_code'):
            log_entry["stock_code"] = record.stock_code
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        
        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_level=logging.INFO, json_output=True):
    """
    配置日志系统
    
    Args:
        log_level: 日志级别
        json_output: 是否使用 JSON 格式输出
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 移除默认处理器
    root_logger.handlers = []
    
    # 添加控制台处理器
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s [%(name)s] %(message)s'
        )
        handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
    
    # 设置第三方库日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


def get_logger(name):
    """获取日志记录器"""
    return logging.getLogger(name)


# 全局日志记录器
logger = get_logger('app')


def request_id_middleware():
    """
    Flask 中间件：为每个请求生成唯一 ID
    
    使用方式：
        from app.utils.logging_config import request_id_middleware
        
        app = Flask(__name__)
        app.before_request(request_id_middleware)
    """
    g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())[:8]


def log_request(func):
    """
    请求日志装饰器
    
    使用方式：
        @log_request
        def some_api():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        request_id = getattr(g, 'request_id', 'unknown')
        logger.info(
            f"Request started: {request.method} {request.path}",
            extra={'request_id': request_id}
        )
        
        try:
            result = func(*args, **kwargs)
            logger.info(
                f"Request completed: {request.method} {request.path}",
                extra={'request_id': request_id}
            )
            return result
        except Exception as e:
            logger.error(
                f"Request failed: {request.method} {request.path} - {str(e)}",
                extra={'request_id': request_id},
                exc_info=True
            )
            raise
    
    return wrapper


class LogContext:
    """
    日志上下文管理器
    
    使用方式：
        with LogContext(stock_code='600488.SH'):
            logger.info("Processing stock")
    """
    
    def __init__(self, **kwargs):
        self.extra = kwargs
        self.old_factory = None
    
    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.extra.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, *args):
        logging.setLogRecordFactory(self.old_factory)
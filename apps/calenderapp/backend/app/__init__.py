import logging

from flask import Flask
from flask_cors import CORS
from flask_restx import Api
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

from app.api.calendar import calendar_ns
from app.api.events import events_ns
from app.api.stocks import stocks_ns
from app.api.system import system_ns
from app.api.limit_up import limit_up_ns
from app.api.partition import partition_ns
from app.api.stockkb import stockkb_ns
from app.api.announcements import announcements_ns
from app.db import Base, engine, ensure_schema
from app.models import CalendarDay, CalendarEvent, LimitUpStock, Stock
from config.api_config import APIConstants, APIResponse


def create_app():
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    app.config["JSON_SORT_KEYS"] = False
    app.config["RESTX_MASK_SWAGGER"] = False
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    api = Api(
        app,
        version="5.1.0",
        title="A股投研数据平台 API",
        description="A股投研数据平台（v5.1）",
        doc="/api/docs/",
    )

    api.add_namespace(system_ns, path="/api/system")
    api.add_namespace(calendar_ns, path="/api/calendar")
    api.add_namespace(events_ns, path="/api/events")
    api.add_namespace(stocks_ns, path="/api/stocks")
    api.add_namespace(limit_up_ns, path="/api/limit-up")
    api.add_namespace(partition_ns, path="/api/partition")
    api.add_namespace(stockkb_ns, path="/api/stockkb")
    api.add_namespace(announcements_ns, path="/api/announcements")

    @app.get("/health")
    def health():
        return APIResponse.success({"status": "healthy", "service": "a-stock-research-v5.1"})

    @app.get("/")
    def index():
        return APIResponse.success(
            {"message": "a-stock-research-v5.1", "documentation": "/api/docs/", "health": "/health"}
        )

    @app.errorhandler(404)
    def not_found(_):
        return APIResponse.error(
            message="资源未找到",
            code=APIConstants.ERROR_CODES["NOT_FOUND"],
            http_status=404,
        ), 404

    @app.errorhandler(500)
    def internal_error(_):
        return APIResponse.error(
            message="服务器内部错误",
            code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
            http_status=500,
        ), 500

    @app.errorhandler(ValueError)
    def validation_error(e):
        return APIResponse.error(
            message=str(e) or "参数错误",
            code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
            http_status=400,
        ), 400

    @app.errorhandler(SQLAlchemyError)
    def db_error(_):
        return APIResponse.error(
            message="数据库错误",
            code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
            http_status=500,
        ), 500

    try:
        ensure_schema()
        Base.metadata.create_all(engine)
    except Exception:
        logging.getLogger("db").exception("init_db_failed")

    return app

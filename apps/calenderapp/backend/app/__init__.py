import logging

from flask import Flask
from flask_cors import CORS
from flask_restx import Api
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

from app.api.calendar_v2 import calendar_v2_ns
from app.api.stocks import stocks_ns
from app.api.stock_groups import stock_groups_ns
from app.api.stock_tags import stock_tags_ns
from app.api.system import system_ns
from app.api.limit_up import limit_up_ns
from app.api.partition import partition_ns
from app.api.stockkb import stockkb_ns
from app.api.analysis import analysis_ns
from app.api.announcements import announcements_ns
from app.db import Base, engine, ensure_schema
from app.models import (
    LimitUpAnalysis,
    LimitUpStock,
    Stock,
    StockGroup,
    StockGroupMember,
    StockTag,
    StockTagBinding,
)
from config.api_config import APIConstants, APIResponse


def _ensure_stock_favorited_at_column():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE sc.stocks
                  ADD COLUMN IF NOT EXISTS favorited_at TIMESTAMPTZ
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_stocks_favorited_at
                  ON sc.stocks(favorited_at DESC)
                """
            )
        )
        conn.execute(
            text(
                """
                WITH ranked_favorites AS (
                  SELECT
                    id,
                    ROW_NUMBER() OVER (ORDER BY id DESC) AS rn
                  FROM sc.stocks
                  WHERE is_favorite = TRUE
                    AND favorited_at IS NULL
                )
                UPDATE sc.stocks AS stocks
                SET favorited_at = NOW() - ((ranked_favorites.rn - 1) * INTERVAL '1 second')
                FROM ranked_favorites
                WHERE stocks.id = ranked_favorites.id
                """
            )
        )


def create_app():
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
        title="A股事件投研平台 API",
        description="A股事件投研平台（v5.1）",
        doc="/api/docs/",
    )

    api.add_namespace(system_ns, path="/api/system")
    api.add_namespace(calendar_v2_ns, path="/api/calendar-v2")
    api.add_namespace(stocks_ns, path="/api/stocks")
    api.add_namespace(stock_groups_ns, path="/api/stock-groups")
    api.add_namespace(stock_tags_ns, path="/api/stock-tags")
    api.add_namespace(limit_up_ns, path="/api/limit-up")
    api.add_namespace(partition_ns, path="/api/partition")
    api.add_namespace(stockkb_ns, path="/api/stockkb")
    api.add_namespace(analysis_ns, path="/api/analysis")
    api.add_namespace(announcements_ns, path="/api/announcements")

    @app.get("/health")
    def health():
        return APIResponse.success({"status": "healthy", "service": "a-stock-research-v5.1"})

    @app.get("/")
    def index():
        return APIResponse.success(
            {"message": "a-stock-research-v5.1", "documentation": "/api/docs/", "health": "/health"}
        )

    # === API 认证中间件（L2）===
    # 默认关闭（AUTH_ENABLED=false），本地 / 现有部署零影响。开启后所有
    # 非公开路径必须带合法 Bearer token，否则 401。CORS 预检 OPTIONS
    # 一律放行（否则跨域请求会挂）。
    from flask import g, request

    from app.services.auth_service import (
        auth_enabled,
        extract_bearer_token,
        is_public_path,
        validate_token,
    )

    @app.before_request
    def _enforce_api_auth():
        if not auth_enabled():
            return None
        if request.method == "OPTIONS":
            return None
        if is_public_path(request.path):
            return None

        token = extract_bearer_token(request.headers.get("Authorization"))
        user = validate_token(token)
        if user is None:
            return (
                APIResponse.error(
                    message="未授权：缺少或无效的访问 Token",
                    code=APIConstants.ERROR_CODES["UNAUTHORIZED"],
                    http_status=401,
                ),
                401,
            )
        # 把身份挂到请求上下文，将来审计日志（L3）可直接取 g.current_user
        g.current_user = user
        return None

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
        _ensure_stock_favorited_at_column()
    except Exception:
        logging.getLogger("db").exception("init_db_failed")

    return app

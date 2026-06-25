from flask_restx import Namespace, Resource
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine, session_scope
from app.settings import PGSCHEMA
from config.api_config import APIConstants, APIResponse

system_ns = Namespace("system", description="系统与数据库")


@system_ns.route("/db-status")
class DBStatus(Resource):
    def get(self):
        try:
            info = {
                "dialect": engine.dialect.name,
                "driver": getattr(engine.dialect, "driver", None),
                "url": str(engine.url).replace(str(engine.url.password or ""), "***") if engine.url.password else str(engine.url),
            }
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            with session_scope() as session:
                tables = session.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema=:schema AND table_type='BASE TABLE'"
                    )
                    .bindparams(schema=PGSCHEMA)
                ).scalars().all()
                table_set = set(tables or [])
                counts = {}
                tracked_tables = (
                    "stocks",
                    "stock_notes",
                    "stock_groups",
                    "stock_group_members",
                    "stock_tags",
                    "stock_tag_bindings",
                    "limit_up_stocks",
                    "limit_up_analyses",
                )
                for t in tracked_tables:
                    if t in table_set:
                        counts[t] = int(session.execute(text(f"SELECT COUNT(1) FROM {PGSCHEMA}.{t}")).scalar() or 0)

            return APIResponse.success(
                {
                    "engine": info,
                    "schema": PGSCHEMA,
                    "tables": {t: (t in table_set) for t in tracked_tables},
                    "counts": counts,
                }
            )
        except SQLAlchemyError as e:
            return (
                APIResponse.error(
                    message="数据库连接失败",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    details={"error": type(e).__name__},
                    http_status=500,
                ),
                500,
            )

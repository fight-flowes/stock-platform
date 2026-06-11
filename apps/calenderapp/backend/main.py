import os

from app import create_app
from app.utils.logging_config import setup_logging, request_id_middleware


# 初始化日志系统
setup_logging(log_level=os.environ.get("LOG_LEVEL", "INFO"), json_output=False)

app = create_app()

# 添加请求 ID 中间件
app.before_request(request_id_middleware)


if __name__ == "__main__":
    debug_mode = os.environ.get("DEBUG", "True").lower() == "true"
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=debug_mode, threaded=True)

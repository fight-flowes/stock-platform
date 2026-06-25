"""API 认证服务（L2：后端 Token 校验）。

公网部署的安全基线。当前实现是"共享 Token 白名单"——和前端
``VITE_AUTH_TOKEN`` 同源的一组 Token，请求带 ``Authorization: Bearer
<token>``，命中白名单即放行。

设计为可平滑演进到 L3（用户体系）：

* ``validate_token(token)`` 返回 ``user_info`` dict（而不是 bool）。L2
  阶段对所有合法 token 都返回同一个共享身份；L3 阶段把内部实现换成查
  用户表 / 校验 JWT 即可，调用方（中间件）无需改动。
* 中间件通过 ``g.current_user`` 暴露身份，将来接审计日志时可直接取用。

默认关闭（``AUTH_ENABLED=false``），所以本地开发和现有部署零影响。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.settings import AUTH_ENABLED, AUTH_TOKENS


# 不需要认证的路径前缀（健康检查 / 文档 / 静态）。即便开启认证，这些
# 也保持公开——公网探活、Swagger 文档不应被 token 挡住。
_PUBLIC_PATH_PREFIXES = (
    "/health",
    "/api/docs",
    "/swagger",       # flask-restx swagger 静态资源
    "/swaggerui",
)
_PUBLIC_EXACT_PATHS = (
    "/",
)


def auth_enabled() -> bool:
    """认证总开关。关闭时所有请求直接放行（本地 / 现有部署默认行为）。"""
    return bool(AUTH_ENABLED)


def is_public_path(path: str) -> bool:
    """该路径是否豁免认证。"""
    if path in _PUBLIC_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


def extract_bearer_token(authorization_header: Optional[str]) -> str:
    """从 ``Authorization`` 头里取出 bearer token。

    兼容三种写法：``Bearer <token>``、``bearer <token>``、以及直接传裸
    token（容错老客户端）。取不到返回空串。
    """
    raw = (authorization_header or "").strip()
    if not raw:
        return ""
    parts = raw.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    # 容错：直接传了裸 token（无 Bearer 前缀）
    if len(parts) == 1:
        return parts[0].strip()
    return ""


def validate_token(token: str) -> Optional[Dict[str, Any]]:
    """校验 token，合法返回 user_info dict，非法返回 None。

    L2 阶段：命中 ``AUTH_TOKENS`` 白名单即视为合法，返回共享身份。
    L3 阶段：把这里换成查用户表 / 解 JWT，返回真实用户信息——中间件
    和审计逻辑不用改。
    """
    token = (token or "").strip()
    if not token:
        return None
    if token in AUTH_TOKENS:
        return {
            "user_id": "shared",
            "name": "默认用户",
            "auth_method": "shared_token",
        }
    return None

from flask import Response, request, stream_with_context
from flask_restx import Namespace, Resource

from app.services.vibe_trading_proxy_service import (
    VibeTradingProxyError,
    VibeTradingProxyService,
)
from config.api_config import APIConstants, APIResponse

analysis_ns = Namespace("analysis", description="AI 分析对话代理")


@analysis_ns.route("/sessions")
class AnalysisSessionList(Resource):
    def get(self):
        """获取 Vibe-Trading session 列表"""
        try:
            limit = request.args.get("limit", default=50, type=int) or 50
            data = VibeTradingProxyService.list_sessions(limit=limit)
            return APIResponse.success({"items": data})
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except VibeTradingProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@analysis_ns.route("/session")
class AnalysisSession(Resource):
    def post(self):
        """创建一个新的 Vibe-Trading session"""
        try:
            payload = request.get_json(force=True, silent=True) or {}
            title = str(payload.get("title") or "Vibe-Trading").strip() or "Vibe-Trading"
            session = VibeTradingProxyService.create_session(title=title)
            return APIResponse.success(session, message="会话创建成功"), 201
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except VibeTradingProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@analysis_ns.route("/session/<string:session_id>/messages")
class AnalysisMessages(Resource):
    def get(self, session_id: str):
        """获取会话消息历史"""
        try:
            data = VibeTradingProxyService.get_messages(session_id=session_id)
            return APIResponse.success({"items": data})
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except VibeTradingProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )

    def post(self, session_id: str):
        """发送一条用户消息"""
        try:
            payload = request.get_json(force=True, silent=True) or {}
            content = str(payload.get("content") or "").strip()
            if not content:
                raise ValueError("content 不能为空")
            result = VibeTradingProxyService.send_message(
                session_id=session_id,
                content=content,
            )
            return APIResponse.success(
                {
                    "status": "accepted",
                    "session_id": session_id,
                    "upstream": result,
                },
                message="消息已发送",
            )
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except VibeTradingProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@analysis_ns.route("/session/<string:session_id>/cancel")
class AnalysisCancel(Resource):
    def post(self, session_id: str):
        """停止当前生成"""
        try:
            result = VibeTradingProxyService.cancel_session(session_id=session_id)
            return APIResponse.success(result, message="取消请求已发送")
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except VibeTradingProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@analysis_ns.route("/session/<string:session_id>/events")
class AnalysisEvents(Resource):
    def get(self, session_id: str):
        """透传 Vibe-Trading 的 SSE 事件流"""
        try:
            @stream_with_context
            def generate():
                yield from VibeTradingProxyService.stream_events(session_id=session_id)

            return Response(
                generate(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except VibeTradingProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )

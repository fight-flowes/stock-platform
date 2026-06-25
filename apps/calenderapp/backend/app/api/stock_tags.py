from flask import request
from flask_restx import Namespace, Resource

from app.services.stock_tags_service import StockTagsService
from config.api_config import APIConstants, APIResponse


stock_tags_ns = Namespace("stock-tags", description="股票标签")


@stock_tags_ns.route("")
class StockTags(Resource):
    def get(self):
        return APIResponse.success(StockTagsService.list_tags())

    def post(self):
        payload = request.get_json(force=True, silent=True) or {}
        result = StockTagsService.create_tag(
            name=payload.get("name"),
            color=payload.get("color"),
        )
        return APIResponse.success(result, message="创建成功")


@stock_tags_ns.route("/<int:tag_id>")
class StockTagById(Resource):
    def delete(self, tag_id: int):
        result = StockTagsService.delete_tag(tag_id)
        return APIResponse.success(result, message="删除成功")


@stock_tags_ns.route("/<int:tag_id>/bindings")
class StockTagBindings(Resource):
    def post(self, tag_id: int):
        payload = request.get_json(force=True, silent=True) or {}
        stock_codes = payload.get("stock_codes") or []
        if not isinstance(stock_codes, list):
            return (
                APIResponse.error(
                    message="stock_codes 必须为数组",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        result = StockTagsService.add_bindings(tag_id, stock_codes)
        return APIResponse.success(result, message="添加成功")

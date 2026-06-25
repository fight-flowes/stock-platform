from flask import request
from flask_restx import Namespace, Resource

from app.services.stock_groups_service import StockGroupsService
from config.api_config import APIConstants, APIResponse


stock_groups_ns = Namespace("stock-groups", description="股票分组")


@stock_groups_ns.route("")
class StockGroups(Resource):
    def get(self):
        return APIResponse.success(StockGroupsService.list_groups())

    def post(self):
        payload = request.get_json(force=True, silent=True) or {}
        result = StockGroupsService.create_group(
            name=payload.get("name"),
            description=payload.get("description"),
            color=payload.get("color"),
        )
        return APIResponse.success(result, message="创建成功")


@stock_groups_ns.route("/<int:group_id>")
class StockGroupById(Resource):
    def patch(self, group_id: int):
        payload = request.get_json(force=True, silent=True) or {}
        result = StockGroupsService.update_group(group_id, payload)
        return APIResponse.success(result, message="更新成功")

    def delete(self, group_id: int):
        result = StockGroupsService.delete_group(group_id)
        return APIResponse.success(result, message="删除成功")


@stock_groups_ns.route("/<int:group_id>/members")
class StockGroupMembers(Resource):
    def post(self, group_id: int):
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
        result = StockGroupsService.add_members(group_id, stock_codes)
        return APIResponse.success(result, message="添加成功")

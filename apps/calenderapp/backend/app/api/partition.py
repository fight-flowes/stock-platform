"""
分区管理 API

提供分区状态查询、创建、归档等功能
"""
from flask import request
from flask_restx import Namespace, Resource, fields

from app.services.partition_service import PartitionService
from config.api_config import APIConstants, APIResponse

partition_ns = Namespace("partition", description="分区表管理")

partition_model = partition_ns.model(
    "Partition",
    {
        "name": fields.String(description="分区名称"),
        "type": fields.String(description="分区类型"),
        "start_date": fields.String(description="起始日期"),
        "end_date": fields.String(description="结束日期"),
        "size": fields.String(description="分区大小"),
        "live_tuples": fields.Integer(description="数据量"),
    },
)

status_model = partition_ns.model(
    "PartitionStatus",
    {
        "main_table": fields.Nested(partition_ns.model("MainTable", {
            "schema": fields.String(),
            "name": fields.String(),
            "total_size": fields.String(),
            "total_records": fields.Integer(),
        })),
        "partitions": fields.List(fields.Nested(partition_model)),
        "partition_count": fields.Integer(),
    },
)


@partition_ns.route("/status")
class PartitionStatus(Resource):
    def get(self):
        """获取分区状态"""
        status = PartitionService.get_partition_status()
        return APIResponse.success(status)


@partition_ns.route("/create")
class CreatePartition(Resource):
    @partition_ns.param("year", "年份", type=int, required=True)
    @partition_ns.param("month", "月份", type=int, required=True)
    def post(self):
        """创建指定月份分区"""
        args = request.args
        year = args.get("year", type=int)
        month = args.get("month", type=int)

        if not year or not month:
            return (
                APIResponse.error(
                    message="year 和 month 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )

        try:
            result = PartitionService.create_partition(year, month)
            if result["status"] == "created":
                return APIResponse.success(result, message=result["message"]), 201
            return APIResponse.success(result, message=result["message"])
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )


@partition_ns.route("/create-future")
class CreateFuturePartitions(Resource):
    @partition_ns.param("months", "创建月数", type=int, default=3)
    def post(self):
        """批量创建未来分区"""
        args = request.args
        months = args.get("months", type=int, default=3)
        months = min(max(months, 1), 12)  # 限制 1-12

        results = PartitionService.create_future_partitions(months)
        created = [r for r in results if r.get("status") == "created"]
        exists = [r for r in results if r.get("status") == "exists"]

        return APIResponse.success({
            "total": len(results),
            "created": len(created),
            "already_exists": len(exists),
            "details": results,
        })


@partition_ns.route("/next-month")
class CreateNextMonthPartition(Resource):
    def post(self):
        """创建下月分区"""
        result = PartitionService.create_next_month_partition()
        if result["status"] == "created":
            return APIResponse.success(result, message=result["message"]), 201
        return APIResponse.success(result, message=result["message"])


@partition_ns.route("/detach/<partition_name>")
class DetachPartition(Resource):
    def post(self, partition_name: str):
        """分离分区（归档）"""
        if not partition_name.startswith("limit_up_stocks_"):
            return (
                APIResponse.error(
                    message="分区名必须以 limit_up_stocks_ 开头",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )

        result = PartitionService.detach_partition(partition_name)
        if result["status"] == "not_found":
            return (
                APIResponse.error(
                    message=result["message"],
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        return APIResponse.success(result, message=result["message"])


@partition_ns.route("/drop/<partition_name>")
class DropDetachedPartition(Resource):
    def delete(self, partition_name: str):
        """删除已分离的分区表（谨慎操作）"""
        if not partition_name.startswith("limit_up_stocks_"):
            return (
                APIResponse.error(
                    message="分区名必须以 limit_up_stocks_ 开头",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )

        result = PartitionService.drop_detached_partition(partition_name)
        return APIResponse.success(result, message=result["message"])
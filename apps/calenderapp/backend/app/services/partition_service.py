"""
分区表管理服务

功能：
- 自动创建下月分区
- 查询分区状态
- 归档旧分区
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from app.db import engine, session_scope
from app.settings import PGSCHEMA


class PartitionService:
    """分区表管理服务"""

    @staticmethod
    def get_partition_status() -> Dict[str, any]:
        """获取分区状态"""
        with session_scope() as session:
            # 查询所有分区
            result = session.execute(
                text("""
                    SELECT 
                        t.relname as partition_name,
                        pg_size_pretty(pg_total_relation_size(c.oid)) as size,
                        pg_stat_get_tuples_inserted(c.oid) as inserts,
                        pg_stat_get_tuples_deleted(c.oid) as deletes,
                        pg_stat_get_live_tuples(c.oid) as live_tuples
                    FROM pg_class c
                    JOIN pg_inherits i ON c.oid = i.inhrelid
                    JOIN pg_class t ON c.oid = t.oid
                    JOIN pg_namespace n ON c.relnamespace = n.oid
                    WHERE n.nspname = :schema
                    AND t.relname LIKE 'limit_up_stocks_%'
                    ORDER BY t.relname
                """),
                {"schema": PGSCHEMA}
            ).fetchall()

            partitions = []
            for row in result:
                # 从分区名解析日期范围
                name = row[0]
                if name == "limit_up_stocks_default":
                    partitions.append({
                        "name": name,
                        "type": "default",
                        "size": row[1],
                        "inserts": row[2],
                        "deletes": row[3],
                        "live_tuples": row[4]
                    })
                else:
                    # 解析 YYYYMM 格式
                    try:
                        year_month = name.replace("limit_up_stocks_", "")
                        year = int(year_month[:4])
                        month = int(year_month[4:6])
                        start_date = date(year, month, 1)
                        if month == 12:
                            end_date = date(year + 1, 1, 1)
                        else:
                            end_date = date(year, month + 1, 1)
                        
                        partitions.append({
                            "name": name,
                            "type": "monthly",
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "size": row[1],
                            "inserts": row[2],
                            "deletes": row[3],
                            "live_tuples": row[4]
                        })
                    except Exception:
                        partitions.append({
                            "name": name,
                            "type": "unknown",
                            "size": row[1]
                        })

            # 主表信息
            main_info = session.execute(
                text("""
                    SELECT 
                        pg_size_pretty(pg_total_relation_size(:table_oid)) as total_size,
                        (SELECT COUNT(*) FROM sc.limit_up_stocks) as total_records
                """),
                {"table_oid": f"{PGSCHEMA}.limit_up_stocks"}
            ).first()

            return {
                "main_table": {
                    "schema": PGSCHEMA,
                    "name": "limit_up_stocks",
                    "total_size": main_info[0] if main_info else "N/A",
                    "total_records": main_info[1] if main_info else 0
                },
                "partitions": partitions,
                "partition_count": len(partitions)
            }

    @staticmethod
    def create_partition(year: int, month: int) -> Dict[str, str]:
        """创建指定月份的分区
        
        Args:
            year: 年份
            month: 月份 (1-12)
        
        Returns:
            创建结果
        """
        if month < 1 or month > 12:
            raise ValueError("月份必须在 1-12 之间")

        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        partition_name = f"limit_up_stocks_{year}{month:02d}"

        with session_scope() as session:
            # 检查分区是否已存在
            exists = session.execute(
                text("""
                    SELECT 1 FROM pg_tables 
                    WHERE schemaname = :schema AND tablename = :name
                """),
                {"schema": PGSCHEMA, "name": partition_name}
            ).first()

            if exists:
                return {"status": "exists", "message": f"分区 {partition_name} 已存在"}

            # 创建分区
            session.execute(
                text(f"""
                    CREATE TABLE {PGSCHEMA}.{partition_name}
                    PARTITION OF {PGSCHEMA}.limit_up_stocks
                    FOR VALUES FROM ('{start_date.isoformat()}') TO ('{end_date.isoformat()}')
                """)
            )
            session.commit()

            return {
                "status": "created",
                "message": f"分区 {partition_name} 创建成功",
                "partition_name": partition_name,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }

    @staticmethod
    def ensure_partition_exists(target_date: date) -> bool:
        """确保目标日期的分区存在
        
        Args:
            target_date: 目标日期
        
        Returns:
            分区是否存在或已创建
        """
        year = target_date.year
        month = target_date.month

        try:
            result = PartitionService.create_partition(year, month)
            return result["status"] in ["exists", "created"]
        except Exception as e:
            print(f"创建分区失败: {e}")
            return False

    @staticmethod
    def create_next_month_partition() -> Dict[str, str]:
        """创建下月分区（定时任务使用）"""
        today = date.today()
        next_month = today.month + 1 if today.month < 12 else 1
        next_year = today.year if today.month < 12 else today.year + 1

        return PartitionService.create_partition(next_year, next_month)

    @staticmethod
    def create_future_partitions(months: int = 3) -> List[Dict[str, str]]:
        """批量创建未来几个月的分区
        
        Args:
            months: 创建几个月的分区
        
        Returns:
            创建结果列表
        """
        results = []
        today = date.today()

        for i in range(months):
            future_date = today + timedelta(days=i * 30)
            year = future_date.year
            month = future_date.month

            try:
                result = PartitionService.create_partition(year, month)
                results.append(result)
            except Exception as e:
                results.append({
                    "status": "error",
                    "message": f"创建 {year}-{month:02d} 分区失败: {str(e)}"
                })

        return results

    @staticmethod
    def detach_partition(partition_name: str) -> Dict[str, str]:
        """分离（归档）分区
        
        分离后的分区变为普通表，可以导出或删除
        
        Args:
            partition_name: 分区名（如 limit_up_stocks_202508）
        
        Returns:
            操作结果
        """
        with session_scope() as session:
            # 检查分区是否存在
            exists = session.execute(
                text("""
                    SELECT 1 FROM pg_tables 
                    WHERE schemaname = :schema AND tablename = :name
                """),
                {"schema": PGSCHEMA, "name": partition_name}
            ).first()

            if not exists:
                return {"status": "not_found", "message": f"分区 {partition_name} 不存在"}

            # 分离分区
            session.execute(
                text(f"""
                    ALTER TABLE {PGSCHEMA}.limit_up_stocks
                    DETACH PARTITION {PGSCHEMA}.{partition_name}
                """)
            )
            session.commit()

            return {
                "status": "detached",
                "message": f"分区 {partition_name} 已分离，现在是独立表",
                "table_name": f"{PGSCHEMA}.{partition_name}"
            }

    @staticmethod
    def drop_detached_partition(partition_name: str) -> Dict[str, str]:
        """删除已分离的分区表
        
        Args:
            partition_name: 分区名
        
        Returns:
            操作结果
        """
        with session_scope() as session:
            session.execute(
                text(f"DROP TABLE IF EXISTS {PGSCHEMA}.{partition_name}")
            )
            session.commit()

            return {
                "status": "deleted",
                "message": f"分区表 {partition_name} 已删除"
            }

    @staticmethod
    def get_partition_data_count(partition_name: str) -> int:
        """获取指定分区的数据量"""
        with session_scope() as session:
            result = session.execute(
                text(f"SELECT COUNT(*) FROM {PGSCHEMA}.{partition_name}")
            ).scalar()
            return result or 0


# 定时任务：每月初自动创建下月分区
def auto_create_partition_job():
    """定时任务入口函数"""
    result = PartitionService.create_next_month_partition()
    print(f"[Partition Job] {result['message']}")
    return result
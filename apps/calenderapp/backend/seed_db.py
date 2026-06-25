import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import session_scope
from app.models import Stock


def seed():
    with session_scope() as session:
        stock_items = [
            ("600519", "贵州茅台", "SH"),
            ("000001", "平安银行", "SZ"),
            ("000333", "美的集团", "SZ"),
            ("601318", "中国平安", "SH"),
        ]
        for code, name, exchange in stock_items:
            existing = session.query(Stock).filter(Stock.code == code).first()
            if existing:
                existing.name = name
                existing.exchange = exchange
            else:
                session.add(Stock(code=code, name=name, exchange=exchange))


if __name__ == "__main__":
    seed()

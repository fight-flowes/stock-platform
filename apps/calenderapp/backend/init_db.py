import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import Base, engine, ensure_schema
from app.models import CalendarDay, CalendarEvent, Stock


def init_database():
    ensure_schema()
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_database()

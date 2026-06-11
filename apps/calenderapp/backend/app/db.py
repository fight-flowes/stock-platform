import os
from contextlib import contextmanager
from getpass import getuser

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

# Schema 名称
PGSCHEMA = os.environ.get("PGSCHEMA", "sc")


def _build_engine():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return create_engine(database_url, pool_pre_ping=True)

    username = os.environ.get("PGUSER") or getuser()
    password = os.environ.get("PGPASSWORD")
    host = os.environ.get("PGHOST")
    port = os.environ.get("PGPORT")
    database = os.environ.get("PGDATABASE", "calenderdb")
    schema = os.environ.get("PGSCHEMA", "sc")

    port_value = int(port) if port else None

    url = URL.create(
        "postgresql+psycopg2",
        username=username,
        password=password or None,
        host=host or None,
        port=port_value,
        database=database,
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": f"-c search_path={schema},public"},
    )


def ensure_schema(schema: str = "sc"):
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

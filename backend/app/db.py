"""MySQL connection helper. Agents: use get_conn() with parameterized queries only."""
import os
from contextlib import contextmanager
from urllib.parse import unquote, urlparse

import pymysql


def _params() -> dict:
    url = urlparse(os.environ.get("DATABASE_URL", "mysql://app:app@localhost:3306/app"))
    return {
        "host": url.hostname or "localhost",
        "port": url.port or 3306,
        "user": unquote(url.username or ""),
        "password": unquote(url.password or ""),
        "database": url.path.lstrip("/"),
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }


@contextmanager
def get_conn():
    conn = pymysql.connect(**_params())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

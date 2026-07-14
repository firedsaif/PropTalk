"""Database access. Reads DATABASE_URL from the repo-root .env (gitignored).
Use your Supabase connection string - the Session pooler URI works well from anywhere.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

# app/db.py -> app -> backend -> repo root, where .env lives.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_pool: ConnectionPool | None = None


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add your Supabase connection string to the repo-root .env"
        )
    return url


def get_connection() -> psycopg.Connection:
    """One-off connection - used by scripts (apply_sql.py, test_search.py)."""
    return psycopg.connect(_database_url(), connect_timeout=10)


def get_pooled_connection():
    """Borrow a connection from the shared pool - same `with ... as conn:` interface
    as get_connection(), but reused across requests so a tool call doesn't pay a
    fresh TCP+TLS+auth round trip to Supabase every time (rules.md SS1: tools < 800ms).
    Used by API request handlers (routes/tools.py, routes/webhooks.py); route handlers
    are plain `def` functions FastAPI runs in its worker threadpool, so this blocking
    call never blocks the event loop.
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool(_database_url(), min_size=1, max_size=5, kwargs={"connect_timeout": 10})
    return _pool.connection()

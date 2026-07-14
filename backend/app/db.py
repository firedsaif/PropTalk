"""Database access. One connection helper for scripts and (Phase 2) the API.

Reads DATABASE_URL from the repo-root .env (gitignored). Use your Supabase
connection string - the Session pooler URI works well from anywhere.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# app/db.py -> app -> backend -> repo root, where .env lives.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def get_connection() -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add your Supabase connection string to the repo-root .env"
        )
    return psycopg.connect(url, connect_timeout=10)

"""Apply schema.sql then seed_willowbrook.sql to the database in DATABASE_URL.

Run from the backend/ folder:  python scripts/apply_sql.py
(Or paste the two .sql files straight into the Supabase SQL editor.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # put backend/ on sys.path
from app.db import get_connection  # noqa: E402

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def split_statements(sql: str) -> list[str]:
    """Split a .sql file into statements on top-level ';'.

    A ';' is only a separator outside single-quoted strings *and* outside '--' comments -
    the schema documents itself heavily, and a semicolon in prose ("null = degraded; add
    manually") would otherwise silently cut a CREATE TABLE in half.
    """
    stmts: list[str] = []
    buf: list[str] = []
    in_str = False
    in_comment = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if in_comment:
            buf.append(ch)
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if not in_str and ch == "-" and sql[i : i + 2] == "--":
            in_comment = True
            buf.append(ch)
            i += 1
            continue
        if ch == "'":
            in_str = not in_str
        if ch == ";" and not in_str:
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def run_file(conn, path: Path) -> None:
    statements = split_statements(path.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()
    print(f"  applied {path.name}  ({len(statements)} statements)")


def main() -> None:
    print("Applying SQL to the database in DATABASE_URL...")
    with get_connection() as conn:
        run_file(conn, SQL_DIR / "schema.sql")
        run_file(conn, SQL_DIR / "seed_willowbrook.sql")
        with conn.cursor() as cur:
            cur.execute("select count(*) from clients")
            clients = cur.fetchone()[0]
            cur.execute("select count(*) from properties")
            props = cur.fetchone()[0]
            cur.execute("select count(*) from properties where status = 'available'")
            avail = cur.fetchone()[0]
    print(f"Done.  clients={clients}  properties={props}  available={avail}")


if __name__ == "__main__":
    main()

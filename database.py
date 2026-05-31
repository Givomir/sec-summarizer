import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DATABASE_PATH", "sec_summaries.db")


def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS filing_summaries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_url    TEXT    NOT NULL,
                company_name  TEXT,
                filing_type   TEXT,
                section_extracted TEXT,
                summary       TEXT,
                status        TEXT    NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at    TEXT
            )
        """)
        conn.commit()


@contextmanager
def get_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

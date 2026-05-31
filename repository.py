import sqlite3
from typing import Optional
from database import get_db, DB_PATH


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row else None


class SummaryRepository:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def create(self, filing_url: str) -> dict:
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO filing_summaries (filing_url, status) VALUES (?, 'pending')",
                (filing_url,),
            )
            row = conn.execute(
                "SELECT * FROM filing_summaries WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return _row_to_dict(row)

    def get_by_id(self, summary_id: int) -> Optional[dict]:
        with get_db(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM filing_summaries WHERE id = ?", (summary_id,)
            ).fetchone()
            return _row_to_dict(row)

    def list_all(self, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        offset = (page - 1) * page_size
        with get_db(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM filing_summaries").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM filing_summaries ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            ).fetchall()
            return [_row_to_dict(r) for r in rows], total

    def update_processing(self, summary_id: int) -> Optional[dict]:
        with get_db(self.db_path) as conn:
            conn.execute(
                "UPDATE filing_summaries SET status='processing', updated_at=datetime('now') WHERE id=?",
                (summary_id,),
            )
            return _row_to_dict(conn.execute(
                "SELECT * FROM filing_summaries WHERE id=?", (summary_id,)
            ).fetchone())

    def update_completed(self, summary_id: int, company_name, filing_type,
                         section_extracted, summary_text) -> Optional[dict]:
        with get_db(self.db_path) as conn:
            conn.execute(
                """UPDATE filing_summaries
                   SET status='completed', company_name=?, filing_type=?,
                       section_extracted=?, summary=?, updated_at=datetime('now')
                   WHERE id=?""",
                (company_name, filing_type, section_extracted, summary_text, summary_id),
            )
            return _row_to_dict(conn.execute(
                "SELECT * FROM filing_summaries WHERE id=?", (summary_id,)
            ).fetchone())

    def update_failed(self, summary_id: int, error: str) -> Optional[dict]:
        with get_db(self.db_path) as conn:
            conn.execute(
                "UPDATE filing_summaries SET status='failed', error_message=?, updated_at=datetime('now') WHERE id=?",
                (error, summary_id),
            )
            return _row_to_dict(conn.execute(
                "SELECT * FROM filing_summaries WHERE id=?", (summary_id,)
            ).fetchone())

from datetime import date, datetime
from typing import Any

import psycopg
from psycopg import errors

from positives.types import Entry, ReminderSettings, User


class PostgresRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url)

    def init_db(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS users (
          id bigserial PRIMARY KEY,
          email varchar(320) NOT NULL UNIQUE,
          password_hash text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS daily_positives_user (
          user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          entry_date date NOT NULL,
          positive_1 varchar(200) NOT NULL,
          positive_2 varchar(200) NOT NULL,
          positive_3 varchar(200) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, entry_date)
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
          user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
          reminder_enabled boolean NOT NULL DEFAULT false,
          reminder_time char(5) NOT NULL DEFAULT '20:00',
          updated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_daily_positives_user_date
        ON daily_positives_user (user_id, entry_date DESC);
        """

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

    def health_check(self) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def create_user(self, email: str, password_hash: str) -> User | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO users (email, password_hash)
                        VALUES (%s, %s)
                        RETURNING id, email, created_at
                        """,
                        (email, password_hash),
                    )
                except errors.UniqueViolation:
                    return None

                row = cur.fetchone()

        return self._row_to_user(row)

    def get_user_by_email(self, email: str) -> tuple[User, str] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, created_at, password_hash
                    FROM users
                    WHERE email = %s
                    """,
                    (email,),
                )
                row = cur.fetchone()

        if row is None:
            return None

        user = self._row_to_user((row[0], row[1], row[2]))
        password_hash = str(row[3])
        return user, password_hash

    def get_user_by_id(self, user_id: int) -> User | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, created_at
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return self._row_to_user(row)

    def list_entries(
        self, user_id: int, query_text: str, limit: int, offset: int
    ) -> tuple[list[Entry], bool, int | None]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      entry_date,
                      positive_1,
                      positive_2,
                      positive_3,
                      updated_at
                    FROM daily_positives_user
                    WHERE user_id = %s
                      AND (
                        %s = ''
                        OR concat_ws(
                          ' ',
                          positive_1,
                          positive_2,
                          positive_3,
                          entry_date::text
                        ) ILIKE '%%' || %s || '%%'
                      )
                    ORDER BY entry_date DESC
                    LIMIT %s
                    OFFSET %s
                    """,
                    (user_id, query_text, query_text, limit + 1, offset),
                )
                rows = cur.fetchall()

        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        next_offset = offset + len(visible_rows) if has_more else None

        return [self._row_to_entry(row) for row in visible_rows], has_more, next_offset

    def get_entry(self, user_id: int, date_value: str) -> Entry | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      entry_date,
                      positive_1,
                      positive_2,
                      positive_3,
                      updated_at
                    FROM daily_positives_user
                    WHERE user_id = %s
                      AND entry_date = %s
                    """,
                    (user_id, date_value),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return self._row_to_entry(row)

    def upsert_entry(self, user_id: int, date_value: str, items: list[str]) -> Entry:
        item1, item2, item3 = items

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO daily_positives_user (
                      user_id,
                      entry_date,
                      positive_1,
                      positive_2,
                      positive_3
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, entry_date)
                    DO UPDATE SET
                      positive_1 = EXCLUDED.positive_1,
                      positive_2 = EXCLUDED.positive_2,
                      positive_3 = EXCLUDED.positive_3,
                      updated_at = now()
                    RETURNING
                      entry_date,
                      positive_1,
                      positive_2,
                      positive_3,
                      updated_at
                    """,
                    (user_id, date_value, item1, item2, item3),
                )
                row = cur.fetchone()

        return self._row_to_entry(row)

    def delete_entry(self, user_id: int, date_value: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM daily_positives_user
                    WHERE user_id = %s AND entry_date = %s
                    """,
                    (user_id, date_value),
                )
                return cur.rowcount > 0

    def list_completed_dates_for_month(self, user_id: int, month_value: str) -> list[str]:
        month_start = date.fromisoformat(f"{month_value}-01")
        if month_start.month == 12:
            month_end = date(month_start.year + 1, 1, 1)
        else:
            month_end = date(month_start.year, month_start.month + 1, 1)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT entry_date::text
                    FROM daily_positives_user
                    WHERE user_id = %s
                      AND entry_date >= %s
                      AND entry_date < %s
                    ORDER BY entry_date ASC
                    """,
                    (user_id, month_start, month_end),
                )
                rows = cur.fetchall()

        return [str(row[0]) for row in rows]

    def get_reminder_settings(self, user_id: int) -> ReminderSettings:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT reminder_enabled, reminder_time
                    FROM user_preferences
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()

        if row is None:
            return {"enabled": False, "time": "20:00"}

        return {
            "enabled": bool(row[0]),
            "time": str(row[1]),
        }

    def upsert_reminder_settings(
        self, user_id: int, enabled: bool, reminder_time: str
    ) -> ReminderSettings:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_preferences (user_id, reminder_enabled, reminder_time)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                      reminder_enabled = EXCLUDED.reminder_enabled,
                      reminder_time = EXCLUDED.reminder_time,
                      updated_at = now()
                    RETURNING reminder_enabled, reminder_time
                    """,
                    (user_id, enabled, reminder_time),
                )
                row = cur.fetchone()

        return {
            "enabled": bool(row[0]),
            "time": str(row[1]),
        }

    @staticmethod
    def _row_to_entry(row: tuple[Any, Any, Any, Any, Any]) -> Entry:
        entry_date, positive_1, positive_2, positive_3, updated_at = row

        if isinstance(updated_at, datetime):
            updated_at_value = updated_at.isoformat()
        else:
            updated_at_value = str(updated_at)

        return {
            "date": str(entry_date),
            "items": [str(positive_1), str(positive_2), str(positive_3)],
            "updatedAt": updated_at_value,
        }

    @staticmethod
    def _row_to_user(row: tuple[Any, Any, Any]) -> User:
        user_id, email, created_at = row

        if isinstance(created_at, datetime):
            created_at_value = created_at.isoformat()
        else:
            created_at_value = str(created_at)

        return {
            "id": int(user_id),
            "email": str(email),
            "createdAt": created_at_value,
        }

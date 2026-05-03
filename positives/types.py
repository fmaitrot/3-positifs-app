from typing import Protocol, TypedDict


class Entry(TypedDict):
    date: str
    items: list[str]
    updatedAt: str


class User(TypedDict):
    id: int
    email: str
    createdAt: str


class ReminderSettings(TypedDict):
    enabled: bool
    time: str


class Repository(Protocol):
    def init_db(self) -> None: ...

    def health_check(self) -> bool: ...

    def create_user(self, email: str, password_hash: str) -> User | None: ...

    def get_user_by_email(self, email: str) -> tuple[User, str] | None: ...

    def get_user_by_id(self, user_id: int) -> User | None: ...

    def list_entries(
        self, user_id: int, query_text: str, limit: int, offset: int
    ) -> tuple[list[Entry], bool, int | None]: ...

    def get_entry(self, user_id: int, date_value: str) -> Entry | None: ...

    def upsert_entry(self, user_id: int, date_value: str, items: list[str]) -> Entry: ...

    def delete_entry(self, user_id: int, date_value: str) -> bool: ...

    def list_completed_dates_for_month(self, user_id: int, month_value: str) -> list[str]: ...

    def get_reminder_settings(self, user_id: int) -> ReminderSettings: ...

    def upsert_reminder_settings(
        self, user_id: int, enabled: bool, reminder_time: str
    ) -> ReminderSettings: ...

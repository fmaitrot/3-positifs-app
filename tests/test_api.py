from datetime import date, timedelta
from typing import Any

import pytest

from positives.app_factory import create_app
from positives.types import Entry, ReminderSettings, User


class FakeRepository:
    def __init__(self) -> None:
        self.entries_by_user: dict[int, dict[str, Entry]] = {}
        self.users_by_id: dict[int, User] = {}
        self.user_password_hash_by_id: dict[int, str] = {}
        self.user_id_by_email: dict[str, int] = {}
        self.reminders_by_user: dict[int, ReminderSettings] = {}
        self._next_user_id = 1
        self._revision = 0

    def init_db(self) -> None:
        return None

    def health_check(self) -> bool:
        return True

    def create_user(self, email: str, password_hash: str) -> User | None:
        if email in self.user_id_by_email:
            return None

        user_id = self._next_user_id
        self._next_user_id += 1

        user: User = {
            "id": user_id,
            "email": email,
            "createdAt": "2026-05-02T00:00:00+00:00",
        }

        self.users_by_id[user_id] = user
        self.user_password_hash_by_id[user_id] = password_hash
        self.user_id_by_email[email] = user_id
        self.entries_by_user.setdefault(user_id, {})
        return user

    def get_user_by_email(self, email: str) -> tuple[User, str] | None:
        user_id = self.user_id_by_email.get(email)
        if user_id is None:
            return None

        user = self.users_by_id[user_id]
        password_hash = self.user_password_hash_by_id[user_id]
        return user, password_hash

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.users_by_id.get(user_id)

    def list_entries(
        self, user_id: int, query_text: str, limit: int, offset: int
    ) -> tuple[list[Entry], bool, int | None]:
        lowered = query_text.lower()
        user_entries = self.entries_by_user.get(user_id, {})
        all_entries = [user_entries[key] for key in sorted(user_entries.keys(), reverse=True)]

        if lowered:
            all_entries = [
                entry
                for entry in all_entries
                if lowered in f"{entry['date']} {' '.join(entry['items'])}".lower()
            ]

        visible = all_entries[offset : offset + limit]
        has_more = offset + limit < len(all_entries)
        next_offset = offset + len(visible) if has_more else None
        return visible, has_more, next_offset

    def get_entry(self, user_id: int, date_value: str) -> Entry | None:
        return self.entries_by_user.get(user_id, {}).get(date_value)

    def upsert_entry(self, user_id: int, date_value: str, items: list[str]) -> Entry:
        self._revision += 1
        entry: Entry = {
            "date": date_value,
            "items": items,
            "updatedAt": f"2026-05-02T00:00:{self._revision:02d}+00:00",
        }
        self.entries_by_user.setdefault(user_id, {})[date_value] = entry
        return entry

    def delete_entry(self, user_id: int, date_value: str) -> bool:
        user_entries = self.entries_by_user.setdefault(user_id, {})
        if date_value not in user_entries:
            return False

        del user_entries[date_value]
        return True

    def list_completed_dates_for_month(self, user_id: int, month_value: str) -> list[str]:
        entries = self.entries_by_user.get(user_id, {})
        return sorted(
            [entry_date for entry_date in entries if entry_date.startswith(f"{month_value}-")]
        )

    def get_reminder_settings(self, user_id: int) -> ReminderSettings:
        return self.reminders_by_user.get(user_id, {"enabled": False, "time": "20:00"})

    def upsert_reminder_settings(
        self, user_id: int, enabled: bool, reminder_time: str
    ) -> ReminderSettings:
        settings: ReminderSettings = {
            "enabled": enabled,
            "time": reminder_time,
        }
        self.reminders_by_user[user_id] = settings
        return settings


class UnhealthyRepository(FakeRepository):
    def health_check(self) -> bool:
        return False


def seed_repository(repo: FakeRepository, user_id: int, days: int = 25) -> None:
    start = date(2026, 4, 30)
    for index in range(days):
        current = (start - timedelta(days=index)).isoformat()
        repo.upsert_entry(
            user_id,
            current,
            [
                f"Positive A {index}",
                f"Positive B {index}",
                f"Positive C {index}",
            ],
        )


def register_user(
    client: Any, email: str = "test@example.com", password: str = "password123"
) -> User:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.get_json()["user"]


@pytest.fixture()
def app_with_repo() -> tuple[Any, FakeRepository]:
    repo = FakeRepository()
    app = create_app(repo, secret_key="test-secret")
    app.config["TESTING"] = True
    return app, repo


@pytest.fixture()
def client(app_with_repo: tuple[Any, FakeRepository]) -> Any:
    app, _repo = app_with_repo
    return app.test_client()


def test_health_endpoint(client: Any) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_health_endpoint_returns_503_when_unhealthy() -> None:
    app = create_app(UnhealthyRepository(), secret_key="test-secret")
    app.config["TESTING"] = True
    test_client = app.test_client()

    response = test_client.get("/api/health")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False}


def test_root_serves_index_html(client: Any) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert b"<!doctype html>" in response.data.lower()


def test_entries_require_authentication(client: Any) -> None:
    response = client.get("/api/entries")
    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication required"}


def test_auth_register_me_and_logout_flow(client: Any) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={"email": "flow@example.com", "password": "password123"},
    )
    assert register_response.status_code == 201

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.get_json()["user"]["email"] == "flow@example.com"

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 204

    me_after_logout_response = client.get("/api/auth/me")
    assert me_after_logout_response.status_code == 401


def test_register_rejects_duplicate_email(client: Any) -> None:
    first_response = client.post(
        "/api/auth/register",
        json={"email": "duplicate@example.com", "password": "password123"},
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/auth/register",
        json={"email": "duplicate@example.com", "password": "password123"},
    )
    assert second_response.status_code == 409
    assert second_response.get_json() == {"error": "email already exists"}


def test_login_rejects_invalid_credentials(client: Any) -> None:
    register_user(client, email="login@example.com")
    client.post("/api/auth/logout")

    response = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}


def test_list_entries_uses_progressive_pagination(
    client: Any, app_with_repo: tuple[Any, FakeRepository]
) -> None:
    _app, repo = app_with_repo
    user = register_user(client)
    seed_repository(repo, user_id=user["id"])

    response = client.get("/api/entries")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload["entries"]) == 20
    assert payload["hasMore"] is True
    assert payload["nextOffset"] == 20


def test_list_entries_with_offset_returns_last_page(
    client: Any, app_with_repo: tuple[Any, FakeRepository]
) -> None:
    _app, repo = app_with_repo
    user = register_user(client)
    seed_repository(repo, user_id=user["id"])

    response = client.get("/api/entries?limit=20&offset=20")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload["entries"]) == 5
    assert payload["hasMore"] is False
    assert payload["nextOffset"] is None


def test_list_entries_supports_search(
    client: Any, app_with_repo: tuple[Any, FakeRepository]
) -> None:
    _app, repo = app_with_repo
    user = register_user(client)
    seed_repository(repo, user_id=user["id"])

    response = client.get("/api/entries?q=Positive%20A%201")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload["entries"]) >= 1
    assert all("Positive A 1" in item["items"][0] for item in payload["entries"])


def test_get_entry_rejects_invalid_date(client: Any) -> None:
    register_user(client)

    response = client.get("/api/entries/30-04-2026")
    assert response.status_code == 422
    assert response.get_json() == {"error": "invalid date format"}


def test_put_entry_and_get_entry_round_trip(client: Any) -> None:
    register_user(client)

    response = client.put(
        "/api/entries/2026-05-02",
        json={"items": ["Un", "Deux", "Trois"]},
    )

    assert response.status_code == 200
    assert response.get_json()["entry"]["items"] == ["Un", "Deux", "Trois"]

    get_response = client.get("/api/entries/2026-05-02")
    assert get_response.status_code == 200
    assert get_response.get_json()["entry"]["items"] == ["Un", "Deux", "Trois"]


def test_put_entry_rejects_invalid_payload(client: Any) -> None:
    register_user(client)

    response = client.put("/api/entries/2026-05-02", json={"items": ["a", "b"]})
    assert response.status_code == 422
    assert response.get_json() == {"error": "items must be an array of 3 values"}


def test_put_entry_rejects_future_date(client: Any) -> None:
    register_user(client)

    response = client.put("/api/entries/2099-01-01", json={"items": ["a", "b", "c"]})
    assert response.status_code == 422
    assert response.get_json() == {"error": "future dates are not allowed"}


def test_put_entry_rejects_missing_json_content_type(client: Any) -> None:
    register_user(client)

    response = client.put("/api/entries/2026-05-02", data="{}")
    assert response.status_code == 415
    assert response.get_json() == {"error": "content type must be application/json"}


def test_put_entry_rejects_invalid_json_payload(client: Any) -> None:
    register_user(client)

    response = client.put(
        "/api/entries/2026-05-02",
        data="{invalid",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid json payload"}


def test_delete_entry_returns_404_when_missing(client: Any) -> None:
    register_user(client)

    response = client.delete("/api/entries/2020-01-01")
    assert response.status_code == 404
    assert response.get_json() == {"error": "entry not found"}


def test_delete_entry_success(client: Any) -> None:
    register_user(client)

    put_response = client.put(
        "/api/entries/2026-05-01",
        json={"items": ["A", "B", "C"]},
    )
    assert put_response.status_code == 200

    delete_response = client.delete("/api/entries/2026-05-01")
    assert delete_response.status_code == 204

    get_response = client.get("/api/entries/2026-05-01")
    assert get_response.status_code == 404


def test_calendar_endpoint_returns_completed_dates(
    client: Any, app_with_repo: tuple[Any, FakeRepository]
) -> None:
    _app, repo = app_with_repo
    user = register_user(client)
    seed_repository(repo, user_id=user["id"], days=10)

    response = client.get("/api/calendar?month=2026-04")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["month"] == "2026-04"
    assert len(payload["completedDates"]) == 10


def test_reminder_endpoints(client: Any) -> None:
    register_user(client)

    get_default_response = client.get("/api/reminder")
    assert get_default_response.status_code == 200
    assert get_default_response.get_json() == {
        "settings": {"enabled": False, "time": "20:00"}
    }

    upsert_response = client.put(
        "/api/reminder",
        json={"enabled": True, "time": "21:15"},
    )
    assert upsert_response.status_code == 200
    assert upsert_response.get_json() == {
        "settings": {"enabled": True, "time": "21:15"}
    }


def test_api_sets_cors_headers(client: Any) -> None:
    response = client.get("/api/health")
    assert response.headers["Access-Control-Allow-Origin"] == "*"


def test_api_options_preflight(client: Any) -> None:
    response = client.options("/api/entries/2026-04-30")
    assert response.status_code in (200, 204)
    assert response.headers["Access-Control-Allow-Methods"] == "GET, PUT, DELETE, POST, OPTIONS"


def test_delete_rejects_invalid_date_format(client: Any) -> None:
    register_user(client)

    response = client.delete("/api/entries/30-04-2026")
    assert response.status_code == 422
    assert response.get_json() == {"error": "invalid date format"}

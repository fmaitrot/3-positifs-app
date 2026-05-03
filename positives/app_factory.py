import os
from datetime import date
from typing import Any

from flask import Flask, current_app, jsonify, request, send_from_directory, session
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash, generate_password_hash

from positives.types import Repository, User
from positives.validation import (
    is_not_future_iso_date,
    is_valid_iso_date,
    normalize_email,
    parse_bounded_int,
    validate_email,
    validate_items,
    validate_month,
    validate_password,
    validate_reminder_time,
)

REPOSITORY_KEY = "POSITIVES_REPOSITORY"
SESSION_USER_ID_KEY = "user_id"
HTTP_UNPROCESSABLE_ENTITY = 422


def create_app(repository: Repository, secret_key: str = "dev-secret-change-me") -> Flask:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    public_dir = os.path.join(project_root, "public")
    app = Flask(__name__, static_folder=public_dir, static_url_path="")
    app.config[REPOSITORY_KEY] = repository
    app.config["SECRET_KEY"] = secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    @app.after_request
    def add_api_cors_headers(response: Any) -> Any:
        if request.path.startswith("/api"):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, PUT, DELETE, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.route("/api", methods=["OPTIONS"])
    @app.route("/api/<path:_path>", methods=["OPTIONS"])
    def api_options(_path: str = "") -> Any:
        return "", 204

    @app.get("/api/health")
    def health() -> Any:
        repo = _get_repository()
        is_healthy = repo.health_check()
        status_code = 200 if is_healthy else 503
        return jsonify({"ok": is_healthy}), status_code

    @app.post("/api/auth/register")
    def register() -> Any:
        payload, error_response = _require_json_object()
        if error_response is not None:
            return error_response

        is_valid, email_or_message = validate_email(payload.get("email"))
        if not is_valid:
            return jsonify({"error": email_or_message}), HTTP_UNPROCESSABLE_ENTITY

        is_valid_password, password_or_message = validate_password(payload.get("password"))
        if not is_valid_password:
            return jsonify({"error": password_or_message}), HTTP_UNPROCESSABLE_ENTITY

        email = normalize_email(email_or_message)
        password_hash = generate_password_hash(password_or_message)

        repo = _get_repository()

        try:
            user = repo.create_user(email, password_hash)
        except Exception:
            return jsonify({"error": "failed to create user"}), 500

        if user is None:
            return jsonify({"error": "email already exists"}), 409

        session[SESSION_USER_ID_KEY] = user["id"]
        return jsonify({"user": user}), 201

    @app.post("/api/auth/login")
    def login() -> Any:
        payload, error_response = _require_json_object()
        if error_response is not None:
            return error_response

        is_valid, email_or_message = validate_email(payload.get("email"))
        if not is_valid:
            return jsonify({"error": email_or_message}), HTTP_UNPROCESSABLE_ENTITY

        password = str(payload.get("password") or "")
        if not password:
            return jsonify({"error": "password is required"}), HTTP_UNPROCESSABLE_ENTITY

        email = normalize_email(email_or_message)

        repo = _get_repository()
        try:
            result = repo.get_user_by_email(email)
        except Exception:
            return jsonify({"error": "failed to authenticate"}), 500

        if result is None:
            return jsonify({"error": "invalid credentials"}), 401

        user, password_hash = result
        if not check_password_hash(password_hash, password):
            return jsonify({"error": "invalid credentials"}), 401

        session[SESSION_USER_ID_KEY] = user["id"]
        return jsonify({"user": user}), 200

    @app.post("/api/auth/logout")
    def logout() -> Any:
        session.pop(SESSION_USER_ID_KEY, None)
        return "", 204

    @app.get("/api/auth/me")
    def me() -> Any:
        user, unauthorized_response = _require_authenticated_user()
        if unauthorized_response is not None:
            return unauthorized_response

        return jsonify({"user": user})

    @app.get("/api/entries")
    def list_entries() -> Any:
        user, unauthorized_response = _require_authenticated_user()
        if unauthorized_response is not None:
            return unauthorized_response

        repo = _get_repository()
        query_text = str(request.args.get("q", "")).strip()
        limit = parse_bounded_int(request.args.get("limit"), default=20, min_value=1, max_value=100)
        offset = parse_bounded_int(
            request.args.get("offset"), default=0, min_value=0, max_value=1_000_000
        )

        try:
            entries, has_more, next_offset = repo.list_entries(
                user["id"], query_text, limit, offset
            )
        except Exception:
            return jsonify({"error": "failed to list entries"}), 500

        return jsonify(
            {
                "entries": entries,
                "hasMore": has_more,
                "nextOffset": next_offset,
            }
        )

    @app.get("/api/entries/<date_value>")
    def get_entry(date_value: str) -> Any:
        user, unauthorized_response = _require_authenticated_user()
        if unauthorized_response is not None:
            return unauthorized_response

        if not is_valid_iso_date(date_value):
            return jsonify({"error": "invalid date format"}), HTTP_UNPROCESSABLE_ENTITY

        repo = _get_repository()

        try:
            entry = repo.get_entry(user["id"], date_value)
        except Exception:
            return jsonify({"error": "failed to fetch entry"}), 500

        if entry is None:
            return jsonify({"error": "entry not found"}), 404

        return jsonify({"entry": entry})

    @app.put("/api/entries/<date_value>")
    def upsert_entry(date_value: str) -> Any:
        user, unauthorized_response = _require_authenticated_user()
        if unauthorized_response is not None:
            return unauthorized_response

        if not is_valid_iso_date(date_value):
            return jsonify({"error": "invalid date format"}), HTTP_UNPROCESSABLE_ENTITY
        if not is_not_future_iso_date(date_value):
            return jsonify({"error": "future dates are not allowed"}), HTTP_UNPROCESSABLE_ENTITY

        payload, error_response = _require_json_object()
        if error_response is not None:
            return error_response

        ok, message, normalized_items = validate_items(payload.get("items"))
        if not ok:
            return jsonify({"error": message}), HTTP_UNPROCESSABLE_ENTITY

        repo = _get_repository()

        try:
            entry = repo.upsert_entry(user["id"], date_value, normalized_items)
        except Exception:
            return jsonify({"error": "failed to save entry"}), 500

        return jsonify({"entry": entry})

    @app.delete("/api/entries/<date_value>")
    def delete_entry(date_value: str) -> Any:
        user, unauthorized_response = _require_authenticated_user()
        if unauthorized_response is not None:
            return unauthorized_response

        if not is_valid_iso_date(date_value):
            return jsonify({"error": "invalid date format"}), HTTP_UNPROCESSABLE_ENTITY

        repo = _get_repository()

        try:
            deleted = repo.delete_entry(user["id"], date_value)
        except Exception:
            return jsonify({"error": "failed to delete entry"}), 500

        if not deleted:
            return jsonify({"error": "entry not found"}), 404

        return "", 204

    @app.get("/api/calendar")
    def calendar() -> Any:
        user, unauthorized_response = _require_authenticated_user()
        if unauthorized_response is not None:
            return unauthorized_response

        month_input = request.args.get("month") or date.today().strftime("%Y-%m")
        is_valid, month_value_or_error = validate_month(month_input)
        if not is_valid:
            return jsonify({"error": month_value_or_error}), HTTP_UNPROCESSABLE_ENTITY

        repo = _get_repository()
        month_value = month_value_or_error
        try:
            completed_dates = repo.list_completed_dates_for_month(user["id"], month_value)
        except Exception:
            return jsonify({"error": "failed to load calendar"}), 500

        return jsonify({"month": month_value, "completedDates": completed_dates})

    @app.get("/api/reminder")
    def get_reminder() -> Any:
        user, unauthorized_response = _require_authenticated_user()
        if unauthorized_response is not None:
            return unauthorized_response

        repo = _get_repository()
        try:
            settings = repo.get_reminder_settings(user["id"])
        except Exception:
            return jsonify({"error": "failed to load reminder settings"}), 500

        return jsonify({"settings": settings})

    @app.put("/api/reminder")
    def upsert_reminder() -> Any:
        user, unauthorized_response = _require_authenticated_user()
        if unauthorized_response is not None:
            return unauthorized_response

        payload, error_response = _require_json_object()
        if error_response is not None:
            return error_response

        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            return jsonify({"error": "enabled must be a boolean"}), HTTP_UNPROCESSABLE_ENTITY

        is_valid_time, time_or_error = validate_reminder_time(payload.get("time"))
        if not is_valid_time:
            return jsonify({"error": time_or_error}), HTTP_UNPROCESSABLE_ENTITY

        repo = _get_repository()
        try:
            settings = repo.upsert_reminder_settings(user["id"], enabled, time_or_error)
        except Exception:
            return jsonify({"error": "failed to save reminder settings"}), 500

        return jsonify({"settings": settings})

    @app.route("/api")
    @app.route("/api/<path:_path>")
    def api_not_found(_path: str = "") -> Any:
        return jsonify({"error": "not found"}), 404

    @app.get("/")
    def serve_index() -> Any:
        return send_from_directory(public_dir, "index.html")

    @app.get("/<path:path_value>")
    def serve_static(path_value: str) -> Any:
        requested = os.path.join(public_dir, path_value)
        if os.path.isfile(requested):
            return send_from_directory(public_dir, path_value)
        return send_from_directory(public_dir, "index.html")

    return app


def _get_repository() -> Repository:
    return current_app.config[REPOSITORY_KEY]


def _require_json_object() -> tuple[dict[str, Any], Any | None]:
    if not request.is_json:
        return {}, (jsonify({"error": "content type must be application/json"}), 415)

    try:
        payload = request.get_json(silent=False)
    except BadRequest:
        return {}, (jsonify({"error": "invalid json payload"}), 400)

    if not isinstance(payload, dict):
        return {}, (jsonify({"error": "invalid json payload"}), 400)

    return payload, None


def _require_authenticated_user() -> tuple[User | None, Any | None]:
    raw_user_id = session.get(SESSION_USER_ID_KEY)
    if not isinstance(raw_user_id, int):
        return None, (jsonify({"error": "authentication required"}), 401)

    repo = _get_repository()
    try:
        user = repo.get_user_by_id(raw_user_id)
    except Exception:
        return None, (jsonify({"error": "failed to authenticate"}), 500)

    if user is None:
        session.pop(SESSION_USER_ID_KEY, None)
        return None, (jsonify({"error": "authentication required"}), 401)

    return user, None

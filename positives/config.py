import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    port: int = 8080

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DATABASE_URL is required")

        secret_key = os.getenv("SECRET_KEY", "").strip() or "dev-secret-change-me"
        port = int(os.getenv("PORT", "8080"))
        return cls(database_url=database_url, secret_key=secret_key, port=port)

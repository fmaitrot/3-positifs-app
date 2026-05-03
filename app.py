from positives.app_factory import create_app
from positives.config import Settings
from positives.repository import PostgresRepository

settings = Settings.from_env()
repository = PostgresRepository(settings.database_url)
app = create_app(repository, settings.secret_key)


def init_db() -> None:
    repository.init_db()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=settings.port)

"""Load project environment settings and build the PostgreSQL connection URL."""

import os
from pathlib import Path
from urllib.parse import quote

from dotenv import dotenv_values


PROJECT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
PROJECT_ENV_KEYS = frozenset(
    {
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_PORT",
        "DATABASE_URL",
        "GEMINI_API_KEY",
        "SEARXNG_URL",
        "REPOSITORY_ROOT",
    }
)


def load_project_environment(env_file: Path | None = None) -> None:
    """Load supported settings from .env without overriding shell variables."""
    values = dotenv_values(env_file or PROJECT_ENV_FILE, interpolate=False)
    for name in PROJECT_ENV_KEYS:
        value = values.get(name)
        if value is not None:
            os.environ.setdefault(name, value)


def resolve_database_url() -> str:
    """Use DATABASE_URL or derive one from POSTGRES_* values."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        return database_url

    password = os.environ.get("POSTGRES_PASSWORD", "")
    if not password:
        raise RuntimeError(
            "Set DATABASE_URL or a non-empty POSTGRES_PASSWORD in .env or the shell."
        )

    user = os.environ.get("POSTGRES_USER", "developer")
    database = os.environ.get("POSTGRES_DB", "developer_intelligence")
    port = os.environ.get("POSTGRES_PORT", "5433").strip()
    if not user or not database:
        raise ValueError("POSTGRES_USER and POSTGRES_DB must not be empty.")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("POSTGRES_PORT must be an integer from 1 to 65535.")

    database_url = (
        f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@127.0.0.1:{port}/{quote(database, safe='')}"
    )
    os.environ["DATABASE_URL"] = database_url
    return database_url

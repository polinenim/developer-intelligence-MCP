import os

from tools.environment import load_project_environment, resolve_database_url


def test_project_env_fills_unset_values_without_overriding_shell(
    monkeypatch, tmp_path
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POSTGRES_USER=file_user\n"
        "POSTGRES_PASSWORD=file-password\n"
        "POSTGRES_DB=file_database\n"
        "POSTGRES_PORT=5434\n"
        "DATABASE_URL=\n"
        "GEMINI_API_KEY=file-key\n"
        "SEARXNG_URL=http://localhost:8080\n"
        "REPOSITORY_ROOT=.\n",
        encoding="utf-8",
    )
    for name in (
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_PORT",
        "DATABASE_URL",
        "SEARXNG_URL",
        "REPOSITORY_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("POSTGRES_USER", "shell_user")
    monkeypatch.setenv("GEMINI_API_KEY", "shell-key")

    load_project_environment(env_file)

    assert os.environ["POSTGRES_USER"] == "shell_user"
    assert os.environ["POSTGRES_PASSWORD"] == "file-password"
    assert os.environ["POSTGRES_DB"] == "file_database"
    assert os.environ["POSTGRES_PORT"] == "5434"
    assert os.environ["DATABASE_URL"] == ""
    assert os.environ["GEMINI_API_KEY"] == "shell-key"
    assert os.environ["SEARXNG_URL"] == "http://localhost:8080"
    assert os.environ["REPOSITORY_ROOT"] == "."


def test_database_url_is_derived_with_encoded_password(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "developer")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:/#")
    monkeypatch.setenv("POSTGRES_DB", "developer_intelligence")
    monkeypatch.setenv("POSTGRES_PORT", "5434")
    monkeypatch.setenv("DATABASE_URL", "")

    assert resolve_database_url() == (
        "postgresql://developer:p%40ss%3A%2F%23"
        "@127.0.0.1:5434/developer_intelligence"
    )


def test_explicit_database_url_takes_precedence(monkeypatch):
    configured_url = "postgresql://custom:explicit@db.example:5432/custom_db"
    monkeypatch.setenv("DATABASE_URL", configured_url)
    monkeypatch.setenv("POSTGRES_PASSWORD", "derived-password")

    assert resolve_database_url() == configured_url

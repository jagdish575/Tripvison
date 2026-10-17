"""Single-process deployment: the API serves the built frontend, and SQLite lives under the host's DATA_DIR."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def _static(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>TripMission</title>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("nope", encoding="utf-8")
    return tmp_path


def test_api_serves_the_built_frontend(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "static_dir", str(_static(tmp_path)))
    client = TestClient(create_app())
    for path in ("/", "/plan", "/results/abc", "/trips"):  # client-side routes get the app shell
        response = client.get(path)
        assert response.status_code == 200 and "<title>TripMission</title>" in response.text, path
        assert response.headers["cache-control"] == "no-cache"
    assert client.get("/assets/app.js").text == "console.log('ok')"
    assert client.get("/favicon.svg").text == "<svg/>"
    assert "nope" not in client.get("/..%2Fsecret.txt").text  # no escaping the static folder
    # the API still wins, and unknown API paths stay JSON errors rather than the HTML shell
    assert client.get("/api/v1/health").json()["status"] == "ok"
    missing = client.get("/api/v1/does-not-exist")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def test_without_a_build_the_api_runs_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "static_dir", str(tmp_path / "missing"))
    client = TestClient(create_app())
    assert client.get("/plan").status_code == 404
    assert client.get("/api/v1/health").status_code == 200


def test_sqlite_lives_in_data_dir_unless_a_database_url_is_set(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)  # the test suite points every Settings() at its own DB
    data = tmp_path / "data"
    settings = Settings(_env_file=None, data_dir=str(data))
    assert settings.database_url == f"sqlite:///{(data / 'tripmission.db').as_posix()}" and data.is_dir()
    explicit = Settings(_env_file=None, data_dir=str(data), database_url="postgresql+psycopg://u:p@h/db")
    assert explicit.database_url == "postgresql+psycopg://u:p@h/db"

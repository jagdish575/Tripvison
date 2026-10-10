from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Configure the environment before the app (and its cached settings) is imported.
_TMP = Path(tempfile.mkdtemp(prefix="tripvision-tests-"))
os.environ.update({
    "DEMO_MODE": "false",
    "SERPAPI_API_KEY": "test-serpapi-key-123456",
    "AI_API_KEY": "",
    "REDIS_URL": "",
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    "LOG_LEVEL": "WARNING",
    # Never send real email from tests, whatever the developer's .env says.
    "EMAIL_PROVIDER": "preview",
    "SMTP_HOST": "",
    "SMTP_PASSWORD": "",
    "RESEND_API_KEY": "",
    "DEBUG_MODE": "false",
    "GOOGLE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
    "SESSION_SECRET": "test-session-secret-0123456789-abcdefghij",
    "AUTH_REQUIRED": "true",
    "DEMO_LOGIN_ENABLED": "true",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.core.cache import MemoryCache, set_cache  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import init_db  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.integrations.serpapi.client import SerpApiClient  # noqa: E402
from app.services.providers import set_serpapi_client  # noqa: E402
from fixtures.serpapi_payloads import MockSerpApi  # noqa: E402

init_db()


async def _no_sleep(_: float) -> None:
    return None


@pytest.fixture
def mock_serpapi():
    return MockSerpApi()


@pytest.fixture
def serp_client(mock_serpapi):
    cache = MemoryCache()
    set_cache(cache)
    client = SerpApiClient("test-serpapi-key-123456", cache=cache, transport=httpx.MockTransport(mock_serpapi),
                           max_retries=2, sleep=_no_sleep)
    set_serpapi_client(client)
    yield client
    set_serpapi_client(None)


@pytest.fixture
def settings():
    return get_settings()


GOOGLE_USER = {"sub": "google-sub-1", "email": "traveller@example.com", "email_verified": True,
               "name": "Asha Traveller", "picture": "https://example.test/a.png"}


def sign_in_google(client, monkeypatch, claims: dict | None = None) -> dict:
    """Sign a TestClient in through the real /auth/google route, with Google's signature check stubbed."""
    from app.services import auth as auth_service

    async def fake_verify(credential, settings=None):
        assert credential.startswith("test-google-credential")
        return claims or GOOGLE_USER

    monkeypatch.setattr(auth_service, "verify_google_id_token", fake_verify)
    import app.api.routes.auth as auth_routes
    monkeypatch.setattr(auth_routes, "verify_google_id_token", fake_verify)
    response = client.post("/api/v1/auth/google", json={"credential": "test-google-credential-0123456789"})
    assert response.status_code == 200, response.text
    return response.json()["user"]


@pytest.fixture
def anon_api(serp_client):
    from fastapi.testclient import TestClient

    from app.main import app

    limiter.reset()
    with TestClient(app) as client:
        yield client
    limiter.reset()


@pytest.fixture
def api(anon_api, monkeypatch):
    """A client signed in as a Google user (live data via the mocked SerpApi)."""
    sign_in_google(anon_api, monkeypatch)
    return anon_api


@pytest.fixture
def demo_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "demo_mode", True)
    return s

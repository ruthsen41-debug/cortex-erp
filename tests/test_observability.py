from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.observability import (
    AccessLogMiddleware,
    RateLimitMiddleware,
    metrics_endpoint,
)


def _app(**limits):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, **limits)
    app.add_middleware(AccessLogMiddleware)
    app.add_route("/metrics", metrics_endpoint)

    @app.post("/api/auth/login")
    def login():
        return {"ok": True}

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


def test_login_rate_limit_returns_429_with_retry_after():
    client = TestClient(_app(api_limit=0, login_limit=3))
    codes = [client.post("/api/auth/login").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    blocked = client.post("/api/auth/login")
    assert int(blocked.headers["Retry-After"]) >= 1
    # Outras rotas nao sao afetadas pelo limite de login.
    assert client.get("/api/ping").status_code == 200


def test_api_rate_limit_spares_health_check():
    client = TestClient(_app(api_limit=2, login_limit=0))
    assert [client.get("/api/ping").status_code for _ in range(3)] == [200, 200, 429]
    for _ in range(5):
        assert client.get("/api/health").status_code == 200


def test_limit_zero_disables_limiting():
    client = TestClient(_app(api_limit=0, login_limit=0))
    assert all(client.post("/api/auth/login").status_code == 200 for _ in range(30))


def test_forwarded_ip_only_trusted_behind_proxy():
    trusted = TestClient(_app(api_limit=1, login_limit=0, trust_proxy=True))
    assert trusted.get("/api/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert trusted.get("/api/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert trusted.get("/api/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429

    direct = TestClient(_app(api_limit=1, login_limit=0, trust_proxy=False))
    assert direct.get("/api/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    # Sem confiar no proxy, trocar o header nao burla o limite.
    assert direct.get("/api/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429


def test_request_id_header_and_metrics():
    client = TestClient(_app(api_limit=0, login_limit=0))
    res = client.get("/api/ping", headers={"X-Request-ID": "abc123"})
    assert res.headers["X-Request-ID"] == "abc123"
    assert client.get("/api/ping").headers["X-Request-ID"]

    text = client.get("/metrics").text
    assert 'cortex_http_requests_total{method="GET",status="2xx"}' in text
    assert "cortex_http_request_duration_seconds_count" in text


def test_metrics_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "s3cret")
    client = TestClient(_app(api_limit=0, login_limit=0))
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret"}).status_code == 200
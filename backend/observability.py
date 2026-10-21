"""Rate limiting, log de acesso estruturado e metricas Prometheus (sem dependencias externas).

Tudo vive em memoria do processo: com varios workers do uvicorn cada um mantem
seus proprios contadores/limites. Para limites globais entre instancias use o
proxy reverso (Caddy/nginx) ou um Redis.
"""
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, PlainTextResponse, Response

logger = logging.getLogger("cortex.access")


def setup_logging() -> None:
    """Configura o log raiz. LOG_FORMAT=json emite uma linha JSON por evento."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    if os.getenv("LOG_FORMAT", "text").lower() == "json":
        class _Json(logging.Formatter):
            def format(self, record):
                data = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                        "logger": record.name, "msg": record.getMessage()}
                data.update(getattr(record, "extra_fields", {}))
                return json.dumps(data, ensure_ascii=False)
        handler = logging.StreamHandler()
        handler.setFormatter(_Json())
        logger.handlers[:] = [handler]
        logger.propagate = False
    else:
        logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.setLevel(level)


def client_ip(request, trust_proxy: bool) -> str:
    if trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class _Window:
    """Janela deslizante: no maximo `limit` eventos nos ultimos `seconds` segundos por chave."""

    def __init__(self, limit: int, seconds: int = 60):
        self.limit, self.seconds = limit, seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str):
        """Devolve (permitido, segundos_ate_liberar)."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= self.seconds:
                q.popleft()
            if len(q) >= self.limit:
                return False, max(1, int(self.seconds - (now - q[0])) + 1)
            q.append(now)
            if len(self._hits) > 10000:  # evita crescer sem limite
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limita requisicoes por IP. limite 0 desliga. `login_paths` tem um limite mais estrito."""

    def __init__(self, app, api_limit=300, login_limit=10, login_paths=("/api/auth/login",), trust_proxy=False):
        super().__init__(app)
        self.api = _Window(api_limit) if api_limit > 0 else None
        self.login = _Window(login_limit) if login_limit > 0 else None
        self.login_paths = tuple(login_paths)
        self.trust_proxy = trust_proxy

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path != "/api/health":
            ip = client_ip(request, self.trust_proxy)
            checks = []
            if self.login and path in self.login_paths:
                checks.append(("login", self.login))
            if self.api:
                checks.append(("api", self.api))
            for name, window in checks:
                ok, retry = window.check(f"{name}:{ip}")
                if not ok:
                    return JSONResponse(
                        {"detail": "Muitas requisições. Tente novamente em instantes."},
                        status_code=429,
                        headers={"Retry-After": str(retry)},
                    )
        return await call_next(request)


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.requests = defaultdict(int)  # (method, status_class) -> n
        self.duration_sum = 0.0
        self.duration_count = 0
        self.started = time.time()

    def observe(self, method: str, status: int, seconds: float):
        with self._lock:
            self.requests[(method, f"{status // 100}xx")] += 1
            self.duration_sum += seconds
            self.duration_count += 1

    def render(self) -> str:
        with self._lock:
            lines = [
                "# HELP cortex_http_requests_total Requisicoes HTTP por metodo e classe de status.",
                "# TYPE cortex_http_requests_total counter",
            ]
            for (method, klass), n in sorted(self.requests.items()):
                lines.append(f'cortex_http_requests_total{{method="{method}",status="{klass}"}} {n}')
            lines += [
                "# HELP cortex_http_request_duration_seconds Duracao das requisicoes.",
                "# TYPE cortex_http_request_duration_seconds summary",
                f"cortex_http_request_duration_seconds_sum {self.duration_sum:.6f}",
                f"cortex_http_request_duration_seconds_count {self.duration_count}",
                "# HELP cortex_uptime_seconds Tempo desde o inicio do processo.",
                "# TYPE cortex_uptime_seconds gauge",
                f"cortex_uptime_seconds {time.time() - self.started:.0f}",
            ]
        return "\n".join(lines) + "\n"


metrics = Metrics()


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Atribui X-Request-ID, registra uma linha por requisicao e alimenta as metricas."""

    def __init__(self, app, trust_proxy=False):
        super().__init__(app)
        self.trust_proxy = trust_proxy

    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            logger.exception("erro nao tratado", extra={"extra_fields": {"request_id": rid, "path": request.url.path}})
            raise
        finally:
            elapsed = time.perf_counter() - start
            if request.url.path != "/metrics":
                metrics.observe(request.method, status, elapsed)
            logger.info(
                "%s %s -> %s (%.1f ms) rid=%s",
                request.method, request.url.path, status, elapsed * 1000, rid,
                extra={"extra_fields": {
                    "request_id": rid, "method": request.method, "path": request.url.path,
                    "status": status, "duration_ms": round(elapsed * 1000, 1),
                    "ip": client_ip(request, self.trust_proxy),
                }},
            )
        response.headers["X-Request-ID"] = rid
        return response


def metrics_endpoint(request) -> Response:
    """GET /metrics (formato Prometheus). Se METRICS_TOKEN estiver definido, exige Bearer."""
    token = os.getenv("METRICS_TOKEN", "").strip()
    if token and request.headers.get("authorization", "") != f"Bearer {token}":
        return PlainTextResponse("unauthorized\n", status_code=401)
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

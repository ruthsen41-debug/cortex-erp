import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    from .config import FRONTEND_DIR, STATIC_DIR, CORS_ORIGINS, SERVER_HOST
    from .database import init_db
    from .routers import all_routers
    from .observability import AccessLogMiddleware, RateLimitMiddleware, metrics_endpoint, setup_logging
except ImportError:
    from config import FRONTEND_DIR, STATIC_DIR, CORS_ORIGINS, SERVER_HOST
    from database import init_db
    from routers import all_routers
    from observability import AccessLogMiddleware, RateLimitMiddleware, metrics_endpoint, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização do banco de dados e dados padrão
    init_db()
    yield


app = FastAPI(
    title="Cortex ERP Pro+",
    description="Sistema de Gestão Empresarial, Financeira & Emissor Fiscal com IA",
    version="4.5.0",
    lifespan=lifespan,
)

# CORS
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Rate limiting (0 desliga), log de acesso com X-Request-ID e metricas.
# O log de acesso é adicionado por último para ficar por fora e registrar também os 429.
setup_logging()
_TRUST_PROXY = os.getenv("TRUSTED_PROXY", "0") == "1"
app.add_middleware(
    RateLimitMiddleware,
    api_limit=int(os.getenv("RATE_LIMIT_API", "300")),
    login_limit=int(os.getenv("RATE_LIMIT_LOGIN", "10")),
    trust_proxy=_TRUST_PROXY,
)
app.add_middleware(AccessLogMiddleware, trust_proxy=_TRUST_PROXY)
app.add_route("/metrics", metrics_endpoint, include_in_schema=False)

# Registra todos os roteadores modulares
for r in all_routers:
    app.include_router(r)

# Health Check
@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "4.5.0", "message": "Cortex ERP Pro+ operacional"}


# Serve Arquivos Estáticos e Interface SPA
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    idx_file = FRONTEND_DIR / "index.html"
    return idx_file.read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=SERVER_HOST, port=8000, reload=True)

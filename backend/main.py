import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import re
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

try:
    from .config import FRONTEND_DIR, STATIC_DIR, CORS_ORIGINS, SERVER_HOST
    from .database import init_db
    from .routers import all_routers
    from .observability import AccessLogMiddleware, RateLimitMiddleware, metrics_endpoint, setup_logging
    from .version import APP_VERSION, build_id
except ImportError:
    from config import FRONTEND_DIR, STATIC_DIR, CORS_ORIGINS, SERVER_HOST
    from database import init_db
    from routers import all_routers
    from observability import AccessLogMiddleware, RateLimitMiddleware, metrics_endpoint, setup_logging
    from version import APP_VERSION, build_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização do banco de dados e dados padrão
    init_db()
    # Rotinas automáticas do DP (calcular folha, enviar holerites, lançar no financeiro)
    try:
        from .routers.dp_utilitarios import iniciar_agendador
    except ImportError:
        from routers.dp_utilitarios import iniciar_agendador
    iniciar_agendador()
    # Servidor instalado (Windows): verificação/instalação automática de atualizações
    try:
        from .routers.atualizacao import iniciar_agendador_atualizacao
    except ImportError:
        from routers.atualizacao import iniciar_agendador_atualizacao
    iniciar_agendador_atualizacao()
    yield


app = FastAPI(
    title="Cortex ERP Pro+",
    description="Sistema de Gestão Empresarial, Financeira & Emissor Fiscal com IA",
    version=APP_VERSION,
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
    return {"status": "ok", "version": APP_VERSION, "message": "Cortex ERP Pro+ operacional"}


@app.get("/api/version")
def app_version():
    """Versão em execução. O navegador compara o build com o da página aberta
    e, se mudou, mostra o aviso "Nova versão disponível"."""
    return JSONResponse(
        {"version": APP_VERSION, "build": build_id()},
        headers={"Cache-Control": "no-store"},
    )


# Service worker com o nome do cache atrelado ao build: qualquer mudança no
# frontend gera um cache novo e o antigo é descartado (sem trocar versão à mão).
@app.get("/static/sw.js", include_in_schema=False)
def service_worker():
    codigo = (STATIC_DIR / "sw.js").read_text(encoding="utf-8-sig")
    codigo = codigo.replace("__CORTEX_BUILD__", build_id())
    return Response(
        codigo,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


# Serve Arquivos Estáticos e Interface SPA
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    idx_file = FRONTEND_DIR / "index.html"
    html = idx_file.read_text(encoding="utf-8")
    build = build_id()
    # ?v=<build> nos scripts/estilos: o navegador nunca mistura arquivo velho com página nova
    html = _RE_ASSET.sub(lambda m: f'{m.group(1)}="{m.group(2)}?v={build}"', html)
    meta = f'<meta name="cortex-build" content="{build}" data-version="{APP_VERSION}" />'
    html = html.replace("<head>", "<head>\n  " + meta, 1)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


_RE_ASSET = re.compile(r'(src|href)="(/static/[^"?]+\.(?:js|css))"')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=SERVER_HOST, port=8000, reload=True)

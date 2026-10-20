from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    from .config import FRONTEND_DIR, STATIC_DIR
    from .database import init_db
    from .routers import all_routers
except ImportError:
    from config import FRONTEND_DIR, STATIC_DIR
    from database import init_db
    from routers import all_routers


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

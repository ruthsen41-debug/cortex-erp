import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cortex_erp.db"

# Carrega .env do projeto ou cortex_ai (Gemini)
load_dotenv(BASE_DIR / ".env")
cortex_ai_env = Path.home() / "cortex_ai" / ".env"
if cortex_ai_env.exists():
    load_dotenv(cortex_ai_env, override=False)

# Configurações de Segurança e JWT
def _load_secret_key() -> str:
    """Usa JWT_SECRET_KEY do ambiente; sem ela, gera e persiste uma chave aleatória em data/.jwt_secret."""
    env_key = os.getenv("JWT_SECRET_KEY", "").strip()
    if env_key:
        return env_key
    secret_file = DATA_DIR / ".jwt_secret"
    if secret_file.exists():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_urlsafe(64)
    secret_file.write_text(generated, encoding="utf-8")
    return generated


SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# Multiempresa Padrão
DEFAULT_COMPANY_ID = 1

# CORS: lista separada por vírgula. Vazio = apenas mesma origem (o frontend é servido pelo próprio backend).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
# Host de bind do servidor local
SERVER_HOST = os.getenv("CORTEX_HOST", "127.0.0.1")

# IA / Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

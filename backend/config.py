import os
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
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cortex-erp-secret-key-super-secure-change-in-prod-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# Multiempresa Padrão
DEFAULT_COMPANY_ID = 1

# IA / Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

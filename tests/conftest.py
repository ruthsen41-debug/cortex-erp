import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Na suite de testes, desativa o rate limit por IP para nao interferir em dezenas de chamadas simultaneas
os.environ.setdefault("RATE_LIMIT_LOGIN", "0")
os.environ.setdefault("RATE_LIMIT_API", "0")


@pytest.fixture(scope="session", autouse=True)
def _init_database():
    """Cria schema e dados iniciais (o TestClient sem `with` nao executa o lifespan do app).

    Sem isso a suite so passa num banco que ja foi inicializado, e falha em um
    checkout limpo (CI) ou num PostgreSQL vazio.
    """
    from backend.database import init_db

    init_db()

"""Ambiente do Alembic: usa DATABASE_URL (PostgreSQL) e roda as migracoes em SQL puro."""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith(("postgres://", "postgresql://")):
        raise SystemExit("Defina DATABASE_URL apontando para um PostgreSQL (ex.: postgresql://user:senha@host:5432/cortex).")
    # SQLAlchemy precisa do driver explicito; o app usa psycopg 3.
    return url.replace("postgres://", "postgresql://", 1).replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
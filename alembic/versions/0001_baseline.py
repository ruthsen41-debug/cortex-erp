"""Schema inicial do Cortex ERP (39 tabelas).

Gerado com pg_dump --schema-only a partir do PostgreSQL criado por init_db().
O SQL fica em 0001_baseline_schema.sql. Em um banco que ja tem as tabelas
(criado por init_db), use `alembic stamp head` em vez de `upgrade`.

Revision ID: 0001
Revises:
Create Date: 2026-10-21
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_SQL = Path(__file__).with_name("0001_baseline_schema.sql")


def upgrade() -> None:
    script = _SQL.read_text(encoding="utf-8")
    # Linhas de sessao do pg_dump (search_path vazio etc.) nao se aplicam aqui.
    lines = [
        ln for ln in script.splitlines()
        if not ln.startswith("\\") and "set_config('search_path'" not in ln
    ]
    op.get_bind().exec_driver_sql("\n".join(lines))


def downgrade() -> None:
    raise NotImplementedError("O baseline nao e reversivel; recrie o banco.")
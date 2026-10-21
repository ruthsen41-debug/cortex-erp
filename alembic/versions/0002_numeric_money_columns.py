"""Converte colunas monetárias de REAL para NUMERIC(15,2) no PostgreSQL.

No SQLite a mudança é no-op: o tipo é consultivo e os valores float
já são arredondados para 2 casas decimais pela camada Python (round_money).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# (tabela, [colunas monetárias])
_MONEY_COLS = [
    ("bank_accounts",      ["initial_balance", "current_balance"]),
    ("cost_centers",       ["monthly_budget"]),
    ("contacts",           ["credit_limit"]),
    ("products",           ["cost_price", "average_cost", "sale_price"]),
    ("financial_entries",  ["amount", "interest", "fine", "discount", "paid_amount"]),
    ("financial_payments", ["principal_paid", "interest_paid", "fine_paid",
                            "discount_applied", "total_cash_flow"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite: no-op

    numeric = sa.Numeric(15, 2)
    for table, cols in _MONEY_COLS:
        for col in cols:
            op.alter_column(
                table, col,
                type_=numeric,
                existing_type=sa.Float(),
                existing_nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table, cols in _MONEY_COLS:
        for col in cols:
            op.alter_column(
                table, col,
                type_=sa.Float(),
                existing_type=sa.Numeric(15, 2),
                existing_nullable=True,
            )

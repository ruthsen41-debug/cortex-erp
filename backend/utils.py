import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any
from datetime import date


def rows_to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    """Converte lista de sqlite3.Row em lista de dicionários padrão."""
    return [dict(r) for r in rows] if rows else []


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Converte um único sqlite3.Row em dicionário."""
    return dict(row) if row else {}


def round_money(value) -> float:
    """Arredonda um valor monetário para 2 casas decimais usando ROUND_HALF_UP.

    Usa Decimal internamente para evitar a imprecisão do float IEEE 754.
    Retorna float para compatibilidade com o banco SQLite e a API JSON.
    """
    try:
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return round(float(value or 0), 2)


def add_months(d: date, months: int) -> date:
    """Adiciona N meses a uma data respeitando o último dia do mês."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(
        d.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return date(year, month, day)

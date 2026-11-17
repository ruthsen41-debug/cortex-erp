from datetime import date
import html as html_lib
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
    from ..schemas.accounting import AccountingAccountCreate, AccountingAccountUpdate, AccountingEntryCreate
    from ..services.ecd_generator import EcdGenerator
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts
    from schemas.accounting import AccountingAccountCreate, AccountingAccountUpdate, AccountingEntryCreate
    from services.ecd_generator import EcdGenerator

router = APIRouter(tags=["Módulo Contábil"])


class ClosePeriodPayload(BaseModel):
    start_date: str
    end_date: str
    lock_period: bool = True


class StandardHistoryPayload(BaseModel):
    code: str
    description: str
    debit_account_code: str
    credit_account_code: str


class EntryFromStandardPayload(BaseModel):
    history_code: str
    entry_date: str
    amount: float
    complement: str = ""
    document_number: str = ""
    cost_center_id: Optional[int] = None


class AccountingNotePayload(BaseModel):
    year: int
    number: int
    title: str
    content: str


_REFERENCIAL_MAP = [
    ("1.1.01", "1.01.01.01.01"),
    ("1.1.02", "1.01.01.02.01"),
    ("1.1.03", "1.01.01.03.01"),
    ("1.1.04", "1.01.02.01.01"),
    ("1.1.05", "1.01.02.01.99"),
    ("1.1.06", "1.01.03.01.01"),
    ("1.1.07", "1.01.04.01.01"),
    ("1.1.08", "1.01.05.01.01"),
    ("1.1.09", "1.01.09.01.01"),
    ("1.2.01", "1.02.01.01.01"),
    ("1.2.02", "1.02.02.01.01"),
    ("1.2.03.04", "1.02.03.01.99"),
    ("1.2.03.01", "1.02.03.01.01"),
    ("1.2.03.02", "1.02.03.01.02"),
    ("1.2.03.03", "1.02.03.01.03"),
    ("1.2.03", "1.02.03.01.00"),
    ("1.2.04.02", "1.02.04.01.99"),
    ("1.2.04.01", "1.02.04.01.01"),
    ("1.2.04", "1.02.04.01.00"),
    ("2.1.01", "2.01.01.01.01"),
    ("2.1.02", "2.01.01.03.00"),
    ("2.1.03", "2.01.01.02.00"),
    ("2.1.04", "2.01.01.04.01"),
    ("2.1.05", "2.01.01.09.01"),
    ("2.2.01", "2.02.01.01.01"),
    ("2.3.01", "2.03.01.01.01"),
    ("2.3.02", "2.03.02.01.01"),
    ("2.3.03", "2.03.04.01.01"),
    ("3.1", "3.01.01.01.01"),
    ("3.2", "3.01.01.01.02"),
    ("3.3", "3.01.01.05.01"),
    ("4.1", "3.01.01.03.01"),
    ("5.1", "3.01.01.07.01.01"),
    ("5.2", "3.01.01.07.01.05"),
    ("5.3", "3.01.01.07.01.02"),
    ("5.4", "3.01.01.09.01"),
    ("5.5", "3.01.01.07.01.99"),
]


def _check_period_open(conn, company_id: int, entry_date: str) -> None:
    """Bloqueia criação/exclusão de lançamentos em períodos contábeis fechados."""
    locked = conn.execute(
        "SELECT id, end_date FROM accounting_periods WHERE company_id = ? AND status = 'fechado' AND end_date >= ? LIMIT 1",
        (company_id, entry_date),
    ).fetchone()
    if locked:
        conn.close()
        raise HTTPException(status_code=400, detail="Período contábil encerrado/bloqueado para esta data.")


def _seed_standard_histories(conn, company_id: int) -> None:
    count = conn.execute(
        "SELECT COUNT(*) FROM accounting_standard_histories WHERE company_id = ?", (company_id,)
    ).fetchone()[0]
    if count > 0:
        return
    defaults = [
        ("H001", "Pagamento a Fornecedor", "2.1.01", "1.1.02"),
        ("H002", "Recebimento de Cliente", "1.1.02", "1.1.04"),
        ("H003", "Pagamento de Salários e Ordenados", "2.1.03.01", "1.1.02"),
        ("H004", "Pagamento de Energia Elétrica / Aluguel", "5.2.02", "1.1.02"),
        ("H005", "Tarifas e Despesas Bancárias", "5.4.01", "1.1.02"),
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO accounting_standard_histories
           (company_id, code, description, debit_account_code, credit_account_code)
           VALUES (?, ?, ?, ?, ?)""",
        [(company_id, *d) for d in defaults],
    )
    conn.commit()


def _seed_default_notes(conn, company_id: int, year: int, company_name: str, regime: str) -> None:
    count = conn.execute(
        "SELECT COUNT(*) FROM accounting_notes WHERE company_id = ? AND year = ?",
        (company_id, year),
    ).fetchone()[0]
    if count > 0:
        return
    reg_fmt = (regime or "simples_nacional").replace("_", " ").title()
    defaults = [
        (1, "Contexto Operacional",
         f"A sociedade {company_name} tem como objeto social a exploração de atividades comerciais e/ou prestação de serviços no território nacional, operando em continuidade normal no exercício de {year}."),
        (2, "Apresentação das Demonstrações Contábeis e Base de Preparação",
         "As demonstrações contábeis foram elaboradas de acordo com as práticas contábeis adotadas no Brasil (NBC TG 1000 — Contabilidade para PMEs / Lei nº 6.404/76 e alterações), sob o regime de competência."),
        (3, "Principais Práticas Contábeis",
         "Caixa e equivalentes compreendem numerários em espécie e depósitos bancários de liquidez imediata. Contas a receber e estoques são avaliados pelo valor realizável/custo médio. O ativo imobilizado é registrado pelo custo de aquisição deduzido da depreciação acumulada linear."),
        (4, "Obrigações Fiscais, Trabalhistas e Regime Tributário",
         f"A entidade encontra-se enquadrada no regime tributário '{reg_fmt}'. Os tributos e encargos trabalhistas sobre folha de pagamento e faturamento são provisionados pelo regime de competência."),
        (5, "Patrimônio Líquido e Destinação do Resultado",
         "O Capital Social encontra-se integralizado conforme contrato social. O resultado líquido apurado na DRE é transferido à conta de Lucros ou Prejuízos Acumulados no encerramento do exercício (ARE)."),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO accounting_notes (company_id, year, number, title, content) VALUES (?, ?, ?, ?, ?)",
        [(company_id, year, num, title, content) for num, title, content in defaults],
    )
    conn.commit()


# =====================================================
# PLANO DE CONTAS
# =====================================================

@router.get("/api/accounting/accounts")
def list_accounts(
    active_only: bool = Query(default=True),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Lista o Plano de Contas Contábil hierarquicamente."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    where = "company_id = ?" + (" AND active = 1" if active_only else "")
    rows = rows_to_dicts(conn.execute(
        f"SELECT * FROM accounting_accounts WHERE {where} ORDER BY code", (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/api/accounting/accounts", status_code=201)
def create_account(
    data: AccountingAccountCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Cria uma conta no Plano de Contas."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    existing = conn.execute(
        "SELECT id FROM accounting_accounts WHERE code = ? AND company_id = ?",
        (data.code, company_id)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Conta com código {data.code} já existe.")

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO accounting_accounts
            (company_id, code, name, account_type, nature, parent_code, accepts_entries, description, referencial_code, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (company_id, data.code, data.name, data.account_type, data.nature,
          data.parent_code or "", int(data.accepts_entries), data.description or "",
          data.referencial_code or ""))
    conn.commit()
    new_id = cur.lastrowid
    row = dict(conn.execute("SELECT * FROM accounting_accounts WHERE id = ?", (new_id,)).fetchone())
    conn.close()
    return row


@router.put("/api/accounting/accounts/{account_id}")
def update_account(
    account_id: int,
    data: AccountingAccountUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Atualiza dados de uma conta contábil."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    acc = conn.execute(
        "SELECT * FROM accounting_accounts WHERE id = ? AND company_id = ?",
        (account_id, company_id)
    ).fetchone()
    if not acc:
        conn.close()
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    fields = []
    values = []
    if data.name is not None:
        fields.append("name = ?"); values.append(data.name)
    if data.description is not None:
        fields.append("description = ?"); values.append(data.description)
    if data.accepts_entries is not None:
        fields.append("accepts_entries = ?"); values.append(int(data.accepts_entries))
    if data.active is not None:
        fields.append("active = ?"); values.append(int(data.active))
    if data.referencial_code is not None:
        fields.append("referencial_code = ?"); values.append(data.referencial_code)

    if fields:
        values.append(account_id)
        conn.execute(f"UPDATE accounting_accounts SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()

    row = dict(conn.execute("SELECT * FROM accounting_accounts WHERE id = ?", (account_id,)).fetchone())
    conn.close()
    return row


@router.delete("/api/accounting/accounts/{account_id}")
def delete_account(
    account_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove uma conta (apenas se não tiver lançamentos)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    acc = conn.execute(
        "SELECT * FROM accounting_accounts WHERE id = ? AND company_id = ?",
        (account_id, company_id)
    ).fetchone()
    if not acc:
        conn.close()
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    has_lines = conn.execute(
        "SELECT id FROM accounting_entry_lines WHERE account_id = ? LIMIT 1", (account_id,)
    ).fetchone()
    if has_lines:
        conn.close()
        raise HTTPException(status_code=400, detail="Conta possui lançamentos e não pode ser excluída. Desative-a.")

    conn.execute("DELETE FROM accounting_accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# =====================================================
# LANÇAMENTOS CONTÁBEIS (DIÁRIO)
# =====================================================

@router.get("/api/accounting/entries")
def list_entries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entry_type: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Lista lançamentos contábeis com filtros."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    today = date.today()
    s_date = start_date or date(today.year, today.month, 1).isoformat()
    e_date = end_date or today.isoformat()

    q = "SELECT * FROM accounting_entries WHERE company_id = ? AND entry_date BETWEEN ? AND ?"
    params = [company_id, s_date, e_date]
    if entry_type:
        q += " AND entry_type = ?"
        params.append(entry_type)
    q += " ORDER BY entry_date DESC, id DESC LIMIT ?"
    params.append(limit)

    entries = rows_to_dicts(conn.execute(q, params).fetchall())
    for entry in entries:
        entry["lines"] = rows_to_dicts(conn.execute("""
            SELECT l.*, a.code as account_code, a.name as account_name
            FROM accounting_entry_lines l
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE l.entry_id = ?
            ORDER BY l.id
        """, (entry["id"],)).fetchall())
    conn.close()
    return entries


@router.get("/api/accounting/entries/{entry_id}")
def get_entry(
    entry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retorna um lançamento contábil com suas linhas."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    entry = conn.execute(
        "SELECT * FROM accounting_entries WHERE id = ? AND company_id = ?",
        (entry_id, company_id)
    ).fetchone()
    if not entry:
        conn.close()
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")

    result = dict(entry)
    result["lines"] = rows_to_dicts(conn.execute("""
        SELECT l.*, a.code as account_code, a.name as account_name
        FROM accounting_entry_lines l
        JOIN accounting_accounts a ON a.id = l.account_id
        WHERE l.entry_id = ?
        ORDER BY l.id
    """, (entry_id,)).fetchall())
    conn.close()
    return result


@router.post("/api/accounting/entries", status_code=201)
def create_entry(
    data: AccountingEntryCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Cria um lançamento contábil (partidas dobradas)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _check_period_open(conn, company_id, data.entry_date)

    # Valida que todas as contas existem e aceitam lançamentos
    for line in data.lines:
        acc = conn.execute(
            "SELECT id, accepts_entries FROM accounting_accounts WHERE id = ? AND company_id = ? AND active = 1",
            (line.account_id, company_id)
        ).fetchone()
        if not acc:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Conta id={line.account_id} não encontrada.")
        if not acc["accepts_entries"]:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Conta id={line.account_id} é sintética e não aceita lançamentos diretos.")

    total_debit = sum(ln.debit or 0 for ln in data.lines)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO accounting_entries
            (company_id, entry_date, description, document_number, entry_type, origin_id, total_debit, total_credit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (company_id, data.entry_date, data.description,
          data.document_number or "", data.entry_type or "manual",
          data.origin_id, total_debit, total_debit))
    entry_id = cur.lastrowid

    for line in data.lines:
        cur.execute("""
            INSERT INTO accounting_entry_lines (entry_id, account_id, debit, credit, description, cost_center_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (entry_id, line.account_id, line.debit or 0.0, line.credit or 0.0, line.description or "", line.cost_center_id))

    conn.commit()
    conn.close()
    return get_entry(entry_id, current_user)


@router.delete("/api/accounting/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove um lançamento contábil (apenas manuais e em período aberto)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    entry = conn.execute(
        "SELECT * FROM accounting_entries WHERE id = ? AND company_id = ?",
        (entry_id, company_id)
    ).fetchone()
    if not entry:
        conn.close()
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
    entry_d = dict(entry)
    if entry_d.get("entry_type") in ("automatico", "encerramento"):
        conn.close()
        raise HTTPException(status_code=400, detail="Lançamentos automáticos ou de encerramento não podem ser excluídos manualmente.")
    _check_period_open(conn, company_id, entry_d.get("entry_date", ""))

    conn.execute("DELETE FROM accounting_entry_lines WHERE entry_id = ?", (entry_id,))
    conn.execute("DELETE FROM accounting_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# =====================================================
# RELATÓRIOS CONTÁBEIS
# =====================================================

@router.get("/api/accounting/razao")
def razao_contabil(
    account_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Razão Contábil — extrato de movimentações de uma conta."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    today = date.today()
    s_date = start_date or date(today.year, 1, 1).isoformat()
    e_date = end_date or today.isoformat()

    acc = conn.execute(
        "SELECT * FROM accounting_accounts WHERE id = ? AND company_id = ?",
        (account_id, company_id)
    ).fetchone()
    if not acc:
        conn.close()
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    acc_dict = dict(acc)
    lines = rows_to_dicts(conn.execute("""
        SELECT l.debit, l.credit, l.description as line_desc,
               e.entry_date, e.description as entry_desc, e.document_number, e.id as entry_id
        FROM accounting_entry_lines l
        JOIN accounting_entries e ON e.id = l.entry_id
        WHERE l.account_id = ? AND e.company_id = ? AND e.entry_date BETWEEN ? AND ?
        ORDER BY e.entry_date, e.id
    """, (account_id, company_id, s_date, e_date)).fetchall())
    conn.close()

    saldo = 0.0
    is_devedora = acc_dict["nature"] == "devedora"
    movimentos = []
    for ln in lines:
        debit = float(ln["debit"] or 0)
        credit = float(ln["credit"] or 0)
        if is_devedora:
            saldo += debit - credit
        else:
            saldo += credit - debit
        movimentos.append({**ln, "saldo_acumulado": round(saldo, 2)})

    return {
        "account": acc_dict,
        "period": {"start": s_date, "end": e_date},
        "movements": movimentos,
        "total_debit": round(sum(float(ln["debit"] or 0) for ln in lines), 2),
        "total_credit": round(sum(float(ln["credit"] or 0) for ln in lines), 2),
        "saldo_final": round(saldo, 2),
    }


@router.get("/api/accounting/balancete")
def balancete(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Balancete de Verificação — saldos de todas as contas no período."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    today = date.today()
    s_date = start_date or date(today.year, 1, 1).isoformat()
    e_date = end_date or today.isoformat()

    accounts = rows_to_dicts(conn.execute(
        "SELECT * FROM accounting_accounts WHERE company_id = ? AND active = 1 ORDER BY code",
        (company_id,)
    ).fetchall())

    result = []
    total_debit = total_credit = 0.0
    for acc in accounts:
        totals = conn.execute("""
            SELECT COALESCE(SUM(l.debit), 0) as total_debit,
                   COALESCE(SUM(l.credit), 0) as total_credit
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            WHERE l.account_id = ? AND e.company_id = ? AND e.entry_date BETWEEN ? AND ?
        """, (acc["id"], company_id, s_date, e_date)).fetchone()

        d = float(totals["total_debit"])
        c = float(totals["total_credit"])
        is_devedora = acc["nature"] == "devedora"
        saldo = round((d - c) if is_devedora else (c - d), 2)

        total_debit += d
        total_credit += c
        result.append({
            "code": acc["code"],
            "name": acc["name"],
            "account_type": acc["account_type"],
            "nature": acc["nature"],
            "total_debit": round(d, 2),
            "total_credit": round(c, 2),
            "saldo": saldo,
        })

    conn.close()
    return {
        "period": {"start": s_date, "end": e_date},
        "accounts": result,
        "totals": {
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
        }
    }


def _compute_dre_data(conn, company_id: int, s_date: str, e_date: str) -> Dict[str, Any]:
    """Calcula a DRE do período desconsiderando lançamentos de encerramento (ARE)."""
    def saldo_tipo(tipo: str, code_prefix: Optional[str] = None, exclude_prefix: Optional[str] = None) -> float:
        q = """
            SELECT a.nature,
                   COALESCE(SUM(l.debit), 0) as td,
                   COALESCE(SUM(l.credit), 0) as tc
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE a.account_type = ? AND a.company_id = ?
              AND e.entry_date BETWEEN ? AND ?
              AND COALESCE(e.entry_type, '') != 'encerramento'
        """
        params: List[Any] = [tipo, company_id, s_date, e_date]
        if code_prefix:
            q += " AND a.code LIKE ?"
            params.append(f"{code_prefix}%")
        if exclude_prefix:
            q += " AND a.code NOT LIKE ?"
            params.append(f"{exclude_prefix}%")
        q += " GROUP BY a.nature"
        rows = conn.execute(q, params).fetchall()
        total = 0.0
        for r in rows:
            d, c = float(r["td"]), float(r["tc"])
            total += (c - d) if r["nature"] == "credora" else (d - c)
        return round(total, 2)

    receita_bruta = saldo_tipo("receita", exclude_prefix="3.2")
    deducoes = saldo_tipo("receita", code_prefix="3.2")
    receita_liquida = round(receita_bruta - deducoes, 2)
    cmv = saldo_tipo("custo")
    lucro_bruto = round(receita_liquida - cmv, 2)
    despesas = saldo_tipo("despesa")
    lucro_operacional = round(lucro_bruto - despesas, 2)
    lucro_liquido = round(lucro_operacional, 2)

    return {
        "period": {"start": s_date, "end": e_date},
        "receita_bruta": receita_bruta,
        "deducoes_receita": deducoes,
        "receita_liquida": receita_liquida,
        "custo_mercadorias_servicos": cmv,
        "lucro_bruto": lucro_bruto,
        "despesas_operacionais": despesas,
        "lucro_operacional": lucro_operacional,
        "resultado_financeiro": 0.0,
        "lucro_liquido": lucro_liquido,
    }


def _compute_balanco_data(conn, company_id: int, r_date: str) -> Dict[str, Any]:
    """Calcula o Balanço Patrimonial acumulado até ref_date."""
    def saldo_conta(account_id: int, nature: str) -> float:
        row = conn.execute("""
            SELECT COALESCE(SUM(l.debit), 0) as td, COALESCE(SUM(l.credit), 0) as tc
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            WHERE l.account_id = ? AND e.company_id = ? AND e.entry_date <= ?
        """, (account_id, company_id, r_date)).fetchone()
        d, c = float(row["td"]), float(row["tc"])
        return round((d - c) if nature == "devedora" else (c - d), 2)

    def grupo(tipo: str) -> Dict[str, Any]:
        accounts = rows_to_dicts(conn.execute(
            "SELECT * FROM accounting_accounts WHERE account_type = ? AND company_id = ? AND active = 1 ORDER BY code",
            (tipo, company_id)
        ).fetchall())
        total = 0.0
        items = []
        for acc in accounts:
            s = saldo_conta(acc["id"], acc["nature"])
            if s != 0:
                items.append({"code": acc["code"], "name": acc["name"], "saldo": s})
                total += s
        return {"items": items, "total": round(total, 2)}

    ativo = grupo("ativo")
    passivo = grupo("passivo")
    pl = grupo("patrimonio_liquido")
    passivo_total = round(passivo["total"] + pl["total"], 2)
    return {
        "ref_date": r_date,
        "ativo": ativo,
        "passivo": passivo,
        "patrimonio_liquido": pl,
        "passivo_total": passivo_total,
        "balanceado": abs(ativo["total"] - passivo_total) < 0.02,
    }


@router.get("/api/accounting/dre")
def dre_contabil(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """DRE — Demonstrativo de Resultado do Exercício."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    today = date.today()
    s_date = start_date or date(today.year, 1, 1).isoformat()
    e_date = end_date or today.isoformat()
    res = _compute_dre_data(conn, company_id, s_date, e_date)
    conn.close()
    return res


@router.get("/api/accounting/balanco")
def balanco_patrimonial(
    ref_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Balanço Patrimonial — posição em uma data de referência."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    r_date = ref_date or date.today().isoformat()
    res = _compute_balanco_data(conn, company_id, r_date)
    conn.close()
    return res


# =====================================================
# SPED CONTÁBIL (ECD) E LIVRO DIÁRIO
# =====================================================

@router.get("/api/accounting/livro-diario")
def livro_diario(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Livro Diário — todos os lançamentos do período com suas partidas."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    today = date.today()
    s_date = start_date or date(today.year, 1, 1).isoformat()
    e_date = end_date or today.isoformat()

    entries = rows_to_dicts(conn.execute("""
        SELECT * FROM accounting_entries
        WHERE company_id = ? AND entry_date BETWEEN ? AND ?
        ORDER BY entry_date, id
    """, (company_id, s_date, e_date)).fetchall())

    for entry in entries:
        entry["lines"] = rows_to_dicts(conn.execute("""
            SELECT l.*, a.code as account_code, a.name as account_name
            FROM accounting_entry_lines l
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE l.entry_id = ?
            ORDER BY l.id
        """, (entry["id"],)).fetchall())

    total_d = sum(float(e.get("total_debit") or 0) for e in entries)
    total_c = sum(float(e.get("total_credit") or 0) for e in entries)
    conn.close()
    return {
        "period": {"start": s_date, "end": e_date},
        "total_entries": len(entries),
        "total_debit": round(total_d, 2),
        "total_credit": round(total_c, 2),
        "entries": entries,
    }


@router.get("/api/accounting/ecd")
def download_ecd(
    year: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Gera e faz download do arquivo SPED Contábil (ECD) em formato .txt."""
    from fastapi.responses import Response as FResponse
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    today = date.today()
    ano = year or today.year
    s_date = start_date or f"{ano}-01-01"
    e_date = end_date or f"{ano}-12-31"

    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())

    # Contas com totais de movimentação
    accounts = rows_to_dicts(conn.execute(
        "SELECT * FROM accounting_accounts WHERE company_id = ? AND active = 1 ORDER BY code",
        (company_id,)
    ).fetchall())

    for acc in accounts:
        totals = conn.execute("""
            SELECT COALESCE(SUM(l.debit), 0) as td, COALESCE(SUM(l.credit), 0) as tc
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            WHERE l.account_id = ? AND e.company_id = ? AND e.entry_date BETWEEN ? AND ?
        """, (acc["id"], company_id, s_date, e_date)).fetchone()
        acc["_total_debit"] = float(totals["td"])
        acc["_total_credit"] = float(totals["tc"])

    # Lançamentos com linhas
    entries = rows_to_dicts(conn.execute("""
        SELECT * FROM accounting_entries
        WHERE company_id = ? AND entry_date BETWEEN ? AND ?
        ORDER BY entry_date, id
    """, (company_id, s_date, e_date)).fetchall())

    for entry in entries:
        entry["lines"] = rows_to_dicts(conn.execute("""
            SELECT l.*, a.code as account_code
            FROM accounting_entry_lines l
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE l.entry_id = ?
        """, (entry["id"],)).fetchall())

    conn.close()

    content = EcdGenerator.generate(company, accounts, entries, s_date, e_date, ano)
    cnpj_clean = "".join(c for c in company.get("cnpj", "00000000000000") if c.isdigit())
    filename = f"ECD_SPED_Contabil_{cnpj_clean}_{ano}.txt"

    return FResponse(
        content=content.encode("latin1", errors="replace"),
        media_type="text/plain; charset=latin1",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =====================================================
# ENCERRAMENTO DE EXERCÍCIO (ARE) & BLOQUEIO DE PERÍODO
# =====================================================

@router.get("/api/accounting/periods")
def list_periods(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Lista os períodos contábeis encerrados/abertos da empresa."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM accounting_periods WHERE company_id = ? ORDER BY end_date DESC",
        (company_id,),
    ).fetchall())
    conn.close()
    return rows


@router.post("/api/accounting/close-period")
def close_period(
    data: ClosePeriodPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Executa o encerramento formal do exercício (ARE) zerando contas de resultado contra 2.3.03 e bloqueando o período."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()

    # Remove eventual ARE anterior do mesmo end_date para evitar duplicação
    prev = conn.execute(
        "SELECT id, are_entry_id FROM accounting_periods WHERE company_id = ? AND end_date = ?",
        (company_id, data.end_date),
    ).fetchone()
    if prev and prev["are_entry_id"]:
        cur.execute("DELETE FROM accounting_entry_lines WHERE entry_id = ?", (prev["are_entry_id"],))
        cur.execute("DELETE FROM accounting_entries WHERE id = ?", (prev["are_entry_id"],))

    # Garante conta 2.3.03 (Lucros ou Prejuízos Acumulados)
    acc_2303 = conn.execute(
        "SELECT id FROM accounting_accounts WHERE company_id = ? AND code = '2.3.03' LIMIT 1",
        (company_id,),
    ).fetchone()
    if not acc_2303:
        cur.execute("""
            INSERT INTO accounting_accounts
                (company_id, code, name, account_type, nature, parent_code, accepts_entries, active)
            VALUES (?, '2.3.03', 'Lucros ou Prejuízos Acumulados', 'patrimonio_liquido', 'credora', '2.3', 1, 1)
        """, (company_id,))
        acc_2303_id = cur.lastrowid
    else:
        acc_2303_id = acc_2303["id"]

    result_accounts = rows_to_dicts(conn.execute("""
        SELECT id, code, name, account_type, nature
        FROM accounting_accounts
        WHERE company_id = ? AND active = 1 AND accepts_entries = 1
          AND account_type IN ('receita', 'custo', 'despesa')
        ORDER BY code
    """, (company_id,)).fetchall())

    closing_lines: List[Dict[str, Any]] = []
    tot_deb_res = 0.0
    tot_cred_res = 0.0
    for acc in result_accounts:
        row = conn.execute("""
            SELECT COALESCE(SUM(l.debit), 0) as td, COALESCE(SUM(l.credit), 0) as tc
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            WHERE l.account_id = ? AND e.company_id = ?
              AND e.entry_date BETWEEN ? AND ?
              AND COALESCE(e.entry_type, '') != 'encerramento'
        """, (acc["id"], company_id, data.start_date, data.end_date)).fetchone()
        net = round(float(row["td"]) - float(row["tc"]), 2)
        if abs(net) < 0.01:
            continue
        if net > 0:
            # Conta com saldo devedor -> credita para zerar
            closing_lines.append({
                "account_id": acc["id"], "debit": 0.0, "credit": net,
                "description": f"Zeramento ARE {acc['code']} - {acc['name']}",
            })
            tot_deb_res = round(tot_deb_res + net, 2)
        else:
            val_c = abs(net)
            closing_lines.append({
                "account_id": acc["id"], "debit": val_c, "credit": 0.0,
                "description": f"Zeramento ARE {acc['code']} - {acc['name']}",
            })
            tot_cred_res = round(tot_cred_res + val_c, 2)

    lucro_prejuizo = round(tot_cred_res - tot_deb_res, 2)
    are_entry_id = None
    if closing_lines:
        if lucro_prejuizo > 0:
            closing_lines.append({
                "account_id": acc_2303_id, "debit": 0.0, "credit": lucro_prejuizo,
                "description": "Transferência de Lucro Líquido do Exercício (ARE)",
            })
        elif lucro_prejuizo < 0:
            closing_lines.append({
                "account_id": acc_2303_id, "debit": abs(lucro_prejuizo), "credit": 0.0,
                "description": "Transferência de Prejuízo do Exercício (ARE)",
            })
        tot_d = round(sum(ln["debit"] for ln in closing_lines), 2)
        tot_c = round(sum(ln["credit"] for ln in closing_lines), 2)
        if tot_d > 0 and abs(tot_d - tot_c) < 0.02:
            cur.execute("""
                INSERT INTO accounting_entries
                    (company_id, entry_date, description, document_number, entry_type, total_debit, total_credit)
                VALUES (?, ?, ?, ?, 'encerramento', ?, ?)
            """, (
                company_id,
                data.end_date,
                f"Encerramento do Exercício (ARE) {data.start_date} a {data.end_date}",
                f"ARE-{data.end_date[:4]}",
                tot_d,
                tot_c,
            ))
            are_entry_id = cur.lastrowid
            for ln in closing_lines:
                cur.execute("""
                    INSERT INTO accounting_entry_lines (entry_id, account_id, debit, credit, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (are_entry_id, ln["account_id"], ln["debit"], ln["credit"], ln["description"]))

    status_periodo = "fechado" if data.lock_period else "aberto"
    closed_by = current_user.get("email", "admin")
    cur.execute("""
        INSERT OR REPLACE INTO accounting_periods
            (company_id, start_date, end_date, status, are_entry_id, lucro_prejuizo, closed_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, data.start_date, data.end_date, status_periodo, are_entry_id, lucro_prejuizo, closed_by))
    period_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {
        "status": "ok",
        "period_id": period_id,
        "are_entry_id": are_entry_id,
        "lucro_prejuizo": lucro_prejuizo,
        "status_periodo": status_periodo,
    }


@router.post("/api/accounting/reopen-period/{period_id}")
def reopen_period(period_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Reabre um período contábil encerrado e estorna/remove o lançamento de ARE vinculado."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    period = conn.execute(
        "SELECT * FROM accounting_periods WHERE id = ? AND company_id = ?",
        (period_id, company_id),
    ).fetchone()
    if not period:
        conn.close()
        raise HTTPException(status_code=404, detail="Período contábil não encontrado.")

    are_id = period["are_entry_id"]
    if are_id:
        conn.execute("DELETE FROM accounting_entry_lines WHERE entry_id = ?", (are_id,))
        conn.execute("DELETE FROM accounting_entries WHERE id = ?", (are_id,))
    conn.execute(
        "UPDATE accounting_periods SET status = 'aberto', are_entry_id = NULL WHERE id = ?",
        (period_id,),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "period_id": period_id, "status_periodo": "aberto"}


# =====================================================
# DEMONSTRAÇÕES CONTÁBEIS AVANÇADAS (DFC, DMPL, NOTAS)
# =====================================================

def _compute_dfc_data(conn, company_id: int, s_date: str, e_date: str) -> Dict[str, Any]:
    """Calcula a DFC (Métodos Direto e Indireto) para o período informado."""
    def cash_balance(op: str, ref_dt: str) -> float:
        row = conn.execute(f"""
            SELECT COALESCE(SUM(l.debit - l.credit), 0)
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE e.company_id = ? AND e.entry_date {op} ?
              AND (a.code LIKE '1.1.01%' OR a.code LIKE '1.1.02%' OR a.code LIKE '1.1.03%')
        """, (company_id, ref_dt)).fetchone()
        return round(float(row[0] or 0.0), 2)

    def net_change(prefixes: tuple[str, ...], exclude: tuple[str, ...] = (), nature_credit: bool = False) -> float:
        like_clause = " OR ".join("a.code LIKE ?" for _ in prefixes)
        params: List[Any] = [company_id, s_date, e_date] + [f"{p}%" for p in prefixes]
        excl_clause = ""
        if exclude:
            excl_clause = " AND " + " AND ".join("a.code NOT LIKE ?" for _ in exclude)
            params.extend(f"{x}%" for x in exclude)
        expr = "l.credit - l.debit" if nature_credit else "l.debit - l.credit"
        row = conn.execute(f"""
            SELECT COALESCE(SUM({expr}), 0)
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE e.company_id = ? AND e.entry_date BETWEEN ? AND ?
              AND COALESCE(e.entry_type, '') != 'encerramento'
              AND ({like_clause}) {excl_clause}
        """, params).fetchone()
        return round(float(row[0] or 0.0), 2)

    saldo_inicial = cash_balance("<", s_date)
    saldo_final = cash_balance("<=", e_date)

    # Inspeção direta das partidas que movimentam Caixa/Equivalentes (1.1.01 / 1.1.02 / 1.1.03)
    entries = rows_to_dicts(conn.execute("""
        SELECT id FROM accounting_entries
        WHERE company_id = ? AND entry_date BETWEEN ? AND ?
          AND COALESCE(entry_type, '') != 'encerramento'
    """, (company_id, s_date, e_date)).fetchall())

    rec_clientes = 0.0
    pag_fornecedores = 0.0
    pag_pessoal_impostos = 0.0
    pag_desp_oper = 0.0
    ativ_invest = 0.0
    ativ_financ = 0.0
    has_cash_entries = False

    for ent in entries:
        lns = rows_to_dicts(conn.execute("""
            SELECT l.debit, l.credit, a.code, a.account_type
            FROM accounting_entry_lines l
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE l.entry_id = ?
        """, (ent["id"],)).fetchall())
        cash_delta = sum(float(ln["debit"] or 0) - float(ln["credit"] or 0)
                         for ln in lns if ln["code"].startswith(("1.1.01", "1.1.02", "1.1.03")))
        if abs(cash_delta) < 0.01:
            continue
        has_cash_entries = True
        non_cash = [ln for ln in lns if not ln["code"].startswith(("1.1.01", "1.1.02", "1.1.03"))]
        if any(ln["code"].startswith(("1.2.02", "1.2.03", "1.2.04")) for ln in non_cash):
            ativ_invest += cash_delta
        elif any(ln["code"].startswith(("2.1.04", "2.2", "2.3.01", "2.3.03")) for ln in non_cash):
            ativ_financ += cash_delta
        elif cash_delta > 0:
            rec_clientes += cash_delta
        else:
            outflow = abs(cash_delta)
            if any(ln["code"].startswith(("2.1.02", "2.1.03", "5.1")) for ln in non_cash):
                pag_pessoal_impostos += outflow
            elif any(ln["code"].startswith(("2.1.01", "4.1", "1.1.06")) for ln in non_cash):
                pag_fornecedores += outflow
            else:
                pag_desp_oper += outflow

    if not has_cash_entries:
        rec_fin = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM financial_entries WHERE company_id=? AND type='receita' AND status='pago' AND due_date BETWEEN ? AND ?",
            (company_id, s_date, e_date),
        ).fetchone()[0]
        desp_fin = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM financial_entries WHERE company_id=? AND type='despesa' AND status='pago' AND due_date BETWEEN ? AND ?",
            (company_id, s_date, e_date),
        ).fetchone()[0]
        rec_clientes = round(float(rec_fin or 0.0), 2)
        pag_fornecedores = round(float(desp_fin or 0.0), 2)

    rec_clientes = round(rec_clientes, 2)
    pag_fornecedores = round(pag_fornecedores, 2)
    pag_pessoal_impostos = round(pag_pessoal_impostos, 2)
    pag_desp_oper = round(pag_desp_oper, 2)
    ativ_invest = round(ativ_invest, 2)
    ativ_financ = round(ativ_financ, 2)
    caixa_op_direto = round(rec_clientes - pag_fornecedores - pag_pessoal_impostos - pag_desp_oper, 2)
    var_caixa_direto = round(caixa_op_direto + ativ_invest + ativ_financ, 2)

    # Método Indireto
    dre = _compute_dre_data(conn, company_id, s_date, e_date)
    lucro_liq = dre["lucro_liquido"]
    dep_amort = net_change(("5.5.01",))
    var_clientes = net_change(("1.1.04", "1.1.05", "1.1.07", "1.1.08", "1.1.09"))
    var_estoques = net_change(("1.1.06",))
    var_fornec_obrig = net_change(("2.1.01", "2.1.02", "2.1.03", "2.1.05"), nature_credit=True)
    caixa_op_indireto = round(lucro_liq + dep_amort - var_clientes - var_estoques + var_fornec_obrig, 2)
    inv_indireto = round(-net_change(("1.2.01", "1.2.02", "1.2.03", "1.2.04"), exclude=("1.2.03.04", "1.2.04.02")), 2)
    fin_indireto = round(net_change(("2.1.04", "2.2", "2.3.01"), nature_credit=True), 2)
    var_caixa_indireto = round(caixa_op_indireto + inv_indireto + fin_indireto, 2)

    return {
        "period": {"start": s_date, "end": e_date},
        "saldo_inicial_caixa": saldo_inicial,
        "saldo_final_caixa": saldo_final if has_cash_entries else round(saldo_inicial + var_caixa_direto, 2),
        "variacao_liquida_caixa": round(saldo_final - saldo_inicial, 2) if has_cash_entries else var_caixa_direto,
        "metodo_direto": {
            "recebimentos_clientes": rec_clientes,
            "pagamentos_fornecedores": pag_fornecedores,
            "pagamentos_pessoal_impostos": pag_pessoal_impostos,
            "pagamentos_despesas_operacionais": pag_desp_oper,
            "caixa_liquido_operacional": caixa_op_direto,
            "atividades_investimento": ativ_invest,
            "atividades_financiamento": ativ_financ,
            "variacao_liquida_caixa": var_caixa_direto,
        },
        "metodo_indireto": {
            "lucro_liquido_exercicio": lucro_liq,
            "depreciacao_amortizacao": dep_amort,
            "variacao_clientes": round(-var_clientes, 2),
            "variacao_estoques": round(-var_estoques, 2),
            "variacao_fornecedores_obrigacoes": var_fornec_obrig,
            "caixa_liquido_operacional": caixa_op_indireto,
            "atividades_investimento": inv_indireto,
            "atividades_financiamento": fin_indireto,
            "variacao_liquida_caixa": var_caixa_indireto,
        },
    }


def _compute_dmpl_data(conn, company_id: int, yr: int) -> Dict[str, Any]:
    """Calcula a DMPL (Demonstração das Mutações do Patrimônio Líquido) e DLPA do ano."""
    s_date, e_date = f"{yr}-01-01", f"{yr}-12-31"

    def pl_mov(code_prefix: str, cond: str, params_extra: tuple, excl_closing: bool = False) -> float:
        q = f"""
            SELECT COALESCE(SUM(l.credit - l.debit), 0)
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE e.company_id = ? AND a.code LIKE ? AND {cond}
        """
        if excl_closing:
            q += " AND COALESCE(e.entry_type, '') != 'encerramento'"
        row = conn.execute(q, (company_id, f"{code_prefix}%", *params_extra)).fetchone()
        return round(float(row[0] or 0.0), 2)

    cap_ini = pl_mov("2.3.01", "e.entry_date < ?", (s_date,))
    res_ini = pl_mov("2.3.02", "e.entry_date < ?", (s_date,))
    luc_ini = pl_mov("2.3.03", "e.entry_date < ?", (s_date,))

    cap_aum = pl_mov("2.3.01", "e.entry_date BETWEEN ? AND ?", (s_date, e_date), excl_closing=True)
    res_mov = pl_mov("2.3.02", "e.entry_date BETWEEN ? AND ?", (s_date, e_date), excl_closing=True)
    luc_outros = pl_mov("2.3.03", "e.entry_date BETWEEN ? AND ?", (s_date, e_date), excl_closing=True)

    dre = _compute_dre_data(conn, company_id, s_date, e_date)
    lucro_ex = dre["lucro_liquido"]

    def _row(desc: str, cap: float, res: float, luc: float) -> Dict[str, Any]:
        return {
            "descricao": desc,
            "capital_social": round(cap, 2),
            "reservas_lucros": round(res, 2),
            "lucros_prejuizos_acumulados": round(luc, 2),
            "total_pl": round(cap + res + luc, 2),
        }

    rows = [
        _row("Saldo Inicial do Exercício", cap_ini, res_ini, luc_ini),
        _row("Aumento / Integralização de Capital", cap_aum, 0.0, 0.0),
        _row("Lucro / Prejuízo Líquido do Exercício", 0.0, 0.0, lucro_ex),
        _row("Constituição de Reservas de Lucros", 0.0, res_mov, 0.0),
        _row("Dividendos / Outras Destinações", 0.0, 0.0, luc_outros),
    ]
    cap_fin = round(cap_ini + cap_aum, 2)
    res_fin = round(res_ini + res_mov, 2)
    luc_fin = round(luc_ini + lucro_ex + luc_outros, 2)
    rows.append(_row("Saldo Final do Exercício", cap_fin, res_fin, luc_fin))

    return {
        "year": yr,
        "rows": rows,
        "dlpa": {
            "saldo_inicial": luc_ini,
            "lucro_prejuizo_exercicio": lucro_ex,
            "destinacoes_dividendos": luc_outros,
            "saldo_final": luc_fin,
        },
        "saldo_final_pl": round(cap_fin + res_fin + luc_fin, 2),
    }


@router.get("/api/accounting/dfc")
def dfc_demonstracao(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """DFC — Demonstração dos Fluxos de Caixa (Métodos Direto e Indireto — CPC 03)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    today = date.today()
    s_date = start_date or date(today.year, 1, 1).isoformat()
    e_date = end_date or today.isoformat()
    res = _compute_dfc_data(conn, company_id, s_date, e_date)
    conn.close()
    return res


@router.get("/api/accounting/dmpl")
def dmpl_demonstracao(
    year: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """DMPL (Demonstração das Mutações do Patrimônio Líquido) e DLPA."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    yr = year or date.today().year
    res = _compute_dmpl_data(conn, company_id, yr)
    conn.close()
    return res


@router.get("/api/accounting/notas-explicativas")
def list_notas_explicativas(
    year: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Lista Notas Explicativas da empresa no exercício (com seed automático padrão NBC TG)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    yr = year or date.today().year
    comp = conn.execute("SELECT razao_social, regime_tributario FROM companies WHERE id = ?", (company_id,)).fetchone()
    _seed_default_notes(
        conn, company_id, yr,
        comp["razao_social"] if comp else "Empresa",
        comp["regime_tributario"] if comp else "simples_nacional",
    )
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM accounting_notes WHERE company_id = ? AND year = ? ORDER BY number",
        (company_id, yr),
    ).fetchall())
    conn.close()
    return rows


@router.post("/api/accounting/notas-explicativas")
def upsert_nota_explicativa(
    data: AccountingNotePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Cria ou atualiza uma Nota Explicativa do exercício."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("""
        INSERT OR REPLACE INTO accounting_notes (company_id, year, number, title, content)
        VALUES (?, ?, ?, ?, ?)
    """, (company_id, data.year, data.number, data.title, data.content))
    conn.commit()
    row = dict(conn.execute(
        "SELECT * FROM accounting_notes WHERE company_id = ? AND year = ? AND number = ?",
        (company_id, data.year, data.number),
    ).fetchone())
    conn.close()
    return row


@router.get("/api/accounting/relatorio-demonstracoes-html", response_class=HTMLResponse)
def relatorio_demonstracoes_html(
    year: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Gera o caderno completo imprimível: BP, DRE, DFC, DMPL, Notas Explicativas e Carta de Responsabilidade."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    yr = year or date.today().year
    s_date, e_date = f"{yr}-01-01", f"{yr}-12-31"
    comp = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    bp = _compute_balanco_data(conn, company_id, e_date)
    dre = _compute_dre_data(conn, company_id, s_date, e_date)
    dfc = _compute_dfc_data(conn, company_id, s_date, e_date)
    dmpl = _compute_dmpl_data(conn, company_id, yr)
    _seed_default_notes(conn, company_id, yr, comp.get("razao_social") or "Empresa", comp.get("regime_tributario") or "")
    notas = rows_to_dicts(conn.execute(
        "SELECT * FROM accounting_notes WHERE company_id = ? AND year = ? ORDER BY number",
        (company_id, yr),
    ).fetchall())
    conn.close()

    def _fmt(v: float) -> str:
        return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    esc = html_lib.escape
    bp_ativo_rows = "".join(
        f"<tr><td>{esc(i['code'])} — {esc(i['name'])}</td><td class='num'>{_fmt(i['saldo'])}</td></tr>"
        for i in bp["ativo"]["items"]
    ) or "<tr><td colspan='2'>Sem saldos no período</td></tr>"
    bp_pass_rows = "".join(
        f"<tr><td>{esc(i['code'])} — {esc(i['name'])}</td><td class='num'>{_fmt(i['saldo'])}</td></tr>"
        for i in (bp["passivo"]["items"] + bp["patrimonio_liquido"]["items"])
    ) or "<tr><td colspan='2'>Sem saldos no período</td></tr>"
    dmpl_rows = "".join(
        f"<tr><td>{esc(r['descricao'])}</td><td class='num'>{_fmt(r['capital_social'])}</td>"
        f"<td class='num'>{_fmt(r['reservas_lucros'])}</td><td class='num'>{_fmt(r['lucros_prejuizos_acumulados'])}</td>"
        f"<td class='num'><strong>{_fmt(r['total_pl'])}</strong></td></tr>"
        for r in dmpl["rows"]
    )
    notas_html = "".join(
        f"<div class='nota'><h4>Nota {n['number']} — {esc(n['title'])}</h4><p>{esc(n['content'])}</p></div>"
        for n in notas
    )
    md = dfc["metodo_direto"]
    mi = dfc["metodo_indireto"]

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"/>
<title>Demonstrações Contábeis {yr} — {esc(comp.get('razao_social', ''))}</title>
<style>
  body {{ font-family: Arial, sans-serif; color: #1e293b; max-width: 960px; margin: 24px auto; padding: 0 20px; line-height: 1.45; }}
  h1, h2, h3 {{ color: #0f172a; margin-top: 24px; }}
  .hdr {{ border-bottom: 2px solid #0f172a; padding-bottom: 12px; display: flex; justify-content: space-between; align-items: flex-end; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0 20px; font-size: 13px; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 6px 10px; text-align: left; }}
  th {{ background: #f1f5f9; }}
  .num {{ text-align: right; font-family: monospace; }}
  .tot {{ font-weight: bold; background: #f8fafc; }}
  .nota {{ margin-bottom: 12px; padding: 10px; border-left: 3px solid #4f46e5; background: #f8fafc; }}
  .carta {{ margin-top: 28px; padding: 16px; border: 1px solid #cbd5e1; background: #fff; }}
  .sigs {{ display: flex; justify-content: space-between; gap: 32px; margin-top: 40px; }}
  .sig {{ flex: 1; border-top: 1px solid #334155; padding-top: 6px; text-align: center; font-size: 12px; }}
  @media print {{ .no-print {{ display: none; }} }}
</style></head><body>
<div class="no-print" style="margin-bottom:14px;"><button onclick="window.print()" style="padding:8px 16px;background:#4f46e5;color:#fff;border:0;border-radius:6px;cursor:pointer;">Imprimir / Salvar PDF</button></div>
<div class="hdr">
  <div><h1 style="margin:0;">Caderno de Demonstrações Contábeis — Exercício {yr}</h1>
  <div><strong>{esc(comp.get('razao_social', ''))}</strong> · CNPJ: {esc(comp.get('cnpj', ''))}</div></div>
  <div>Data-base: 31/12/{yr}</div>
</div>

<h2>1. Balanço Patrimonial em 31/12/{yr}</h2>
<table><thead><tr><th>Ativo</th><th class="num">Saldo</th></tr></thead><tbody>{bp_ativo_rows}
<tr class="tot"><td>Total do Ativo</td><td class="num">{_fmt(bp['ativo']['total'])}</td></tr></tbody></table>
<table><thead><tr><th>Passivo e Patrimônio Líquido</th><th class="num">Saldo</th></tr></thead><tbody>{bp_pass_rows}
<tr class="tot"><td>Total do Passivo + Patrimônio Líquido</td><td class="num">{_fmt(bp['passivo_total'])}</td></tr></tbody></table>

<h2>2. Demonstração do Resultado do Exercício (DRE)</h2>
<table><tbody>
  <tr><td>Receita Operacional Bruta</td><td class="num">{_fmt(dre['receita_bruta'])}</td></tr>
  <tr><td>(-) Deduções da Receita</td><td class="num">{_fmt(-dre['deducoes_receita'])}</td></tr>
  <tr class="tot"><td>(=) Receita Operacional Líquida</td><td class="num">{_fmt(dre['receita_liquida'])}</td></tr>
  <tr><td>(-) Custo das Mercadorias/Serviços (CMV/CSP)</td><td class="num">{_fmt(-dre['custo_mercadorias_servicos'])}</td></tr>
  <tr class="tot"><td>(=) Lucro Bruto</td><td class="num">{_fmt(dre['lucro_bruto'])}</td></tr>
  <tr><td>(-) Despesas Operacionais</td><td class="num">{_fmt(-dre['despesas_operacionais'])}</td></tr>
  <tr class="tot"><td>(=) Lucro / Prejuízo Líquido do Exercício</td><td class="num">{_fmt(dre['lucro_liquido'])}</td></tr>
</tbody></table>

<h2>3. Demonstração dos Fluxos de Caixa (DFC — CPC 03)</h2>
<table><thead><tr><th>Método Direto</th><th class="num">Valor</th><th>Método Indireto</th><th class="num">Valor</th></tr></thead><tbody>
  <tr><td>Recebimentos de Clientes</td><td class="num">{_fmt(md['recebimentos_clientes'])}</td><td>Lucro Líquido do Exercício</td><td class="num">{_fmt(mi['lucro_liquido_exercicio'])}</td></tr>
  <tr><td>(-) Pagamentos a Fornecedores</td><td class="num">{_fmt(-md['pagamentos_fornecedores'])}</td><td>(+) Depreciação e Amortização</td><td class="num">{_fmt(mi['depreciacao_amortizacao'])}</td></tr>
  <tr><td>(-) Pessoal, Encargos e Tributos</td><td class="num">{_fmt(-md['pagamentos_pessoal_impostos'])}</td><td>(+/-) Variação Capital de Giro</td><td class="num">{_fmt(mi['variacao_clientes'] + mi['variacao_estoques'] + mi['variacao_fornecedores_obrigacoes'])}</td></tr>
  <tr class="tot"><td>Caixa Líquido Operacional</td><td class="num">{_fmt(md['caixa_liquido_operacional'])}</td><td>Caixa Líquido Operacional</td><td class="num">{_fmt(mi['caixa_liquido_operacional'])}</td></tr>
  <tr><td>Atividades de Investimento</td><td class="num">{_fmt(md['atividades_investimento'])}</td><td>Atividades de Investimento</td><td class="num">{_fmt(mi['atividades_investimento'])}</td></tr>
  <tr><td>Atividades de Financiamento</td><td class="num">{_fmt(md['atividades_financiamento'])}</td><td>Atividades de Financiamento</td><td class="num">{_fmt(mi['atividades_financiamento'])}</td></tr>
  <tr class="tot"><td>Saldo Final de Caixa</td><td class="num">{_fmt(dfc['saldo_final_caixa'])}</td><td>Variação Líquida de Caixa</td><td class="num">{_fmt(dfc['variacao_liquida_caixa'])}</td></tr>
</tbody></table>

<h2>4. Demonstração das Mutações do Patrimônio Líquido (DMPL / DLPA)</h2>
<table><thead><tr><th>Movimentação</th><th class="num">Capital Social</th><th class="num">Reservas</th><th class="num">Lucros/Prej. Acum.</th><th class="num">Total PL</th></tr></thead>
<tbody>{dmpl_rows}</tbody></table>

<h2>5. Notas Explicativas às Demonstrações Contábeis</h2>
{notas_html}

<div class="carta">
  <h3 style="margin-top:0;">6. Carta de Responsabilidade da Administração</h3>
  <p>A administração da sociedade <strong>{esc(comp.get('razao_social', ''))}</strong> declara que são de sua inteira responsabilidade as informações econômicas, financeiras e patrimoniais fornecidas à contabilidade para elaboração das Demonstrações Contábeis do exercício findo em 31/12/{yr}, inexistindo fraudes, passivos ocultos ou contingências relevantes não divulgadas.</p>
  <div class="sigs">
    <div class="sig"><strong>{esc(comp.get('razao_social', ''))}</strong><br/>Administrador / Representante Legal</div>
    <div class="sig"><strong>{esc(comp.get('contador_nome') or 'Contador Responsável')}</strong><br/>CRC: {esc(comp.get('contador_crc') or 'CRC-000000/O')}</div>
  </div>
</div>
</body></html>"""
    return HTMLResponse(content=html_doc)


# =====================================================
# PLANO REFERENCIAL RFB & HISTÓRICOS PADRÃO
# =====================================================

@router.post("/api/accounting/mapeamento-referencial/auto")
def auto_map_referencial(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Preenche automaticamente o código do Plano de Contas Referencial da RFB nas contas da empresa."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    accounts = rows_to_dicts(conn.execute(
        "SELECT id, code FROM accounting_accounts WHERE company_id = ?",
        (company_id,),
    ).fetchall())
    mapped = 0
    for acc in accounts:
        code = str(acc["code"] or "")
        ref_code = ""
        for prefix, ref in _REFERENCIAL_MAP:
            if code == prefix or code.startswith(f"{prefix}."):
                ref_code = ref
                break
        if ref_code:
            conn.execute("UPDATE accounting_accounts SET referencial_code = ? WHERE id = ?", (ref_code, acc["id"]))
            mapped += 1
    conn.commit()
    conn.close()
    return {"status": "ok", "mapped_count": mapped}


@router.get("/api/accounting/historicos-padrao")
def list_standard_histories(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Lista os históricos contábeis padrão da empresa (com seed automático se vazio)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _seed_standard_histories(conn, company_id)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM accounting_standard_histories WHERE company_id = ? ORDER BY code",
        (company_id,),
    ).fetchall())
    conn.close()
    return rows


@router.post("/api/accounting/historicos-padrao", status_code=201)
def create_standard_history(
    data: StandardHistoryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Cria ou atualiza um histórico padrão de lançamento rápido."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("""
        INSERT OR REPLACE INTO accounting_standard_histories
            (company_id, code, description, debit_account_code, credit_account_code)
        VALUES (?, ?, ?, ?, ?)
    """, (company_id, data.code, data.description, data.debit_account_code, data.credit_account_code))
    conn.commit()
    row = dict(conn.execute(
        "SELECT * FROM accounting_standard_histories WHERE company_id = ? AND code = ?",
        (company_id, data.code),
    ).fetchone())
    conn.close()
    return row


@router.post("/api/accounting/entries/from-standard", status_code=201)
def create_entry_from_standard(
    data: EntryFromStandardPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Gera um lançamento contábil por partidas dobradas a partir de um Histórico Padrão."""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero.")
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _check_period_open(conn, company_id, data.entry_date)
    _seed_standard_histories(conn, company_id)

    hist = conn.execute(
        "SELECT * FROM accounting_standard_histories WHERE company_id = ? AND code = ?",
        (company_id, data.history_code),
    ).fetchone()
    if not hist:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Histórico padrão '{data.history_code}' não encontrado.")

    deb_acc = conn.execute(
        "SELECT id FROM accounting_accounts WHERE company_id = ? AND code = ? AND active = 1",
        (company_id, hist["debit_account_code"]),
    ).fetchone()
    cred_acc = conn.execute(
        "SELECT id FROM accounting_accounts WHERE company_id = ? AND code = ? AND active = 1",
        (company_id, hist["credit_account_code"]),
    ).fetchone()
    if not deb_acc or not cred_acc:
        conn.close()
        raise HTTPException(status_code=400, detail="Contas do histórico padrão não encontradas no plano de contas.")

    desc = f"{hist['description']}{(' — ' + data.complement) if data.complement else ''}"
    amt = round(float(data.amount), 2)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO accounting_entries
            (company_id, entry_date, description, document_number, entry_type, total_debit, total_credit)
        VALUES (?, ?, ?, ?, 'manual', ?, ?)
    """, (company_id, data.entry_date, desc, data.document_number or "", amt, amt))
    entry_id = cur.lastrowid
    cur.execute("""
        INSERT INTO accounting_entry_lines (entry_id, account_id, debit, credit, description, cost_center_id)
        VALUES (?, ?, ?, 0.0, ?, ?)
    """, (entry_id, deb_acc["id"], amt, desc, data.cost_center_id))
    cur.execute("""
        INSERT INTO accounting_entry_lines (entry_id, account_id, debit, credit, description, cost_center_id)
        VALUES (?, ?, 0.0, ?, ?, ?)
    """, (entry_id, cred_acc["id"], amt, desc, data.cost_center_id))
    conn.commit()
    conn.close()
    return get_entry(entry_id, current_user)

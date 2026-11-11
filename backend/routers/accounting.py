from datetime import date
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query

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
            (company_id, code, name, account_type, nature, parent_code, accepts_entries, description, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (company_id, data.code, data.name, data.account_type, data.nature,
          data.parent_code or "", int(data.accepts_entries), data.description or ""))
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
            INSERT INTO accounting_entry_lines (entry_id, account_id, debit, credit, description)
            VALUES (?, ?, ?, ?, ?)
        """, (entry_id, line.account_id, line.debit or 0.0, line.credit or 0.0, line.description or ""))

    conn.commit()
    conn.close()
    return get_entry(entry_id, current_user)


@router.delete("/api/accounting/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove um lançamento contábil (apenas manuais)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    entry = conn.execute(
        "SELECT * FROM accounting_entries WHERE id = ? AND company_id = ?",
        (entry_id, company_id)
    ).fetchone()
    if not entry:
        conn.close()
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
    if dict(entry).get("entry_type") == "automatico":
        conn.close()
        raise HTTPException(status_code=400, detail="Lançamentos automáticos não podem ser excluídos manualmente.")

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

    def saldo_tipo(tipo: str) -> float:
        rows = conn.execute("""
            SELECT a.nature,
                   COALESCE(SUM(l.debit), 0) as td,
                   COALESCE(SUM(l.credit), 0) as tc
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE a.account_type = ? AND a.company_id = ?
              AND e.entry_date BETWEEN ? AND ?
            GROUP BY a.nature
        """, (tipo, company_id, s_date, e_date)).fetchall()
        total = 0.0
        for r in rows:
            d, c = float(r["td"]), float(r["tc"])
            total += (c - d) if r["nature"] == "credora" else (d - c)
        return round(total, 2)

    receita_bruta = saldo_tipo("receita")
    deducoes = saldo_tipo("deducao_receita") if False else 0.0  # conta futura
    receita_liquida = round(receita_bruta - deducoes, 2)
    cmv = saldo_tipo("custo")
    lucro_bruto = round(receita_liquida - cmv, 2)
    despesas = saldo_tipo("despesa")
    lucro_operacional = round(lucro_bruto - despesas, 2)

    # Receitas e despesas financeiras separadas via account_type
    rec_fin = sum(
        (float(r["tc"]) - float(r["td"]))
        for r in conn.execute("""
            SELECT COALESCE(SUM(l.debit), 0) as td, COALESCE(SUM(l.credit), 0) as tc
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            JOIN accounting_accounts a ON a.id = l.account_id
            WHERE a.account_type = 'receita' AND a.nature = 'credora'
              AND a.code LIKE '3.3%' AND a.company_id = ?
              AND e.entry_date BETWEEN ? AND ?
        """, (company_id, s_date, e_date)).fetchall()
    ) if False else 0.0

    lucro_liquido = round(lucro_operacional + rec_fin, 2)
    conn.close()

    return {
        "period": {"start": s_date, "end": e_date},
        "receita_bruta": receita_bruta,
        "deducoes_receita": deducoes,
        "receita_liquida": receita_liquida,
        "custo_mercadorias_servicos": cmv,
        "lucro_bruto": lucro_bruto,
        "despesas_operacionais": despesas,
        "lucro_operacional": lucro_operacional,
        "resultado_financeiro": rec_fin,
        "lucro_liquido": lucro_liquido,
    }


@router.get("/api/accounting/balanco")
def balanco_patrimonial(
    ref_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Balanço Patrimonial — posição em uma data de referência."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    r_date = ref_date or date.today().isoformat()

    def saldo_conta(account_id: int, nature: str) -> float:
        row = conn.execute("""
            SELECT COALESCE(SUM(l.debit), 0) as td, COALESCE(SUM(l.credit), 0) as tc
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            WHERE l.account_id = ? AND e.company_id = ? AND e.entry_date <= ?
        """, (account_id, company_id, r_date)).fetchone()
        d, c = float(row["td"]), float(row["tc"])
        return round((d - c) if nature == "devedora" else (c - d), 2)

    def grupo(tipo: str):
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
    conn.close()

    return {
        "ref_date": r_date,
        "ativo": ativo,
        "passivo": passivo,
        "patrimonio_liquido": pl,
        "passivo_total": passivo_total,
        "balanceado": abs(ativo["total"] - passivo_total) < 0.02,
    }


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

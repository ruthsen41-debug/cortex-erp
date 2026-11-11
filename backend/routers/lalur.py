from datetime import date
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(tags=["LALUR"])

# Adições mais comuns ao lucro contábil (Art. 249 do RIR)
ADICOES_COMUNS = [
    "Resultado negativo de equivalência patrimonial",
    "Despesas com brindes",
    "Multas por infração de lei",
    "Provisão para contingências não dedutíveis",
    "Despesas com alimentação de sócios",
    "Amortização de ágio sem base legal",
    "Juros sobre capital próprio excedentes ao limite",
    "Perdas em operações não dedutíveis",
]

EXCLUSOES_COMUNS = [
    "Resultado positivo de equivalência patrimonial",
    "Lucros e dividendos recebidos (já tributados)",
    "Reversão de provisões adicionadas em períodos anteriores",
    "Juros sobre capital próprio recebidos",
    "Ganhos em variação cambial não realizados",
    "Depreciação acelerada incentivada",
    "Subvenções governamentais para investimento",
]


class LalurLancamento(BaseModel):
    tipo: str  # adicao, exclusao
    descricao: str
    valor: float
    ano: int
    trimestre: Optional[int] = None
    parte_b: int = 0  # 1 se controla saldo na Parte B
    parte_b_descricao: str = ""


class ParteBLancamento(BaseModel):
    descricao: str
    saldo_inicial: float = 0.0
    ano: int


@router.get("/api/lalur/lancamentos")
def list_lancamentos(
    ano: Optional[int] = None,
    tipo: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    yr = ano or date.today().year
    q = "SELECT * FROM lalur_lancamentos WHERE company_id=? AND ano=?"
    params: list = [company_id, yr]
    if tipo:
        q += " AND tipo=?"
        params.append(tipo)
    q += " ORDER BY tipo, id"
    rows = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    return rows


@router.post("/api/lalur/lancamentos")
def create_lancamento(body: LalurLancamento, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO lalur_lancamentos
        (company_id, tipo, descricao, valor, ano, trimestre, parte_b, parte_b_descricao)
        VALUES (?,?,?,?,?,?,?,?)
    """, (company_id, body.tipo, body.descricao, body.valor, body.ano,
          body.trimestre, body.parte_b, body.parte_b_descricao))
    lid = cur.lastrowid
    # Se controla Parte B, criar/atualizar saldo
    if body.parte_b and body.parte_b_descricao:
        existing = conn.execute(
            "SELECT id, saldo FROM lalur_parte_b WHERE company_id=? AND descricao=? AND ano=?",
            (company_id, body.parte_b_descricao, body.ano)
        ).fetchone()
        if existing:
            delta = body.valor if body.tipo == "adicao" else -body.valor
            conn.execute("UPDATE lalur_parte_b SET saldo=saldo+? WHERE id=?",
                         (delta, existing["id"]))
        else:
            saldo = body.valor if body.tipo == "adicao" else -body.valor
            conn.execute("""
                INSERT INTO lalur_parte_b (company_id, descricao, saldo, ano)
                VALUES (?,?,?,?)
            """, (company_id, body.parte_b_descricao, saldo, body.ano))
    conn.commit()
    conn.close()
    return {"id": lid, "message": "Lançamento LALUR criado."}


@router.delete("/api/lalur/lancamentos/{lid}")
def delete_lancamento(lid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM lalur_lancamentos WHERE id=? AND company_id=?", (lid, company_id))
    conn.commit()
    conn.close()
    return {"message": "Lançamento excluído."}


@router.get("/api/lalur/parte-b")
def list_parte_b(
    ano: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    yr = ano or date.today().year
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM lalur_parte_b WHERE company_id=? AND ano=? ORDER BY descricao",
        (company_id, yr)
    ).fetchall())
    conn.close()
    return rows


@router.post("/api/lalur/parte-b")
def create_parte_b(body: ParteBLancamento, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO lalur_parte_b (company_id, descricao, saldo, ano)
        VALUES (?,?,?,?)
    """, (company_id, body.descricao, body.saldo_inicial, body.ano))
    conn.commit()
    conn.close()
    return {"message": "Saldo Parte B salvo."}


@router.get("/api/lalur/apuracao")
def apuracao_lucro_real(
    ano: Optional[int] = None,
    trimestre: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Apuração do Lucro Real com base nos lançamentos do LALUR."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    yr = ano or date.today().year

    # Lucro contábil do período
    s_date = f"{yr}-01-01"
    e_date = f"{yr}-12-31"
    if trimestre:
        months = {1: (1,3), 2: (4,6), 3: (7,9), 4: (10,12)}
        m1, m2 = months.get(trimestre, (1,12))
        import calendar
        last_day = calendar.monthrange(yr, m2)[1]
        s_date = f"{yr}-{m1:02d}-01"
        e_date = f"{yr}-{m2:02d}-{last_day:02d}"

    receitas = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM financial_entries WHERE company_id=? AND type='receita' AND status='pago' AND due_date BETWEEN ? AND ?",
        (company_id, s_date, e_date)
    ).fetchone()
    despesas = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM financial_entries WHERE company_id=? AND type='despesa' AND status='pago' AND due_date BETWEEN ? AND ?",
        (company_id, s_date, e_date)
    ).fetchone()
    lucro_contabil = float(receitas["t"] or 0) - float(despesas["t"] or 0)

    # Adições e Exclusões do LALUR
    q_base = "SELECT tipo, COALESCE(SUM(valor),0) as total FROM lalur_lancamentos WHERE company_id=? AND ano=?"
    params_base: list = [company_id, yr]
    if trimestre:
        q_base += " AND (trimestre=? OR trimestre IS NULL)"
        params_base.append(trimestre)
    q_base += " GROUP BY tipo"
    lancs = {r["tipo"]: float(r["total"]) for r in conn.execute(q_base, params_base).fetchall()}
    adicoes = lancs.get("adicao", 0)
    exclusoes = lancs.get("exclusao", 0)

    # Prejuízos a compensar (Parte B)
    prejuizos = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN saldo < 0 THEN ABS(saldo) ELSE 0 END),0) as t FROM lalur_parte_b WHERE company_id=? AND ano<?",
        (company_id, yr)
    ).fetchone()
    prejuizo_compensar = float(prejuizos["t"] or 0)
    limite_compensacao = max(0, (lucro_contabil + adicoes - exclusoes) * 0.3)
    compensacao = min(prejuizo_compensar, limite_compensacao)

    lucro_real = lucro_contabil + adicoes - exclusoes - compensacao
    base_positiva = max(0, lucro_real)

    # IRPJ
    irpj_15 = base_positiva * 0.15
    # Adicional: 10% sobre o que exceder R$20.000/mês (R$60.000 trim / R$240.000 anual)
    limite_add = 240000 if not trimestre else 60000
    irpj_add = max(0, base_positiva - limite_add) * 0.10
    # CSLL
    csll = base_positiva * 0.09

    conn.close()
    return {
        "ano": yr,
        "trimestre": trimestre,
        "periodo": f"{s_date} a {e_date}",
        "lucro_contabil": round(lucro_contabil, 2),
        "adicoes": round(adicoes, 2),
        "exclusoes": round(exclusoes, 2),
        "prejuizo_compensado": round(compensacao, 2),
        "lucro_real": round(lucro_real, 2),
        "base_calculo_positiva": round(base_positiva, 2),
        "irpj_15pct": round(irpj_15, 2),
        "irpj_adicional_10pct": round(irpj_add, 2),
        "irpj_total": round(irpj_15 + irpj_add, 2),
        "csll_9pct": round(csll, 2),
        "total_tributos": round(irpj_15 + irpj_add + csll, 2),
    }


@router.get("/api/lalur/sugestoes")
def get_sugestoes():
    return {"adicoes": ADICOES_COMUNS, "exclusoes": EXCLUSOES_COMUNS}

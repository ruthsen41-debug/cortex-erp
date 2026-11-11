import secrets
from datetime import date
import calendar
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

router = APIRouter(tags=["Honorários"])

SERVICOS_PADRAO = [
    "Escrita Contábil",
    "Escrita Fiscal",
    "Folha de Pagamento",
    "Abertura de Empresa",
    "Encerramento de Empresa",
    "Declaração IR Pessoa Física",
    "Declaração IR Pessoa Jurídica",
    "Regularização FGTS",
    "Consultoria Tributária",
    "Certidão Negativa",
    "Balanço Patrimonial",
    "DRE / Demonstrações Contábeis",
    "Atendimento Fiscalização",
    "Outros Serviços",
]


class HonorarioContrato(BaseModel):
    client_name: str
    cnpj_cpf: str = ""
    email: str = ""
    phone: str = ""
    regime: str = "simples_nacional"
    valor_mensal: float
    dia_vencimento: int = 10
    servicos: str = ""  # JSON list de serviços
    observacoes: str = ""
    ativo: int = 1


class HonorarioFatura(BaseModel):
    contrato_id: int
    competencia: str
    valor: float
    descricao: str = ""


@router.get("/api/honorarios/contratos")
def list_contratos(
    ativo: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    q = "SELECT * FROM honorarios_contratos WHERE company_id=?"
    params: list = [company_id]
    if ativo is not None:
        q += " AND ativo=?"
        params.append(ativo)
    q += " ORDER BY client_name"
    rows = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    return rows


@router.post("/api/honorarios/contratos")
def create_contrato(body: HonorarioContrato, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO honorarios_contratos
        (company_id, client_name, cnpj_cpf, email, phone, regime, valor_mensal,
         dia_vencimento, servicos, observacoes, ativo)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (company_id, body.client_name, body.cnpj_cpf, body.email, body.phone,
          body.regime, body.valor_mensal, body.dia_vencimento, body.servicos,
          body.observacoes, body.ativo))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": cid, "message": "Contrato de honorários criado."}


@router.put("/api/honorarios/contratos/{cid}")
def update_contrato(cid: int, body: HonorarioContrato, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("""
        UPDATE honorarios_contratos SET
        client_name=?, cnpj_cpf=?, email=?, phone=?, regime=?, valor_mensal=?,
        dia_vencimento=?, servicos=?, observacoes=?, ativo=?
        WHERE id=? AND company_id=?
    """, (body.client_name, body.cnpj_cpf, body.email, body.phone,
          body.regime, body.valor_mensal, body.dia_vencimento, body.servicos,
          body.observacoes, body.ativo, cid, company_id))
    conn.commit()
    conn.close()
    return {"message": "Contrato atualizado."}


@router.delete("/api/honorarios/contratos/{cid}")
def delete_contrato(cid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM honorarios_contratos WHERE id=? AND company_id=?", (cid, company_id))
    conn.commit()
    conn.close()
    return {"message": "Contrato excluído."}


@router.get("/api/honorarios/faturas")
def list_faturas(
    competencia: Optional[str] = None,
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    q = "SELECT f.*, c.client_name, c.email FROM honorarios_faturas f JOIN honorarios_contratos c ON c.id=f.contrato_id WHERE f.company_id=?"
    params: list = [company_id]
    if competencia:
        q += " AND f.competencia=?"
        params.append(competencia)
    if status:
        q += " AND f.status=?"
        params.append(status)
    q += " ORDER BY f.competencia DESC, c.client_name"
    rows = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    return rows


@router.post("/api/honorarios/faturar-mes")
def faturar_mes(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Gera faturas para todos os contratos ativos no mês."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    year, month = map(int, comp.split("-"))
    contratos = rows_to_dicts(conn.execute(
        "SELECT * FROM honorarios_contratos WHERE company_id=? AND ativo=1", (company_id,)
    ).fetchall())
    created = 0
    for c in contratos:
        # Check if already has fatura for this competencia
        exists = conn.execute(
            "SELECT id FROM honorarios_faturas WHERE company_id=? AND contrato_id=? AND competencia=?",
            (company_id, c["id"], comp)
        ).fetchone()
        if exists:
            continue
        last_day = calendar.monthrange(year, month)[1]
        due_date = f"{year}-{month:02d}-{min(c['dia_vencimento'], last_day):02d}"
        conn.execute("""
            INSERT INTO honorarios_faturas
            (company_id, contrato_id, competencia, valor, due_date, status, descricao)
            VALUES (?,?,?,?,?,?,?)
        """, (company_id, c["id"], comp, c["valor_mensal"], due_date,
              "pendente", f"Honorários {comp} — {c['client_name']}"))
        created += 1
    conn.commit()
    conn.close()
    return {"competencia": comp, "faturas_geradas": created, "message": f"{created} fatura(s) gerada(s) para {comp}."}


@router.post("/api/honorarios/faturas/{fid}/pagar")
def pagar_fatura(fid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    fatura = conn.execute("SELECT * FROM honorarios_faturas WHERE id=? AND company_id=?", (fid, company_id)).fetchone()
    if not fatura:
        conn.close()
        raise HTTPException(404, "Fatura não encontrada.")
    conn.execute("UPDATE honorarios_faturas SET status='pago', paid_at=? WHERE id=?",
                 (date.today().isoformat(), fid))
    conn.commit()
    conn.close()
    return {"message": "Fatura marcada como paga."}


@router.get("/api/honorarios/summary")
def honorarios_summary(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    total_contratos = conn.execute(
        "SELECT COUNT(*) FROM honorarios_contratos WHERE company_id=? AND ativo=1", (company_id,)
    ).fetchone()[0]
    mrr = conn.execute(
        "SELECT COALESCE(SUM(valor_mensal),0) FROM honorarios_contratos WHERE company_id=? AND ativo=1", (company_id,)
    ).fetchone()[0]
    comp = date.today().strftime("%Y-%m")
    pendente = conn.execute(
        "SELECT COALESCE(SUM(valor),0) FROM honorarios_faturas WHERE company_id=? AND status='pendente' AND competencia=?",
        (company_id, comp)
    ).fetchone()[0]
    pago_mes = conn.execute(
        "SELECT COALESCE(SUM(valor),0) FROM honorarios_faturas WHERE company_id=? AND status='pago' AND competencia=?",
        (company_id, comp)
    ).fetchone()[0]
    inadimplentes = conn.execute("""
        SELECT COUNT(DISTINCT contrato_id) FROM honorarios_faturas
        WHERE company_id=? AND status='pendente' AND due_date < ?
    """, (company_id, date.today().isoformat())).fetchone()[0]
    conn.close()
    return {
        "total_contratos_ativos": total_contratos,
        "mrr": round(float(mrr or 0), 2),
        "mrr_anual": round(float(mrr or 0) * 12, 2),
        "pendente_mes": round(float(pendente or 0), 2),
        "pago_mes": round(float(pago_mes or 0), 2),
        "inadimplentes": inadimplentes,
    }


@router.get("/api/honorarios/servicos")
def get_servicos():
    return {"servicos": SERVICOS_PADRAO}

"""
DIRBI — Declaração de Incentivos, Renúncias, Benefícios e Imunidades de Natureza Tributária
Instituída pela IN RFB nº 2198/2024, obrigatória para tomadores de benefícios fiscais.
"""
from datetime import date
import calendar
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(tags=["DIRBI"])

# Benefícios fiscais mais comuns
BENEFICIOS_FICAIS = [
    {"codigo": "01001", "descricao": "SIMPLES NACIONAL — redução de alíquota", "regime": ["simples_nacional"]},
    {"codigo": "02001", "descricao": "MEI — isenção IRPJ/CSLL/PIS/COFINS", "regime": ["mei"]},
    {"codigo": "03001", "descricao": "LUCRO PRESUMIDO — alíquota reduzida PIS/COFINS cumulativo", "regime": ["lucro_presumido"]},
    {"codigo": "04001", "descricao": "ZFM — Zona Franca de Manaus (IPI)", "regime": ["lucro_real","lucro_presumido"]},
    {"codigo": "05001", "descricao": "REINTEGRA — ressarcimento para exportadores", "regime": ["lucro_real","lucro_presumido"]},
    {"codigo": "06001", "descricao": "PAT — dedução IRPJ alimentação do trabalhador", "regime": ["lucro_real"]},
    {"codigo": "07001", "descricao": "Lei do Bem — P&D inovação tecnológica", "regime": ["lucro_real"]},
    {"codigo": "08001", "descricao": "RECOF — regime aduaneiro especial", "regime": ["lucro_real","lucro_presumido"]},
    {"codigo": "09001", "descricao": "Desoneração da Folha — CPRB", "regime": ["lucro_real","lucro_presumido"]},
    {"codigo": "10001", "descricao": "PROUNI — bolsas de estudo", "regime": ["lucro_real","lucro_presumido"]},
    {"codigo": "11001", "descricao": "Imunidade IRPJ — entidade sem fins lucrativos", "regime": ["lucro_real"]},
    {"codigo": "12001", "descricao": "Isenção IRPJ — atividade rural", "regime": ["lucro_real","lucro_presumido"]},
]


class DIRBIBeneficio(BaseModel):
    codigo_beneficio: str
    descricao: str
    competencia: str
    valor_beneficio: float = 0.0
    base_calculo: float = 0.0
    observacao: str = ""


@router.get("/api/dirbi/beneficios-disponiveis")
def get_beneficios(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = conn.execute("SELECT regime_tributario FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()
    regime = comp["regime_tributario"] if comp else "simples_nacional"
    aplicaveis = [b for b in BENEFICIOS_FICAIS if regime in b["regime"]]
    return {"regime": regime, "beneficios": aplicaveis}


@router.get("/api/dirbi/lancamentos")
def list_dirbi(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    q = "SELECT * FROM dirbi_lancamentos WHERE company_id=?"
    params: list = [company_id]
    if competencia:
        q += " AND competencia=?"
        params.append(competencia)
    q += " ORDER BY competencia DESC, codigo_beneficio"
    rows = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    return rows


@router.post("/api/dirbi/lancamentos")
def create_dirbi(body: DIRBIBeneficio, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO dirbi_lancamentos
        (company_id, codigo_beneficio, descricao, competencia, valor_beneficio, base_calculo, observacao)
        VALUES (?,?,?,?,?,?,?)
    """, (company_id, body.codigo_beneficio, body.descricao, body.competencia,
          body.valor_beneficio, body.base_calculo, body.observacao))
    conn.commit()
    conn.close()
    return {"message": "Benefício DIRBI registrado."}


@router.delete("/api/dirbi/lancamentos/{lid}")
def delete_dirbi(lid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM dirbi_lancamentos WHERE id=? AND company_id=?", (lid, company_id))
    conn.commit()
    conn.close()
    return {"message": "Lançamento excluído."}


@router.get("/api/dirbi/preview")
def dirbi_preview(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Prévia da DIRBI do mês com cálculo estimado dos benefícios."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = date.today().strftime("%Y-%m") if not competencia else competencia
    company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    regime = company["regime_tributario"] if company else "simples_nacional"
    year, month = comp.split("-")
    end_day = calendar.monthrange(int(year), int(month))[1]
    s_date = f"{year}-{month}-01"
    e_date = f"{year}-{month}-{end_day:02d}"
    # Faturamento do mês
    receita = conn.execute("""
        SELECT COALESCE(SUM(amount),0) as total FROM financial_entries
        WHERE company_id=? AND type='receita' AND status='pago' AND due_date BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchone()
    # Benefícios já cadastrados
    lancs = rows_to_dicts(conn.execute(
        "SELECT * FROM dirbi_lancamentos WHERE company_id=? AND competencia=?",
        (company_id, comp)
    ).fetchall())
    conn.close()
    receita_mes = float(receita["total"] or 0)
    total_beneficios = sum(float(l.get("valor_beneficio") or 0) for l in lancs)
    # Estimar benefício do Simples se aplicável
    simples_estimado = 0.0
    if regime == "simples_nacional":
        simples_estimado = receita_mes * 0.045  # estimativa conservadora
    vencimento = f"{year}-{month}-20"
    return {
        "competencia": comp,
        "razao_social": company["razao_social"] if company else "",
        "cnpj": company["cnpj"] if company else "",
        "regime": regime,
        "receita_bruta_mes": round(receita_mes, 2),
        "beneficios_cadastrados": lancs,
        "total_beneficios_declarados": round(total_beneficios, 2),
        "simples_estimado": round(simples_estimado, 2),
        "vencimento": vencimento,
        "obrigatorio": total_beneficios > 0 or regime in ["simples_nacional", "mei"],
        "observacao": "DIRBI é obrigatória para quem usufruiu de benefício fiscal tributário no período.",
    }


@router.get("/api/dirbi/gerar")
def gerar_dirbi(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Gera arquivo texto DIRBI (layout simplificado)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    lancs = rows_to_dicts(conn.execute(
        "SELECT * FROM dirbi_lancamentos WHERE company_id=? AND competencia=?",
        (company_id, comp)
    ).fetchall())
    conn.close()
    if not company:
        raise HTTPException(404, "Empresa não encontrada.")
    cnpj = (company["cnpj"] or "").replace(".","").replace("/","").replace("-","")
    year, month = comp.split("-")
    lines = [
        f"DIRBI|{cnpj}|{company['razao_social']}|{year}{month}|{len(lancs)}",
    ]
    for l in lancs:
        val = f"{float(l.get('valor_beneficio',0)):.2f}".replace(".", ",")
        base = f"{float(l.get('base_calculo',0)):.2f}".replace(".", ",")
        lines.append(f"BENEF|{l['codigo_beneficio']}|{l['descricao']}|{val}|{base}|{l.get('observacao','')}")
    lines.append(f"FIM|{len(lines)+1}")
    content = "\r\n".join(lines)
    fname = f"DIRBI_{cnpj}_{year}{month}.txt"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@router.get("/api/dirbi/calendario")
def dirbi_calendario(year: Optional[int] = None):
    """Calendário de vencimentos DIRBI (todo dia 20 do mês seguinte à competência)."""
    yr = year or date.today().year
    vencimentos = []
    for m in range(1, 13):
        last_day = calendar.monthrange(yr, m)[1]
        comp = f"{yr}-{m:02d}"
        # Vence dia 20 do mês seguinte
        if m == 12:
            venc = f"{yr+1}-01-20"
        else:
            venc = f"{yr}-{(m+1):02d}-20"
        vencimentos.append({"competencia": comp, "vencimento": venc, "mes_nome": ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"][m-1]})
    return {"ano": yr, "vencimentos": vencimentos}

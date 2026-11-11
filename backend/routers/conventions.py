"""
Busca Convenções — CCT (Convenções Coletivas de Trabalho)
Permite pesquisar e registrar CCTs aplicáveis aos empregados da empresa.
"""
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

router = APIRouter(tags=["Convenções Coletivas"])

# CATEGORIAs profissionais comuns no Brasil
CATEGORIAS_PROFISSIONAIS = [
    {"codigo": "001", "descricao": "Comerciários", "sindicato": "SINDICOMERCIO", "cno": "SINDICATO DOS EMPREGADOS NO COMÉRCIO"},
    {"codigo": "002", "descricao": "Metalúrgicos", "sindicato": "SINDICATO DOS METALÚRGICOS", "cno": ""},
    {"codigo": "003", "descricao": "Bancários", "sindicato": "SEEB", "cno": "SINDICATO DOS EMPREGADOS EM ESTABELECIMENTOS BANCÁRIOS"},
    {"codigo": "004", "descricao": "Contabilistas", "sindicato": "SINDCONT", "cno": "SINDICATO DOS CONTABILISTAS"},
    {"codigo": "005", "descricao": "Trabalhadores em TI", "sindicato": "SINDPD", "cno": "SINDICATO DOS TRABALHADORES EM PROCESSAMENTO DE DADOS"},
    {"codigo": "006", "descricao": "Trabalhadores em Escritório", "sindicato": "SINDIFISCO", "cno": ""},
    {"codigo": "007", "descricao": "Motoristas e Transportadores", "sindicato": "SINDIMOTORISTAS", "cno": ""},
    {"codigo": "008", "descricao": "Trabalhadores da Saúde", "sindicato": "SINDISAÚDE", "cno": ""},
    {"codigo": "009", "descricao": "Educadores", "sindicato": "SINPRO", "cno": "SINDICATO DOS PROFESSORES"},
    {"codigo": "010", "descricao": "Construção Civil", "sindicato": "SINDUSCON", "cno": ""},
    {"codigo": "011", "descricao": "Alimentação", "sindicato": "SINTHORESP", "cno": ""},
    {"codigo": "012", "descricao": "Trabalhadores Rurais", "sindicato": "FETAG", "cno": ""},
    {"codigo": "013", "descricao": "Teleatendimento / Call Center", "sindicato": "SINTELMARK", "cno": ""},
    {"codigo": "014", "descricao": "Limpeza e Conservação", "sindicato": "SIEMACO", "cno": ""},
]


class ConvencaoContrato(BaseModel):
    categoria: str
    sindicato_empregados: str
    sindicato_empregadores: str
    uf: str = "SP"
    municipio: str = ""
    data_inicio: str
    data_fim: str
    piso_salarial: float = 0.0
    reajuste_pct: float = 0.0
    jornada_semanal: int = 44
    intervalo_jornada_min: int = 60
    adicional_noturno_pct: float = 20.0
    adicional_hora_extra_pct: float = 50.0
    vale_refeicao_diario: float = 0.0
    vale_transporte: int = 1
    observacoes: str = ""
    arquivo_url: str = ""


class ConvencaoAlerta(BaseModel):
    convencao_id: int
    tipo: str  # vencimento, reajuste, dissidio
    data_alerta: str
    descricao: str


@router.get("/api/conventions/categorias")
def get_categorias():
    return {"categorias": CATEGORIAS_PROFISSIONAIS}


@router.get("/api/conventions/list")
def list_conventions(
    uf: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    q = "SELECT * FROM cct_convencoes WHERE company_id=?"
    params: list = [company_id]
    if uf:
        q += " AND uf=?"
        params.append(uf)
    q += " ORDER BY data_fim DESC"
    rows = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    # Calcula dias para vencimento
    today = date.today()
    for r in rows:
        try:
            fim = date.fromisoformat(r["data_fim"])
            r["dias_para_vencer"] = (fim - today).days
            r["status"] = "vigente" if fim >= today else "vencida"
        except Exception:
            r["dias_para_vencer"] = None
            r["status"] = "indefinido"
    return rows


@router.post("/api/conventions")
def create_convention(body: ConvencaoContrato, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cct_convencoes
        (company_id, categoria, sindicato_empregados, sindicato_empregadores, uf, municipio,
         data_inicio, data_fim, piso_salarial, reajuste_pct, jornada_semanal,
         intervalo_jornada_min, adicional_noturno_pct, adicional_hora_extra_pct,
         vale_refeicao_diario, vale_transporte, observacoes, arquivo_url)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (company_id, body.categoria, body.sindicato_empregados, body.sindicato_empregadores,
          body.uf, body.municipio, body.data_inicio, body.data_fim,
          body.piso_salarial, body.reajuste_pct, body.jornada_semanal,
          body.intervalo_jornada_min, body.adicional_noturno_pct, body.adicional_hora_extra_pct,
          body.vale_refeicao_diario, body.vale_transporte, body.observacoes, body.arquivo_url))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": cid, "message": "Convenção registrada com sucesso."}


@router.put("/api/conventions/{cid}")
def update_convention(cid: int, body: ConvencaoContrato, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("""
        UPDATE cct_convencoes SET
        categoria=?, sindicato_empregados=?, sindicato_empregadores=?, uf=?, municipio=?,
        data_inicio=?, data_fim=?, piso_salarial=?, reajuste_pct=?, jornada_semanal=?,
        intervalo_jornada_min=?, adicional_noturno_pct=?, adicional_hora_extra_pct=?,
        vale_refeicao_diario=?, vale_transporte=?, observacoes=?, arquivo_url=?
        WHERE id=? AND company_id=?
    """, (body.categoria, body.sindicato_empregados, body.sindicato_empregadores,
          body.uf, body.municipio, body.data_inicio, body.data_fim,
          body.piso_salarial, body.reajuste_pct, body.jornada_semanal,
          body.intervalo_jornada_min, body.adicional_noturno_pct, body.adicional_hora_extra_pct,
          body.vale_refeicao_diario, body.vale_transporte, body.observacoes, body.arquivo_url,
          cid, company_id))
    conn.commit()
    conn.close()
    return {"message": "Convenção atualizada."}


@router.delete("/api/conventions/{cid}")
def delete_convention(cid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM cct_convencoes WHERE id=? AND company_id=?", (cid, company_id))
    conn.commit()
    conn.close()
    return {"message": "Convenção excluída."}


@router.get("/api/conventions/{cid}/alertas")
def convention_alerts(cid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Gera alertas automáticos de vencimento para uma CCT."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conv = conn.execute(
        "SELECT * FROM cct_convencoes WHERE id=? AND company_id=?", (cid, company_id)
    ).fetchone()
    conn.close()
    if not conv:
        raise HTTPException(404, "Convenção não encontrada.")
    alerts = []
    today = date.today()
    try:
        fim = date.fromisoformat(conv["data_fim"])
        dias = (fim - today).days
        if dias <= 90:
            nivel = "critico" if dias <= 30 else ("alerta" if dias <= 60 else "aviso")
            alerts.append({
                "tipo": "vencimento",
                "descricao": f"CCT vence em {dias} dia(s) — {conv['categoria']}",
                "data": conv["data_fim"],
                "nivel": nivel,
            })
        # Alerta dissídio (geralmente 60 dias antes do vencimento)
        from datetime import timedelta
        dissidio = fim - timedelta(days=60)
        if dissidio >= today and (dissidio - today).days <= 30:
            alerts.append({
                "tipo": "dissidio",
                "descricao": f"Período de negociação do dissídio — {conv['categoria']}",
                "data": dissidio.isoformat(),
                "nivel": "aviso",
            })
    except Exception:
        pass
    return {"convencao_id": cid, "alerts": alerts}


@router.get("/api/conventions/summary")
def conventions_summary(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    total = conn.execute("SELECT COUNT(*) FROM cct_convencoes WHERE company_id=?", (company_id,)).fetchone()[0]
    today = date.today().isoformat()
    vigentes = conn.execute(
        "SELECT COUNT(*) FROM cct_convencoes WHERE company_id=? AND data_fim>=?", (company_id, today)
    ).fetchone()[0]
    vencidas = conn.execute(
        "SELECT COUNT(*) FROM cct_convencoes WHERE company_id=? AND data_fim<?", (company_id, today)
    ).fetchone()[0]
    # Vencendo em 90 dias
    from datetime import timedelta
    limite = (date.today() + timedelta(days=90)).isoformat()
    vencendo = conn.execute(
        "SELECT COUNT(*) FROM cct_convencoes WHERE company_id=? AND data_fim BETWEEN ? AND ?",
        (company_id, today, limite)
    ).fetchone()[0]
    conn.close()
    return {
        "total": total,
        "vigentes": vigentes,
        "vencidas": vencidas,
        "vencendo_90_dias": vencendo,
    }

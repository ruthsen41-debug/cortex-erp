from fastapi import APIRouter, Depends
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(prefix="/api/reports", tags=["Relatórios & DRE"])


@router.get("/dre")
def get_dre_report(regime: str = "competencia", current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Calcula a DRE Gerencial completa (Regime de Competência ou Regime de Caixa)
    com Análise Vertical (%) no padrão contábil brasileiro.
    """
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT e.*, cat.dre_group, cat.name as category_name
        FROM financial_entries e
        LEFT JOIN categories cat ON cat.id = e.category_id
        WHERE e.status != 'cancelado' AND e.company_id = ?
    """, (company_id,)).fetchall())
    conn.close()

    groups = {
        "receita_bruta": 0.0,
        "deducoes_impostos": 0.0,
        "custos_mercadorias_servicos": 0.0,
        "despesas_pessoal": 0.0,
        "despesas_operacionais": 0.0,
        "despesas_comerciais": 0.0,
        "receitas_financeiras": 0.0,
        "despesas_financeiras": 0.0,
        "investimentos": 0.0,
    }

    for r in rows:
        grp = r.get("dre_group") or ("receita_bruta" if r["type"] == "receita" else "despesas_operacionais")
        if grp not in groups:
            continue
        val = float(r.get("paid_amount") or 0.0) if regime == "caixa" else (float(r["amount"]) + float(r.get("interest") or 0.0) + float(r.get("fine") or 0.0) - float(r.get("discount") or 0.0))
        groups[grp] = round(groups[grp] + val, 2)

    rec_bruta = groups["receita_bruta"]
    deducoes = groups["deducoes_impostos"]
    rec_liquida = round(rec_bruta - deducoes, 2)
    cmv = groups["custos_mercadorias_servicos"]
    lucro_bruto = round(rec_liquida - cmv, 2)
    desp_totais = round(groups["despesas_pessoal"] + groups["despesas_operacionais"] + groups["despesas_comerciais"], 2)
    ebitda = round(lucro_bruto - desp_totais, 2)
    res_fin = round(groups["receitas_financeiras"] - groups["despesas_financeiras"], 2)
    lucro_liquido = round(ebitda + res_fin - groups["investimentos"], 2)

    pct = lambda v: round((v / rec_bruta) * 100.0, 1) if rec_bruta > 0 else 0.0

    lines = [
        {"label": "(+) RECEITA OPERACIONAL BRUTA", "value": rec_bruta, "av_percent": 100.0, "bold": True, "color": "text-emerald-700"},
        {"label": "(-) Deduções e Impostos sobre Vendas (DAS / ISS / ICMS)", "value": -deducoes, "av_percent": pct(deducoes), "bold": False, "color": "text-rose-600"},
        {"label": "(=) RECEITA OPERACIONAL LÍQUIDA", "value": rec_liquida, "av_percent": pct(rec_liquida), "bold": True, "color": "text-slate-900"},
        {"label": "(-) Custos de Mercadorias e Serviços Vendidos (CMV / CSV)", "value": -cmv, "av_percent": pct(cmv), "bold": False, "color": "text-rose-600"},
        {"label": "(=) RESULTADO OPERACIONAL BRUTO (MARGEM BRUTA)", "value": lucro_bruto, "av_percent": pct(lucro_bruto), "bold": True, "color": "text-blue-700"},
        {"label": "(-) Despesas com Pessoal, Folha e Encargos", "value": -groups["despesas_pessoal"], "av_percent": pct(groups["despesas_pessoal"]), "bold": False, "color": "text-slate-700"},
        {"label": "(-) Despesas Administrativas e Operacionais Fixas", "value": -groups["despesas_operacionais"], "av_percent": pct(groups["despesas_operacionais"]), "bold": False, "color": "text-slate-700"},
        {"label": "(-) Despesas Comerciais, Marketing e Comissões", "value": -groups["despesas_comerciais"], "av_percent": pct(groups["despesas_comerciais"]), "bold": False, "color": "text-slate-700"},
        {"label": "(=) EBITDA / GERAÇÃO DE CAIXA OPERACIONAL", "value": ebitda, "av_percent": pct(ebitda), "bold": True, "color": "text-indigo-700"},
        {"label": "(+/-) Resultado Financeiro Líquido (Rendimentos - Tarifas/Juros)", "value": res_fin, "av_percent": pct(res_fin), "bold": False, "color": "text-slate-700"},
        {"label": "(-) Investimentos em Imobilizado / Capex", "value": -groups["investimentos"], "av_percent": pct(groups["investimentos"]), "bold": False, "color": "text-slate-700"},
        {"label": "(=) LUCRO / PREJUÍZO LÍQUIDO DO EXERCÍCIO", "value": lucro_liquido, "av_percent": pct(lucro_liquido), "bold": True, "color": "text-emerald-700" if lucro_liquido >= 0 else "text-rose-700"},
    ]
    return {"regime": regime, "lines": lines, "summary": {"receita_bruta": rec_bruta, "lucro_liquido": lucro_liquido, "margem_liquida": pct(lucro_liquido)}}

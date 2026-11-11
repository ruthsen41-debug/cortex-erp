from datetime import date
from typing import Dict, Any, Optional, List
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

router = APIRouter(tags=["Simples Nacional"])

# Tabelas Simples Nacional 2024 (Lei Complementar 123/2006)
ANEXOS = {
    "I": {  # Comércio
        "name": "Anexo I — Comércio",
        "faixas": [
            (180000,   0.04,       0),
            (360000,   0.073,   5940),
            (720000,   0.095,  13860),
            (1800000,  0.107,  22500),
            (3600000,  0.143,  87300),
            (4800000,  0.19,  378000),
        ]
    },
    "II": {  # Indústria
        "name": "Anexo II — Indústria",
        "faixas": [
            (180000,   0.045,       0),
            (360000,   0.078,   5940),
            (720000,   0.1,    13860),
            (1800000,  0.112,  22500),
            (3600000,  0.147,  85500),
            (4800000,  0.3,  720000),
        ]
    },
    "III": {  # Serviços (locação, escritório contábil, creche, etc.)
        "name": "Anexo III — Serviços (ISS incluso)",
        "faixas": [
            (180000,   0.06,       0),
            (360000,   0.112,   9360),
            (720000,   0.135,  17640),
            (1800000,  0.16,   35640),
            (3600000,  0.21,  125640),
            (4800000,  0.33,  648000),
        ]
    },
    "IV": {  # Serviços (construção, vigilância, limpeza)
        "name": "Anexo IV — Serviços (sem CPP)",
        "faixas": [
            (180000,   0.045,       0),
            (360000,   0.09,   8100),
            (720000,   0.102,  12420),
            (1800000,  0.14,   39780),
            (3600000,  0.22,  183780),
            (4800000,  0.33,  828000),
        ]
    },
    "V": {  # Serviços (medicina, odontologia, TI, engenharia)
        "name": "Anexo V — Serviços (fator R)",
        "faixas": [
            (180000,   0.155,      0),
            (360000,   0.18,   4500),
            (720000,   0.195,  9900),
            (1800000,  0.205, 17100),
            (3600000,  0.23,  62100),
            (4800000,  0.305, 540000),
        ]
    },
}

MEI_LIMITE = 81000.0
SIMPLES_LIMITE = 4800000.0


def _calc_das(rbt12: float, anexo: str) -> dict:
    if anexo == "MEI":
        return {"aliquota_nominal": 0.0, "aliquota_efetiva": 0.0, "valor_das": 0.0, "faixa": "MEI"}
    tabela = ANEXOS.get(anexo)
    if not tabela:
        return {}
    faixas = tabela["faixas"]
    limite_faixa = None
    aliq = 0.0
    pd_val = 0.0
    for i, (limite, aliquota, pd) in enumerate(faixas):
        if rbt12 <= limite:
            limite_faixa = i + 1
            aliq = aliquota
            pd_val = pd
            break
    else:
        limite_faixa = len(faixas)
        aliq = faixas[-1][1]
        pd_val = faixas[-1][2]
    if rbt12 <= 0:
        return {"aliquota_nominal": 0.0, "aliquota_efetiva": 0.0, "valor_das": 0.0, "faixa": limite_faixa}
    aliq_efetiva = ((rbt12 * aliq) - pd_val) / rbt12
    return {
        "aliquota_nominal": round(aliq * 100, 4),
        "aliquota_efetiva": round(aliq_efetiva * 100, 4),
        "valor_das": 0.0,  # will be filled with RBT month
        "faixa": limite_faixa,
        "pd": pd_val,
    }


class SimplesConfig(BaseModel):
    anexo: str = "I"
    faturamento_12m: float = 0.0


class DASCalculate(BaseModel):
    competencia: str  # YYYY-MM
    receita_bruta_mes: float
    rbt12: Optional[float] = None


@router.get("/api/simples/config")
def get_simples_config(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("SELECT * FROM simples_config WHERE company_id=?", (company_id,)).fetchone()
    company = conn.execute("SELECT regime_tributario FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()
    if not row:
        return {
            "company_id": company_id,
            "anexo": "I",
            "faturamento_12m": 0.0,
            "regime": company["regime_tributario"] if company else "simples_nacional",
            "anexos_disponiveis": {k: v["name"] for k, v in ANEXOS.items()},
            "limite_mei": MEI_LIMITE,
            "limite_simples": SIMPLES_LIMITE,
        }
    cfg = dict(row)
    cfg["anexos_disponiveis"] = {k: v["name"] for k, v in ANEXOS.items()}
    cfg["limite_mei"] = MEI_LIMITE
    cfg["limite_simples"] = SIMPLES_LIMITE
    cfg["regime"] = company["regime_tributario"] if company else "simples_nacional"
    return cfg


@router.put("/api/simples/config")
def update_simples_config(body: SimplesConfig, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("""
        INSERT INTO simples_config (company_id, anexo, faturamento_12m)
        VALUES (?,?,?)
        ON CONFLICT(company_id) DO UPDATE SET
        anexo=excluded.anexo, faturamento_12m=excluded.faturamento_12m
    """, (company_id, body.anexo, body.faturamento_12m))
    conn.commit()
    conn.close()
    return {"message": "Configuração do Simples Nacional salva."}


@router.post("/api/simples/calculate-das")
def calculate_das(body: DASCalculate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cfg = conn.execute("SELECT * FROM simples_config WHERE company_id=?", (company_id,)).fetchone()
    anexo = cfg["anexo"] if cfg else "I"
    # Use provided rbt12 or stored
    rbt12 = body.rbt12 or (float(cfg["faturamento_12m"]) if cfg else 0.0)
    result = _calc_das(rbt12, anexo)
    # DAS value = receita_bruta_mes * aliq_efetiva
    aliq_ef = result.get("aliquota_efetiva", 0) / 100
    das_value = round(body.receita_bruta_mes * aliq_ef, 2)
    result["valor_das"] = das_value
    result["receita_bruta_mes"] = body.receita_bruta_mes
    result["rbt12"] = rbt12
    result["competencia"] = body.competencia
    result["anexo"] = anexo
    # Save to history
    conn.execute("""
        INSERT OR REPLACE INTO simples_das_history
        (company_id, competencia, receita_bruta_mes, rbt12, aliquota_efetiva, valor_das, anexo)
        VALUES (?,?,?,?,?,?,?)
    """, (company_id, body.competencia, body.receita_bruta_mes, rbt12,
          result.get("aliquota_efetiva", 0), das_value, anexo))
    conn.commit()
    conn.close()
    return result


@router.get("/api/simples/history")
def get_das_history(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM simples_das_history WHERE company_id=? ORDER BY competencia DESC LIMIT 24",
        (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.get("/api/simples/pgdas-preview")
def pgdas_preview(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Prévia do PGDAS-D para o mês."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    cfg = conn.execute("SELECT * FROM simples_config WHERE company_id=?", (company_id,)).fetchone()
    company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    # Sum revenue for the month
    year, month = comp.split("-")
    start = f"{year}-{month}-01"
    import calendar
    end_day = calendar.monthrange(int(year), int(month))[1]
    end = f"{year}-{month}-{end_day:02d}"
    receitas = conn.execute("""
        SELECT COALESCE(SUM(amount),0) as total FROM financial_entries
        WHERE company_id=? AND type='receita' AND status='pago'
        AND due_date BETWEEN ? AND ?
    """, (company_id, start, end)).fetchone()
    conn.close()
    receita_mes = float(receitas["total"] or 0)
    anexo = cfg["anexo"] if cfg else "I"
    rbt12 = float(cfg["faturamento_12m"]) if cfg else receita_mes * 12
    calc = _calc_das(rbt12, anexo)
    aliq_ef = calc.get("aliquota_efetiva", 0) / 100
    das = round(receita_mes * aliq_ef, 2)
    # Breakdown estimado por tributo (Anexo I como referência)
    breakdown = {
        "IRPJ": round(das * 0.055, 2),
        "CSLL": round(das * 0.035, 2),
        "COFINS": round(das * 0.1265, 2),
        "PIS": round(das * 0.0275, 2),
        "CPP": round(das * 0.43, 2),
        "ICMS": round(das * 0.325, 2),
    } if das else {}
    return {
        "competencia": comp,
        "razao_social": company["razao_social"] if company else "",
        "cnpj": company["cnpj"] if company else "",
        "anexo": anexo,
        "receita_bruta_mes": receita_mes,
        "rbt12": rbt12,
        "aliquota_nominal": calc.get("aliquota_nominal", 0),
        "aliquota_efetiva": calc.get("aliquota_efetiva", 0),
        "faixa": calc.get("faixa"),
        "valor_das": das,
        "breakdown_estimado": breakdown,
        "vencimento": f"{year}-{month}-20" if int(month) < 12 else f"{year}-12-20",
    }

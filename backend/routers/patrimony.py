from datetime import date, datetime
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

router = APIRouter(tags=["Patrimônio"])


class AssetCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "maquinas_equipamentos"
    acquisition_date: str
    acquisition_value: float
    useful_life_months: int = 60
    tax_useful_life_months: Optional[int] = 60
    icms_credit_total: Optional[float] = 0.0
    residual_value: float = 0.0
    depreciation_method: str = "linear"  # linear, acelerado
    notes: str = ""


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    acquisition_date: Optional[str] = None
    acquisition_value: Optional[float] = None
    useful_life_months: Optional[int] = None
    tax_useful_life_months: Optional[int] = None
    icms_credit_total: Optional[float] = None
    residual_value: Optional[float] = None
    depreciation_method: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class AssetDisposalPayload(BaseModel):
    disposal_date: str
    disposal_value: float = 0.0
    disposal_reason: str = "venda"
    gerar_contabil: bool = True


def _calc_monthly_depreciation(acquisition_value: float, residual_value: float,
                                useful_life_months: int, method: str) -> float:
    depreciable = acquisition_value - residual_value
    if useful_life_months <= 0:
        return 0.0
    if method == "acelerado":
        return depreciable / useful_life_months * 1.5
    return depreciable / useful_life_months


@router.get("/api/patrimony")
def list_assets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    q = "SELECT * FROM fixed_assets WHERE company_id = ?"
    params: list = [company_id]
    if status:
        q += " AND status = ?"
        params.append(status)
    if category:
        q += " AND category = ?"
        params.append(category)
    q += " ORDER BY acquisition_date DESC"
    assets = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    return assets


@router.post("/api/patrimony")
def create_asset(body: AssetCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fixed_assets
        (company_id, name, description, category, acquisition_date, acquisition_value,
         useful_life_months, tax_useful_life_months, icms_credit_total,
         residual_value, depreciation_method, accumulated_depreciation,
         net_value, status, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)
    """, (
        company_id, body.name, body.description, body.category,
        body.acquisition_date, body.acquisition_value,
        body.useful_life_months, body.tax_useful_life_months or body.useful_life_months,
        body.icms_credit_total or 0.0,
        body.residual_value, body.depreciation_method,
        body.acquisition_value,
        "ativo", body.notes
    ))
    asset_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": asset_id, "message": "Bem patrimonial criado com sucesso."}


@router.put("/api/patrimony/{asset_id}")
def update_asset(asset_id: int, body: AssetUpdate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    asset = conn.execute("SELECT * FROM fixed_assets WHERE id=? AND company_id=?", (asset_id, company_id)).fetchone()
    if not asset:
        conn.close()
        raise HTTPException(404, "Bem não encontrado.")
    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        conn.close()
        return {"message": "Nenhuma alteração."}
    # recalculate net_value if key fields changed
    acq = fields.get("acquisition_value", asset["acquisition_value"])
    acc_dep = asset["accumulated_depreciation"]
    fields["net_value"] = max(0.0, float(acq) - float(acc_dep))
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE fixed_assets SET {sets} WHERE id=? AND company_id=?",
                 (*fields.values(), asset_id, company_id))
    conn.commit()
    conn.close()
    return {"message": "Bem atualizado com sucesso."}


@router.delete("/api/patrimony/{asset_id}")
def delete_asset(asset_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM fixed_assets WHERE id=? AND company_id=?", (asset_id, company_id))
    conn.commit()
    conn.close()
    return {"message": "Bem excluído."}


@router.get("/api/patrimony/summary")
def patrimony_summary(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT acquisition_value, accumulated_depreciation, net_value, status FROM fixed_assets WHERE company_id=?",
        (company_id,)
    ).fetchall())
    conn.close()
    total_acq = sum(float(r.get("acquisition_value") or 0) for r in rows)
    total_dep = sum(float(r.get("accumulated_depreciation") or 0) for r in rows)
    total_net = sum(float(r.get("net_value") or 0) for r in rows)
    ativos = sum(1 for r in rows if r.get("status") == "ativo")
    return {
        "total_assets": len(rows),
        "total_active": ativos,
        "total_acquisition_value": round(total_acq, 2),
        "total_accumulated_depreciation": round(total_dep, 2),
        "total_net_value": round(total_net, 2),
        "depreciation_percent": round((total_dep / total_acq * 100) if total_acq else 0, 1),
    }


@router.post("/api/patrimony/run-depreciation")
def run_depreciation(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Registra a depreciação mensal de todos os bens ativos."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    assets = rows_to_dicts(conn.execute(
        "SELECT * FROM fixed_assets WHERE company_id=? AND status='ativo'", (company_id,)
    ).fetchall())
    updated = 0
    total_dep_month = 0.0
    for a in assets:
        monthly = _calc_monthly_depreciation(
            float(a.get("acquisition_value") or 0),
            float(a.get("residual_value") or 0),
            int(a.get("useful_life_months") or 60),
            a.get("depreciation_method", "linear")
        )
        new_acc = float(a.get("accumulated_depreciation") or 0) + monthly
        acq = float(a.get("acquisition_value") or 0)
        new_net = max(float(a.get("residual_value") or 0), acq - new_acc)
        new_status = "depreciado" if new_net <= float(a.get("residual_value") or 0) else "ativo"
        conn.execute("""
            UPDATE fixed_assets
            SET accumulated_depreciation=?, net_value=?, status=?
            WHERE id=?
        """, (round(new_acc, 2), round(new_net, 2), new_status, a["id"]))
        # Register in depreciation log
        conn.execute("""
            INSERT OR IGNORE INTO asset_depreciations
            (company_id, asset_id, competencia, monthly_depreciation, accumulated_after, net_value_after)
            VALUES (?,?,?,?,?,?)
        """, (company_id, a["id"], comp, round(monthly, 2), round(new_acc, 2), round(new_net, 2)))
        updated += 1
        total_dep_month += monthly
    conn.commit()
    conn.close()
    return {
        "competencia": comp,
        "assets_processed": updated,
        "total_depreciation_month": round(total_dep_month, 2),
        "message": f"Depreciação de {comp} processada para {updated} bens."
    }


@router.get("/api/patrimony/{asset_id}/depreciations")
def get_asset_depreciations(asset_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM asset_depreciations WHERE company_id=? AND asset_id=? ORDER BY competencia",
        (company_id, asset_id)
    ).fetchall())
    conn.close()
    return rows


@router.get("/api/patrimony/ciap")
def export_ciap(
    year: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Exporta dados para preenchimento do CIAP (Controle de Crédito do ICMS do Ativo Permanente)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    yr = year or date.today().year
    assets = rows_to_dicts(conn.execute(
        "SELECT * FROM fixed_assets WHERE company_id=? AND status IN ('ativo','depreciado')",
        (company_id,)
    ).fetchall())
    ciap_items = []
    for a in assets:
        acq_year = int((a.get("acquisition_date") or "0000")[:4])
        if acq_year > yr:
            continue
        monthly = _calc_monthly_depreciation(
            float(a.get("acquisition_value") or 0),
            float(a.get("residual_value") or 0),
            int(a.get("useful_life_months") or 60),
            a.get("depreciation_method", "linear")
        )
        ciap_items.append({
            "descricao": a.get("name"),
            "data_aquisicao": a.get("acquisition_date"),
            "valor_aquisicao": a.get("acquisition_value"),
            "vida_util_meses": a.get("useful_life_months"),
            "depreciacao_mensal": round(monthly, 2),
            "depreciacao_acumulada": a.get("accumulated_depreciation"),
            "valor_contabil_liquido": a.get("net_value"),
            "status": a.get("status"),
        })
    conn.close()
    return {"year": yr, "items": ciap_items, "total_items": len(ciap_items)}


@router.post("/api/patrimony/{asset_id}/baixa")
def dispose_asset(
    asset_id: int,
    body: AssetDisposalPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Baixa total do bem patrimonial com apuração de Ganho/Perda de Capital e lançamento contábil automático."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    asset = conn.execute(
        "SELECT * FROM fixed_assets WHERE id = ? AND company_id = ?", (asset_id, company_id)
    ).fetchone()
    if not asset:
        conn.close()
        raise HTTPException(404, "Bem patrimonial não encontrado.")
    a = dict(asset)
    acq_val = round(float(a.get("acquisition_value") or 0.0), 2)
    acc_dep = round(float(a.get("accumulated_depreciation") or 0.0), 2)
    net_val = round(acq_val - acc_dep, 2)
    disp_val = round(float(body.disposal_value or 0.0), 2)
    cap_gain_loss = round(disp_val - net_val, 2)

    conn.execute("""
        UPDATE fixed_assets
        SET status = 'baixado', net_value = 0.0,
            disposal_date = ?, disposal_value = ?, disposal_reason = ?, capital_gain_loss = ?
        WHERE id = ? AND company_id = ?
    """, (body.disposal_date, disp_val, body.disposal_reason, cap_gain_loss, asset_id, company_id))

    entry_id = None
    if body.gerar_contabil:
        def _acc_id(code: str) -> Optional[int]:
            row = conn.execute(
                "SELECT id FROM accounting_accounts WHERE company_id = ? AND code = ? AND active = 1 LIMIT 1",
                (company_id, code),
            ).fetchone()
            return row["id"] if row else None

        cta_banco = _acc_id("1.1.02")
        cta_imob = _acc_id("1.2.03.01")
        cta_dep = _acc_id("1.2.03.04")
        cta_ganho = _acc_id("3.3.01")
        cta_perda = _acc_id("5.5.02")
        lines = []
        if disp_val > 0 and cta_banco:
            lines.append((cta_banco, disp_val, 0.0, f"Valor recebido na baixa de {a['name']}"))
        if acc_dep > 0 and cta_dep:
            lines.append((cta_dep, acc_dep, 0.0, f"Baixa depreciação acumulada de {a['name']}"))
        if acq_val > 0 and cta_imob:
            lines.append((cta_imob, 0.0, acq_val, f"Baixa custo aquisição de {a['name']}"))
        if cap_gain_loss > 0 and cta_ganho:
            lines.append((cta_ganho, 0.0, cap_gain_loss, f"Ganho de capital na baixa de {a['name']}"))
        elif cap_gain_loss < 0 and cta_perda:
            lines.append((cta_perda, abs(cap_gain_loss), 0.0, f"Perda de capital na baixa de {a['name']}"))

        tot_d = round(sum(ln[1] for ln in lines), 2)
        tot_c = round(sum(ln[2] for ln in lines), 2)
        if len(lines) >= 2 and tot_d > 0 and abs(tot_d - tot_c) < 0.02:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO accounting_entries
                    (company_id, entry_date, description, document_number, entry_type, origin_id, total_debit, total_credit)
                VALUES (?, ?, ?, ?, 'automatico', ?, ?, ?)
            """, (company_id, body.disposal_date, f"Baixa Patrimonial ({body.disposal_reason}): {a['name']}",
                  f"BAIXA-{asset_id}", asset_id, tot_d, tot_c))
            entry_id = cur.lastrowid
            for acc_id, d_val, c_val, desc in lines:
                cur.execute("""
                    INSERT INTO accounting_entry_lines (entry_id, account_id, debit, credit, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (entry_id, acc_id, d_val, c_val, desc))

    conn.commit()
    conn.close()
    return {
        "id": asset_id,
        "status": "baixado",
        "net_value_at_disposal": net_val,
        "disposal_value": disp_val,
        "capital_gain_loss": cap_gain_loss,
        "tipo_resultado": "ganho_capital" if cap_gain_loss >= 0 else "perda_capital",
        "accounting_entry_id": entry_id,
    }


@router.get("/api/patrimony/depreciacao-paralela")
def depreciacao_paralela(
    competencia: Optional[str] = None,
    gerar_lalur: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Compara Depreciação Societária (CPC 27) vs. Fiscal (IN RFB 1.700) e gera ajuste opcional no LALUR."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    yr = int(comp[:4])
    assets = rows_to_dicts(conn.execute(
        "SELECT * FROM fixed_assets WHERE company_id = ? AND status = 'ativo' ORDER BY id",
        (company_id,),
    ).fetchall())

    items = []
    tot_soc = 0.0
    tot_fis = 0.0
    for a in assets:
        acq = float(a.get("acquisition_value") or 0.0)
        res = float(a.get("residual_value") or 0.0)
        vida_soc = int(a.get("useful_life_months") or 60)
        vida_fis = int(a.get("tax_useful_life_months") or vida_soc or 60)
        dep_soc = round(_calc_monthly_depreciation(acq, res, vida_soc, a.get("depreciation_method", "linear")), 2)
        dep_fis = round(_calc_monthly_depreciation(acq, 0.0, vida_fis, "linear"), 2)
        diff = round(dep_soc - dep_fis, 2)
        tot_soc = round(tot_soc + dep_soc, 2)
        tot_fis = round(tot_fis + dep_fis, 2)
        items.append({
            "asset_id": a["id"],
            "name": a["name"],
            "vida_societaria_meses": vida_soc,
            "vida_fiscal_meses": vida_fis,
            "depreciacao_societaria": dep_soc,
            "depreciacao_fiscal": dep_fis,
            "diferenca_mensal": diff,
            "efeito_lalur": "adicao" if diff > 0 else ("exclusao" if diff < 0 else "neutro"),
        })

    diff_liq = round(tot_soc - tot_fis, 2)
    efeito = "adicao" if diff_liq > 0 else ("exclusao" if diff_liq < 0 else "neutro")
    lalur_id = None
    if gerar_lalur and abs(diff_liq) > 0:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO lalur_lancamentos
                (company_id, tipo, descricao, valor, ano, parte_b, parte_b_descricao)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (
            company_id,
            efeito,
            f"Diferença Depreciação Societária (CPC 27) vs Fiscal (IN 1.700) — {comp}",
            abs(diff_liq),
            yr,
            "Controle Depreciação Societária vs Fiscal",
        ))
        lalur_id = cur.lastrowid
        conn.commit()
    conn.close()

    return {
        "competencia": comp,
        "items": items,
        "total_societaria": tot_soc,
        "total_fiscal": tot_fis,
        "diferenca_liquida": diff_liq,
        "efeito_lalur": efeito,
        "lalur_lancamento_id": lalur_id,
    }

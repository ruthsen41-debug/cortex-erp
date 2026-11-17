"""
Motor de Escrita Fiscal — Acumuladores, Livros Fiscais, Retenções na Fonte,
Apuração Mensal de Impostos, Guias (DARF / DAE / DAM) e Integração Contábil/Financeira.
"""
import calendar
import json
import re
from datetime import date
from typing import Any, Dict, List, Optional

try:
    from .accounting_autopost import _create_accounting_entry, _get_account_id
    from .tax_calculator import ICMS_INTERNO_UF, get_icms_rate
except ImportError:
    from services.accounting_autopost import _create_accounting_entry, _get_account_id
    from services.tax_calculator import ICMS_INTERNO_UF, get_icms_rate


def _r2(v: float) -> float:
    return round(float(v or 0.0), 2)


def _prev_competencia(comp: str) -> str:
    y, m = int(comp[:4]), int(comp[5:7])
    if m == 1:
        return f"{y - 1}-12"
    return f"{y}-{m - 1:02d}"


def _next_month_due(comp: str, day: int) -> str:
    y, m = int(comp[:4]), int(comp[5:7])
    if m == 12:
        ny, nm = y + 1, 1
    else:
        ny, nm = y, m + 1
    last_day = calendar.monthrange(ny, nm)[1]
    return f"{ny}-{nm:02d}-{min(day, last_day):02d}"


def calculate_fiscal_entry(
    payload: Dict[str, Any],
    accumulator: Optional[Dict[str, Any]],
    company: Dict[str, Any],
) -> Dict[str, Any]:
    """Calcula todos os tributos e retenções de um lançamento fiscal com base no acumulador e regime."""
    acc = accumulator or {}
    tipo = (payload.get("tipo") or acc.get("tipo") or "saida").strip().lower()
    regime = (company.get("regime_tributario") or "simples_nacional").strip().lower()
    uf_orig = (payload.get("uf_origem") or company.get("uf") or "MT").strip().upper()[:2]
    uf_dest = (payload.get("uf_destino") or company.get("uf") or uf_orig).strip().upper()[:2]
    is_interestadual = uf_orig != uf_dest

    valor_produtos = _r2(payload.get("valor_produtos") if payload.get("valor_produtos") is not None
                         else payload.get("valor_contabil") or 0.0)
    valor_desconto = _r2(payload.get("valor_desconto") or 0.0)
    valor_frete = _r2(payload.get("valor_frete") or 0.0)
    valor_contabil = _r2(payload.get("valor_contabil")
                         if payload.get("valor_contabil") is not None
                         else max(0.0, valor_produtos - valor_desconto + valor_frete))
    base_merc = max(0.0, _r2(valor_produtos - valor_desconto + valor_frete)) or valor_contabil

    cst_icms = str(payload.get("cst_icms") or acc.get("cst_icms") or "00")
    cst_pc = str(payload.get("cst_pis_cofins") or acc.get("cst_pis_cofins") or "01")
    cfop = str(payload.get("cfop") or acc.get("cfop_padrao") or ("1102" if tipo == "entrada" else "5102"))

    base_icms = aliq_icms = valor_icms = 0.0
    base_icms_st = valor_icms_st = difal_valor = fcp_valor = 0.0
    base_ipi = aliq_ipi = valor_ipi = 0.0
    base_pc = aliq_pis = valor_pis = aliq_cofins = valor_cofins = 0.0
    base_iss = aliq_iss = valor_iss = iss_retido = 0.0
    irrf_retido = csrf_retido = inss_retido = 0.0

    # 1. Mercadorias (ICMS / ST / DIFAL / IPI)
    if tipo in ("entrada", "saida"):
        reduz = float(acc.get("reduz_base_icms_pct") or 0.0)
        explicit_icms = payload.get("aliquota_icms") is not None
        if explicit_icms:
            aliq_icms = float(payload["aliquota_icms"] or 0.0)
        elif regime in ("simples_nacional", "mei"):
            aliq_icms = 0.0
        elif tipo == "entrada" and not acc.get("gera_credito_icms"):
            aliq_icms = 0.0
        elif is_interestadual:
            aliq_icms = get_icms_rate(uf_orig, uf_dest)
        else:
            aliq_icms = float(acc.get("aliquota_icms") or 0.0) or get_icms_rate(uf_orig, uf_dest)

        if aliq_icms > 0 and (tipo == "saida" or acc.get("gera_credito_icms") or explicit_icms):
            base_icms = _r2(base_merc * (1.0 - max(0.0, min(100.0, reduz)) / 100.0))
            valor_icms = _r2(base_icms * aliq_icms / 100.0)

        # ICMS-ST
        if acc.get("tem_icms_st") or float(payload.get("mva_pct") or 0.0) > 0:
            mva = float(payload.get("mva_pct") if payload.get("mva_pct") is not None else acc.get("mva_pct") or 0.0)
            aliq_st = ICMS_INTERNO_UF.get(uf_dest, 18.0)
            base_icms_st = _r2(base_merc * (1.0 + mva / 100.0))
            icms_proprio_calc = valor_icms if valor_icms > 0 else _r2(base_merc * get_icms_rate(uf_orig, uf_dest) / 100.0)
            valor_icms_st = max(0.0, _r2(base_icms_st * aliq_st / 100.0 - icms_proprio_calc))

        # DIFAL / FCP
        if tipo == "saida" and is_interestadual and payload.get("is_consumidor_final"):
            aliq_inter = get_icms_rate(uf_orig, uf_dest)
            aliq_dest = ICMS_INTERNO_UF.get(uf_dest, 18.0)
            difal_valor = _r2(base_merc * max(0.0, aliq_dest - aliq_inter) / 100.0)
            fcp_valor = _r2(base_merc * 0.01)

        # IPI
        aliq_ipi = float(payload.get("aliquota_ipi") if payload.get("aliquota_ipi") is not None
                         else acc.get("aliquota_ipi") or 0.0)
        if aliq_ipi > 0:
            base_ipi = base_merc
            valor_ipi = _r2(base_ipi * aliq_ipi / 100.0)

    # 2. PIS / COFINS
    explicit_pc = payload.get("aliquota_pis") is not None or payload.get("aliquota_cofins") is not None
    if explicit_pc:
        aliq_pis = float(payload.get("aliquota_pis") or 0.0)
        aliq_cofins = float(payload.get("aliquota_cofins") or 0.0)
    elif regime in ("simples_nacional", "mei"):
        aliq_pis = aliq_cofins = 0.0
    elif regime == "lucro_presumido":
        if tipo in ("saida", "servico_prestado") and cst_pc in ("01", "02", "03", "05"):
            aliq_pis = float(acc.get("aliquota_pis") or 0.65)
            aliq_cofins = float(acc.get("aliquota_cofins") or 3.00)
    elif regime == "lucro_real":
        if tipo in ("saida", "servico_prestado") and cst_pc not in ("04", "06", "07", "08", "09"):
            aliq_pis = 1.65
            aliq_cofins = 7.60
        elif tipo in ("entrada", "servico_tomado") and acc.get("gera_credito_pis_cofins"):
            aliq_pis = float(acc.get("aliquota_pis") or 1.65)
            aliq_cofins = float(acc.get("aliquota_cofins") or 7.60)

    if aliq_pis > 0 or aliq_cofins > 0:
        base_pc = valor_contabil
        valor_pis = _r2(base_pc * aliq_pis / 100.0)
        valor_cofins = _r2(base_pc * aliq_cofins / 100.0)

    # 3. ISS & Retenções na Fonte (IRRF / CSRF 4,65% / INSS 11%)
    aliq_iss = float(payload.get("aliquota_iss") if payload.get("aliquota_iss") is not None
                     else acc.get("aliquota_iss") or 0.0)
    if tipo in ("servico_prestado", "servico_tomado") or aliq_iss > 0:
        if aliq_iss > 0:
            base_iss = valor_contabil
            valor_iss = _r2(base_iss * aliq_iss / 100.0)
            ret_iss = payload.get("retencao_iss") if payload.get("retencao_iss") is not None else acc.get("retencao_iss")
            if ret_iss:
                iss_retido = valor_iss

        ret_irrf_pct = float(payload.get("retencao_irrf_pct") if payload.get("retencao_irrf_pct") is not None
                             else acc.get("retencao_irrf_pct") or 0.0)
        if ret_irrf_pct > 0:
            calc_ir = _r2(valor_contabil * ret_irrf_pct / 100.0)
            irrf_retido = calc_ir if calc_ir >= 10.0 else 0.0

        ret_csrf_pct = float(payload.get("retencao_csrf_pct") if payload.get("retencao_csrf_pct") is not None
                             else acc.get("retencao_csrf_pct") or 0.0)
        if ret_csrf_pct > 0:
            calc_csrf = _r2(valor_contabil * ret_csrf_pct / 100.0)
            csrf_retido = calc_csrf if calc_csrf > 10.0 else 0.0

        ret_inss_pct = float(payload.get("retencao_inss_pct") if payload.get("retencao_inss_pct") is not None
                             else acc.get("retencao_inss_pct") or 0.0)
        if ret_inss_pct > 0:
            inss_retido = _r2(valor_contabil * ret_inss_pct / 100.0)

    # 4. Reforma Tributária (IBS / CBS — LC 214/2025 teste 2026)
    aliq_ibs = float(payload.get("aliquota_ibs_teste") if payload.get("aliquota_ibs_teste") is not None
                     else acc.get("aliquota_ibs_teste", 0.1) or 0.0)
    aliq_cbs = float(payload.get("aliquota_cbs_teste") if payload.get("aliquota_cbs_teste") is not None
                     else acc.get("aliquota_cbs_teste", 0.9) or 0.0)
    ibs_valor = _r2(valor_contabil * aliq_ibs / 100.0)
    cbs_valor = _r2(valor_contabil * aliq_cbs / 100.0)

    return {
        "tipo": tipo,
        "cfop": cfop,
        "cst_icms": cst_icms,
        "cst_pis_cofins": cst_pc,
        "uf_origem": uf_orig,
        "uf_destino": uf_dest,
        "valor_contabil": valor_contabil,
        "valor_produtos": valor_produtos,
        "valor_desconto": valor_desconto,
        "valor_frete": valor_frete,
        "base_icms": base_icms,
        "aliquota_icms": aliq_icms,
        "valor_icms": valor_icms,
        "base_icms_st": base_icms_st,
        "valor_icms_st": valor_icms_st,
        "difal_valor": difal_valor,
        "fcp_valor": fcp_valor,
        "base_ipi": base_ipi,
        "aliquota_ipi": aliq_ipi,
        "valor_ipi": valor_ipi,
        "base_pis_cofins": base_pc,
        "aliquota_pis": aliq_pis,
        "valor_pis": valor_pis,
        "aliquota_cofins": aliq_cofins,
        "valor_cofins": valor_cofins,
        "base_iss": base_iss,
        "aliquota_iss": aliq_iss,
        "valor_iss": valor_iss,
        "iss_retido": iss_retido,
        "irrf_retido": irrf_retido,
        "csrf_retido": csrf_retido,
        "inss_retido": inss_retido,
        "ibs_valor": ibs_valor,
        "cbs_valor": cbs_valor,
    }


def post_fiscal_entry_accounting(
    conn,
    company_id: int,
    entry: Dict[str, Any],
    accumulator: Optional[Dict[str, Any]],
) -> Optional[int]:
    """Gera lançamento contábil automático em partidas dobradas para a nota escriturada."""
    acc = accumulator or {}
    tipo = entry.get("tipo", "saida")
    default_deb = "1.1.06" if tipo == "entrada" else ("5.2.07" if tipo == "servico_tomado" else "1.1.04")
    default_cred = "2.1.01" if tipo in ("entrada", "servico_tomado") else ("3.1.02" if tipo == "servico_prestado" else "3.1.01")

    deb_code = acc.get("conta_contabil_debito") or default_deb
    cred_code = acc.get("conta_contabil_credito") or default_cred

    deb_id = _get_account_id(conn, deb_code, company_id) or _get_account_id(conn, default_deb, company_id)
    cred_id = _get_account_id(conn, cred_code, company_id) or _get_account_id(conn, default_cred, company_id)
    if not deb_id or not cred_id:
        return None

    val = _r2(entry.get("valor_contabil") or 0.0)
    if val <= 0:
        return None

    lines = [
        {"account_id": deb_id, "debit": val, "credit": 0.0,
         "description": f"Escrita Fiscal Doc {entry.get('numero', '')}"},
        {"account_id": cred_id, "debit": 0.0, "credit": val,
         "description": f"Escrita Fiscal Doc {entry.get('numero', '')}"},
    ]
    desc = f"Escrituração Fiscal ({tipo.upper()}) NF {entry.get('numero', '')} — {entry.get('participante_nome', '')}".strip()
    return _create_accounting_entry(
        conn,
        company_id,
        entry.get("data_escrituracao") or entry.get("data_emissao") or date.today().isoformat(),
        desc,
        str(entry.get("numero") or ""),
        lines,
        origin_id=entry.get("id"),
    )


def _insert_fiscal_entry(
    conn,
    company_id: int,
    payload: Dict[str, Any],
    acc: Optional[Dict[str, Any]],
    company: Dict[str, Any],
) -> Dict[str, Any]:
    calc = calculate_fiscal_entry(payload, acc, company)
    dt_emi = str(payload.get("data_emissao") or date.today().isoformat())[:10]
    dt_esc = str(payload.get("data_escrituracao") or dt_emi)[:10]
    comp = str(payload.get("competencia") or dt_esc[:7])

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fiscal_entries (
            company_id, tipo, accumulator_id, accumulator_code, modelo, serie, numero, chave_acesso,
            data_emissao, data_escrituracao, competencia, contact_id, participante_nome, participante_doc,
            uf_origem, uf_destino, cfop, ncm, valor_contabil, valor_produtos, valor_desconto, valor_frete,
            cst_icms, base_icms, aliquota_icms, valor_icms, base_icms_st, valor_icms_st,
            difal_valor, fcp_valor, base_ipi, aliquota_ipi, valor_ipi,
            cst_pis_cofins, base_pis_cofins, aliquota_pis, valor_pis, aliquota_cofins, valor_cofins,
            base_iss, aliquota_iss, valor_iss, iss_retido, irrf_retido, csrf_retido, inss_retido,
            ibs_valor, cbs_valor, origem_tipo, origem_id, status, observacoes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        company_id, calc["tipo"], acc.get("id") if acc else None, acc.get("codigo", "") if acc else "",
        str(payload.get("modelo") or "55"), str(payload.get("serie") or "1"),
        str(payload.get("numero") or "1"), str(payload.get("chave_acesso") or ""),
        dt_emi, dt_esc, comp, payload.get("contact_id"),
        str(payload.get("participante_nome") or ""), str(payload.get("participante_doc") or ""),
        calc["uf_origem"], calc["uf_destino"], calc["cfop"], str(payload.get("ncm") or ""),
        calc["valor_contabil"], calc["valor_produtos"], calc["valor_desconto"], calc["valor_frete"],
        calc["cst_icms"], calc["base_icms"], calc["aliquota_icms"], calc["valor_icms"],
        calc["base_icms_st"], calc["valor_icms_st"], calc["difal_valor"], calc["fcp_valor"],
        calc["base_ipi"], calc["aliquota_ipi"], calc["valor_ipi"],
        calc["cst_pis_cofins"], calc["base_pis_cofins"], calc["aliquota_pis"], calc["valor_pis"],
        calc["aliquota_cofins"], calc["valor_cofins"], calc["base_iss"], calc["aliquota_iss"],
        calc["valor_iss"], calc["iss_retido"], calc["irrf_retido"], calc["csrf_retido"],
        calc["inss_retido"], calc["ibs_valor"], calc["cbs_valor"],
        str(payload.get("origem_tipo") or "manual"), payload.get("origem_id"),
        "escriturado", str(payload.get("observacoes") or ""),
    ))
    entry_id = cur.lastrowid
    row = dict(conn.execute("SELECT * FROM fiscal_entries WHERE id = ?", (entry_id,)).fetchone())

    if payload.get("gerar_contabil", True):
        ae_id = post_fiscal_entry_accounting(conn, company_id, row, acc)
        if ae_id:
            conn.execute("UPDATE fiscal_entries SET accounting_entry_id = ? WHERE id = ?", (ae_id, entry_id))
            row["accounting_entry_id"] = ae_id

    if payload.get("gerar_financeiro"):
        ret_total = _r2(row["irrf_retido"] + row["csrf_retido"] + row["inss_retido"] + row["iss_retido"])
        val_liq = max(0.0, _r2(row["valor_contabil"] - ret_total))
        fin_type = "despesa" if row["tipo"] in ("entrada", "servico_tomado") else "receita"
        cur.execute("""
            INSERT INTO financial_entries (
                company_id, type, description, contact_id, competence_date, due_date,
                amount, status, document_number, origin_type, origin_id
            ) VALUES (?,?,?,?,?,?,?,'pendente',?,'escrita_fiscal',?)
        """, (
            company_id, fin_type,
            f"Doc Fiscal {row['modelo']} #{row['numero']} — {row['participante_nome']}".strip(),
            row.get("contact_id"), dt_esc, dt_esc, val_liq, row["numero"], entry_id,
        ))
        fe_id = cur.lastrowid
        conn.execute("UPDATE fiscal_entries SET financial_entry_id = ? WHERE id = ?", (fe_id, entry_id))
        row["financial_entry_id"] = fe_id

    return row


def sync_erp_to_fiscal_books(conn, company_id: int, competencia: str) -> Dict[str, Any]:
    """Importa NF-e/NFC-e/NFS-e emitidas, Manifesto do Destinatário e Compras recebidas para os livros fiscais."""
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    accs = {
        r["codigo"]: dict(r)
        for r in conn.execute("SELECT * FROM fiscal_accumulators WHERE company_id = ?", (company_id,)).fetchall()
    }
    created_saidas = 0
    created_entradas = 0

    # 1. Saídas (invoices autorizadas)
    invs = [dict(r) for r in conn.execute("""
        SELECT * FROM invoices
        WHERE company_id = ? AND status = 'autorizada' AND substr(issued_at, 1, 7) = ?
    """, (company_id, competencia)).fetchall()]
    for inv in invs:
        exists = conn.execute("""
            SELECT id FROM fiscal_entries
            WHERE company_id = ? AND origem_tipo = 'invoice' AND origem_id = ?
        """, (company_id, inv["id"])).fetchone()
        if exists:
            continue
        is_nfse = "nfse" in str(inv.get("model") or "").lower()
        acc = accs.get("301" if is_nfse else "201")
        modelo = "NFS" if is_nfse else ("65" if "65" in str(inv.get("model") or "") else "55")
        payload = {
            "tipo": "servico_prestado" if is_nfse else "saida",
            "modelo": modelo,
            "serie": str(inv.get("series") or "1"),
            "numero": str(inv.get("number") or inv["id"]),
            "chave_acesso": inv.get("access_key") or "",
            "data_emissao": str(inv.get("issued_at") or f"{competencia}-01")[:10],
            "data_escrituracao": str(inv.get("issued_at") or f"{competencia}-01")[:10],
            "competencia": competencia,
            "contact_id": inv.get("contact_id"),
            "participante_nome": inv.get("recipient_name") or "",
            "participante_doc": inv.get("recipient_doc") or "",
            "uf_origem": company.get("uf") or "MT",
            "uf_destino": inv.get("recipient_uf") or company.get("uf") or "MT",
            "valor_contabil": float(inv.get("total_invoice") or 0.0),
            "valor_produtos": float(inv.get("total_products") or inv.get("total_invoice") or 0.0),
            "valor_desconto": float(inv.get("total_discounts") or 0.0),
            "valor_frete": float(inv.get("total_shipping") or 0.0),
            "origem_tipo": "invoice",
            "origem_id": inv["id"],
            "gerar_contabil": True,
        }
        _insert_fiscal_entry(conn, company_id, payload, acc, company)
        created_saidas += 1

    # 2. Entradas do Manifesto do Destinatário
    mans = [dict(r) for r in conn.execute("""
        SELECT * FROM nfe_manifest
        WHERE company_id = ? AND status != 'desconhecimento' AND substr(data_emissao, 1, 7) = ?
    """, (company_id, competencia)).fetchall()]
    for m in mans:
        exists = conn.execute("""
            SELECT id FROM fiscal_entries
            WHERE company_id = ? AND origem_tipo = 'nfe_manifest' AND origem_id = ?
        """, (company_id, m["id"])).fetchone()
        if exists:
            continue
        acc = accs.get("101")
        payload = {
            "tipo": "entrada",
            "modelo": "55",
            "serie": str(m.get("serie") or "1"),
            "numero": str(m.get("numero") or m["id"]),
            "chave_acesso": m.get("chave") or "",
            "data_emissao": str(m.get("data_emissao") or f"{competencia}-01")[:10],
            "data_escrituracao": str(m.get("data_emissao") or f"{competencia}-01")[:10],
            "competencia": competencia,
            "participante_nome": m.get("emit_nome") or "",
            "participante_doc": m.get("emit_cnpj") or "",
            "valor_contabil": float(m.get("total_nota") or 0.0),
            "valor_produtos": float(m.get("total_nota") or 0.0),
            "origem_tipo": "nfe_manifest",
            "origem_id": m["id"],
            "gerar_contabil": True,
        }
        _insert_fiscal_entry(conn, company_id, payload, acc, company)
        created_entradas += 1

    # 3. Entradas de Pedidos de Compra recebidos
    pos = [dict(r) for r in conn.execute("""
        SELECT po.*, c.name as supplier_name, c.document as supplier_doc, c.state as supplier_uf
        FROM purchase_orders po
        LEFT JOIN contacts c ON c.id = po.supplier_id
        WHERE po.company_id = ? AND po.status = 'recebido' AND substr(po.created_at, 1, 7) = ?
    """, (company_id, competencia)).fetchall()]
    for po in pos:
        exists = conn.execute("""
            SELECT id FROM fiscal_entries
            WHERE company_id = ? AND origem_tipo = 'purchase_order' AND origem_id = ?
        """, (company_id, po["id"])).fetchone()
        if exists:
            continue
        acc = accs.get("101")
        dt = str(po.get("created_at") or f"{competencia}-01")[:10]
        payload = {
            "tipo": "entrada",
            "modelo": "55",
            "serie": "1",
            "numero": str(po.get("order_number") or po["id"]),
            "data_emissao": dt,
            "data_escrituracao": dt,
            "competencia": competencia,
            "contact_id": po.get("supplier_id"),
            "participante_nome": po.get("supplier_name") or "Fornecedor",
            "participante_doc": po.get("supplier_doc") or "",
            "uf_origem": po.get("supplier_uf") or company.get("uf") or "MT",
            "uf_destino": company.get("uf") or "MT",
            "valor_contabil": float(po.get("total_value") or 0.0),
            "valor_produtos": float(po.get("total_value") or 0.0),
            "origem_tipo": "purchase_order",
            "origem_id": po["id"],
            "gerar_contabil": True,
        }
        _insert_fiscal_entry(conn, company_id, payload, acc, company)
        created_entradas += 1

    conn.commit()
    return {
        "competencia": competencia,
        "saidas_escrituradas": created_saidas,
        "entradas_escrituradas": created_entradas,
        "total_escriturado": created_saidas + created_entradas,
    }


def apurar_impostos_mes(conn, company_id: int, competencia: str) -> List[Dict[str, Any]]:
    """Apura todos os impostos da competência com transporte de saldo credor anterior e grava em fiscal_apurations."""
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    regime = (company.get("regime_tributario") or "simples_nacional").strip().lower()
    entries = [dict(r) for r in conn.execute(
        "SELECT * FROM fiscal_entries WHERE company_id = ? AND competencia = ? AND status != 'cancelado'",
        (company_id, competencia),
    ).fetchall()]
    accs = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM fiscal_accumulators WHERE company_id = ?", (company_id,)).fetchall()
    }

    prev_comp = _prev_competencia(competencia)
    prev_rows = {
        r["imposto"]: dict(r)
        for r in conn.execute(
            "SELECT * FROM fiscal_apurations WHERE company_id = ? AND competencia = ?",
            (company_id, prev_comp),
        ).fetchall()
    }

    entradas = [e for e in entries if e["tipo"] == "entrada"]
    saidas = [e for e in entries if e["tipo"] == "saida"]
    serv_prest = [e for e in entries if e["tipo"] == "servico_prestado"]
    serv_tom = [e for e in entries if e["tipo"] == "servico_tomado"]

    # Crédito 1/48 PIS/COFINS sobre imobilizado (Bloco F EFD-Contribuições) para Lucro Real
    cred_ativo_pis = cred_ativo_cof = 0.0
    if regime == "lucro_real":
        assets = [dict(a) for a in conn.execute(
            "SELECT acquisition_value FROM fixed_assets WHERE company_id = ? AND status IN ('ativo', 'depreciado')",
            (company_id,),
        ).fetchall()]
        total_ativos = sum(float(a.get("acquisition_value") or 0) for a in assets)
        if total_ativos > 0:
            parcela_48 = total_ativos / 48.0
            cred_ativo_pis = _r2(parcela_48 * 0.0165)
            cred_ativo_cof = _r2(parcela_48 * 0.0760)

    def _cred_icms_entry(e: Dict[str, Any]) -> float:
        acc = accs.get(e.get("accumulator_id"))
        if acc and not acc.get("gera_credito_icms"):
            return 0.0
        return float(e.get("valor_icms") or 0.0)

    def _cred_pc_entry(e: Dict[str, Any], field: str) -> float:
        acc = accs.get(e.get("accumulator_id"))
        if acc and not acc.get("gera_credito_pis_cofins"):
            return 0.0
        return float(e.get(field) or 0.0)

    # 1. ICMS
    icms_deb = _r2(sum(float(e.get("valor_icms") or 0) + float(e.get("difal_valor") or 0) for e in saidas))
    icms_cred = _r2(sum(_cred_icms_entry(e) for e in entradas))
    icms_prev = float((prev_rows.get("ICMS") or {}).get("saldo_credor_transportar") or 0.0)
    icms_liq = _r2(icms_deb - icms_cred - icms_prev)

    # 2. IPI
    ipi_deb = _r2(sum(float(e.get("valor_ipi") or 0) for e in saidas))
    ipi_cred = _r2(sum(float(e.get("valor_ipi") or 0) for e in entradas))
    ipi_prev = float((prev_rows.get("IPI") or {}).get("saldo_credor_transportar") or 0.0)
    ipi_liq = _r2(ipi_deb - ipi_cred - ipi_prev)

    # 3. PIS / COFINS
    pis_deb = _r2(sum(float(e.get("valor_pis") or 0) for e in saidas + serv_prest))
    pis_cred = _r2(sum(_cred_pc_entry(e, "valor_pis") for e in entradas + serv_tom) + cred_ativo_pis)
    pis_prev = float((prev_rows.get("PIS") or {}).get("saldo_credor_transportar") or 0.0)
    pis_liq = _r2(pis_deb - pis_cred - pis_prev)

    cof_deb = _r2(sum(float(e.get("valor_cofins") or 0) for e in saidas + serv_prest))
    cof_cred = _r2(sum(_cred_pc_entry(e, "valor_cofins") for e in entradas + serv_tom) + cred_ativo_cof)
    cof_prev = float((prev_rows.get("COFINS") or {}).get("saldo_credor_transportar") or 0.0)
    cof_liq = _r2(cof_deb - cof_cred - cof_prev)

    # 4. ISS (próprio não retido + retido na fonte de terceiros)
    iss_deb = _r2(
        sum(max(0.0, float(e.get("valor_iss") or 0) - float(e.get("iss_retido") or 0)) for e in serv_prest)
        + sum(float(e.get("iss_retido") or 0) for e in serv_tom)
    )

    # 5. Retenções na Fonte (Serviços Tomados)
    irrf_ret = _r2(sum(float(e.get("irrf_retido") or 0) for e in serv_tom))
    csrf_ret = _r2(sum(float(e.get("csrf_retido") or 0) for e in serv_tom))
    inss_ret = _r2(sum(float(e.get("inss_retido") or 0) for e in serv_tom))

    # 6. IRPJ / CSLL (Estimativa / Presunção mensal)
    rec_merc = sum(float(e.get("valor_contabil") or 0) for e in saidas)
    rec_serv = sum(float(e.get("valor_contabil") or 0) for e in serv_prest)
    irpj_val = csll_val = 0.0
    if regime in ("lucro_presumido", "lucro_real"):
        base_irpj = _r2(rec_merc * 0.08 + rec_serv * 0.32)
        base_csll = _r2(rec_merc * 0.12 + rec_serv * 0.32)
        irpj_val = _r2(base_irpj * 0.15 + max(0.0, base_irpj - 20000.0) * 0.10)
        csll_val = _r2(base_csll * 0.09)

    # 7. IBS / CBS (Reforma Tributária - Teste)
    ibs_deb = _r2(sum(float(e.get("ibs_valor") or 0) for e in saidas + serv_prest))
    ibs_cred = _r2(sum(float(e.get("ibs_valor") or 0) for e in entradas + serv_tom))
    cbs_deb = _r2(sum(float(e.get("cbs_valor") or 0) for e in saidas + serv_prest))
    cbs_cred = _r2(sum(float(e.get("cbs_valor") or 0) for e in entradas + serv_tom))
    ibs_cbs_deb = _r2(ibs_deb + cbs_deb)
    ibs_cbs_cred = _r2(ibs_cred + cbs_cred)
    ibs_cbs_liq = _r2(ibs_cbs_deb - ibs_cbs_cred)

    rows_spec = [
        ("ICMS", icms_deb, icms_cred, 0.0, icms_prev, max(0.0, icms_liq), max(0.0, -icms_liq),
         "1112", _next_month_due(competencia, 15), {"uf": company.get("uf", "MT")}),
        ("IPI", ipi_deb, ipi_cred, 0.0, ipi_prev, max(0.0, ipi_liq), max(0.0, -ipi_liq),
         "1097", _next_month_due(competencia, 25), {}),
        ("PIS", pis_deb, pis_cred, 0.0, pis_prev, max(0.0, pis_liq), max(0.0, -pis_liq),
         "6912" if regime == "lucro_real" else "8109", _next_month_due(competencia, 25),
         {"credito_ativo_1_48": cred_ativo_pis}),
        ("COFINS", cof_deb, cof_cred, 0.0, cof_prev, max(0.0, cof_liq), max(0.0, -cof_liq),
         "5856" if regime == "lucro_real" else "2172", _next_month_due(competencia, 25),
         {"credito_ativo_1_48": cred_ativo_cof}),
        ("ISS", iss_deb, 0.0, 0.0, 0.0, iss_deb, 0.0, "ISS-MUN", _next_month_due(competencia, 10), {}),
        ("IRRF_RET", irrf_ret, 0.0, 0.0, 0.0, irrf_ret, 0.0, "1708", _next_month_due(competencia, 20), {}),
        ("CSRF_RET", csrf_ret, 0.0, 0.0, 0.0, csrf_ret, 0.0, "5952", _next_month_due(competencia, 20), {}),
        ("INSS_RET", inss_ret, 0.0, 0.0, 0.0, inss_ret, 0.0, "2631", _next_month_due(competencia, 20), {}),
        ("IRPJ", irpj_val, 0.0, 0.0, 0.0, irpj_val, 0.0,
         "2362" if regime == "lucro_real" else "2089", _next_month_due(competencia, 31),
         {"receita_mercadorias": _r2(rec_merc), "receita_servicos": _r2(rec_serv)}),
        ("CSLL", csll_val, 0.0, 0.0, 0.0, csll_val, 0.0,
         "2484" if regime == "lucro_real" else "2372", _next_month_due(competencia, 31), {}),
        ("IBS_CBS", ibs_cbs_deb, ibs_cbs_cred, 0.0, 0.0, max(0.0, ibs_cbs_liq), max(0.0, -ibs_cbs_liq),
         "IBS-CBS-2026", _next_month_due(competencia, 25),
         {"ibs_debito": ibs_deb, "cbs_debito": cbs_deb, "ibs_credito": ibs_cred, "cbs_credito": cbs_cred}),
    ]

    out: List[Dict[str, Any]] = []
    for imp, deb, cred, ded, prev_sc, rec, transp, cod_rec, venc, mem in rows_spec:
        existing = conn.execute(
            "SELECT id, financial_entry_id FROM fiscal_apurations WHERE company_id = ? AND competencia = ? AND imposto = ?",
            (company_id, competencia, imp),
        ).fetchone()
        mem_json = json.dumps(mem, ensure_ascii=False)
        if existing:
            conn.execute("""
                UPDATE fiscal_apurations SET
                    regime=?, debitos=?, creditos=?, deducoes=?, saldo_credor_anterior=?,
                    valor_a_recolher=?, saldo_credor_transportar=?, codigo_receita=?,
                    vencimento=?, memoria_calculo=?
                WHERE id=?
            """, (regime, deb, cred, ded, prev_sc, rec, transp, cod_rec, venc, mem_json, existing["id"]))
            ap_id = existing["id"]
        else:
            cur = conn.execute("""
                INSERT INTO fiscal_apurations (
                    company_id, competencia, imposto, regime, debitos, creditos, deducoes,
                    saldo_credor_anterior, valor_a_recolher, saldo_credor_transportar,
                    codigo_receita, vencimento, status, memoria_calculo
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'fechada',?)
            """, (company_id, competencia, imp, regime, deb, cred, ded, prev_sc, rec, transp, cod_rec, venc, mem_json))
            ap_id = cur.lastrowid
        row = dict(conn.execute("SELECT * FROM fiscal_apurations WHERE id = ?", (ap_id,)).fetchone())
        out.append(row)

    conn.commit()
    return out


def gerar_guia_html(company: Dict[str, Any], apuration: Dict[str, Any]) -> str:
    """Gera guia de recolhimento HTML imprimível (DARF Federal, DAE/GNRE Estadual ou DAM Municipal)."""
    imposto = apuration.get("imposto", "TRIBUTO")
    tipo_guia = (
        "DAE / GNRE — GUIA DE RECOLHIMENTO ESTADUAL" if imposto == "ICMS"
        else "DAM — DOCUMENTO DE ARRECADAÇÃO MUNICIPAL" if imposto == "ISS"
        else "DARF — DOCUMENTO DE ARRECADAÇÃO DE RECEITAS FEDERAIS"
    )
    cnpj = re.sub(r"\D", "", str(company.get("cnpj") or "00000000000000")).zfill(14)
    val = float(apuration.get("valor_a_recolher") or 0.0)
    val_brl = f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    cod_rec = apuration.get("codigo_receita") or "0000"
    comp = apuration.get("competencia") or ""
    venc = apuration.get("vencimento") or ""
    cents_str = str(int(round(val * 100))).zfill(11)[-11:]
    bar_code = f"85810000000 {cents_str[:4]} {cod_rec.zfill(4)[:4]}0001 {cnpj[:11]} {comp.replace('-', '')}01"
    pix_payload = f"00020126580014BR.GOV.BCB.PIX0136CORTEX-DARF-{cod_rec}-{comp}520400005303986540{val:.2f}"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>{tipo_guia} — {imposto} ({comp})</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; color: #0f172a; margin: 24px; font-size: 13px; }}
    .guia {{ max-width: 780px; margin: 0 auto; border: 2px solid #0f172a; padding: 20px; }}
    .hdr {{ display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0f172a; padding-bottom:10px; margin-bottom:14px; }}
    .hdr h1 {{ font-size:15px; margin:0; text-transform:uppercase; }}
    .grid {{ display:grid; grid-template-columns: repeat(2, 1fr); gap:10px; margin-bottom:14px; }}
    .box {{ border:1px solid #64748b; padding:8px 10px; }}
    .lbl {{ display:block; font-size:10px; text-transform:uppercase; color:#64748b; margin-bottom:3px; }}
    .val {{ font-size:14px; font-weight:bold; }}
    .barcode {{ border:1px dashed #334155; padding:12px; background:#f8fafc; font-family: monospace; text-align:center; margin-top:14px; }}
    @media print {{ .no-print {{ display:none; }} }}
  </style>
</head>
<body>
  <div class="no-print" style="max-width:780px;margin:0 auto 12px;text-align:right">
    <button onclick="window.print()" style="padding:8px 16px;cursor:pointer;font-weight:bold">Imprimir Guia / Salvar PDF</button>
  </div>
  <div class="guia">
    <div class="hdr">
      <div>
        <h1>{tipo_guia}</h1>
        <div style="font-size:11px;color:#475569">Tributo: <strong>{imposto}</strong> · Competência: <strong>{comp}</strong></div>
      </div>
      <div style="text-align:right"><span class="lbl">Código Receita</span><span class="val">{cod_rec}</span></div>
    </div>
    <div class="grid">
      <div class="box"><span class="lbl">Contribuinte / Razão Social</span><div class="val">{company.get('razao_social', '')}</div></div>
      <div class="box"><span class="lbl">CNPJ</span><div class="val">{company.get('cnpj', '')}</div></div>
      <div class="box"><span class="lbl">Período de Apuração</span><div class="val">{comp}</div></div>
      <div class="box"><span class="lbl">Data de Vencimento</span><div class="val">{venc}</div></div>
      <div class="box"><span class="lbl">Débitos / Apurado</span><div class="val">R$ {float(apuration.get('debitos') or 0):,.2f}</div></div>
      <div class="box"><span class="lbl">Créditos / Saldo Anterior</span><div class="val">R$ {float(apuration.get('creditos') or 0) + float(apuration.get('saldo_credor_anterior') or 0):,.2f}</div></div>
      <div class="box" style="grid-column:span 2;background:#ecfdf5"><span class="lbl">Valor Total a Recolher</span><div class="val" style="font-size:18px;color:#047857">{val_brl}</div></div>
    </div>
    <div class="barcode">
      <div style="font-size:11px;color:#64748b;margin-bottom:4px">Linha Digitável / Código de Barras</div>
      <div style="font-size:14px;font-weight:bold;letter-spacing:1px">{bar_code}</div>
      <div style="font-size:10px;color:#64748b;margin-top:8px">Pix Copia e Cola: {pix_payload}</div>
    </div>
  </div>
</body>
</html>"""

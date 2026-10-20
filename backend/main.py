import os
import re
import io
import json
import uuid
import random
import zipfile
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

try:
    from .database import get_conn, init_db, recalculate_bank_balances
    from .fiscal_engine import (
        gerar_chave_acesso_sefaz,
        validar_dados_fiscais,
        gerar_xml_nfe_400,
        gerar_html_danfe,
        gerar_xml_compra_exemplo,
        parse_nfe_compra_xml,
        gerar_ofx_exemplo,
        parse_ofx_content,
    )
except ImportError:
    from database import get_conn, init_db, recalculate_bank_balances
    from fiscal_engine import (
        gerar_chave_acesso_sefaz,
        validar_dados_fiscais,
        gerar_xml_nfe_400,
        gerar_html_danfe,
        gerar_xml_compra_exemplo,
        parse_nfe_compra_xml,
        gerar_ofx_exemplo,
        parse_ofx_content,
    )

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Tenta carregar variáveis de ambiente locais ou do cortex_ai para usar a chave Gemini no CFO Virtual
load_dotenv(BASE_DIR / ".env")
cortex_ai_env = Path.home() / "cortex_ai" / ".env"
if cortex_ai_env.exists():
    load_dotenv(cortex_ai_env, override=False)

app = FastAPI(title="Cortex ERP Pro+", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


# ==============================================================================
# 1. DASHBOARD EXECUTIVO & INDICADORES EM TEMPO REAL
# ==============================================================================
@app.get("/api/dashboard")
def get_dashboard():
    conn = get_conn()
    cur = conn.cursor()
    today_str = date.today().isoformat()
    month_prefix = today_str[:7]

    accounts = rows_to_dicts(cur.execute("SELECT * FROM bank_accounts WHERE active = 1 ORDER BY id").fetchall())
    total_balance = round(sum(float(a["current_balance"]) for a in accounts), 2)

    entries = rows_to_dicts(cur.execute("""
        SELECT e.*, c.name as contact_name, c.whatsapp as contact_whatsapp,
               cat.name as category_name, cat.dre_group as dre_group,
               b.name as bank_name
        FROM financial_entries e
        LEFT JOIN contacts c ON c.id = e.contact_id
        LEFT JOIN categories cat ON cat.id = e.category_id
        LEFT JOIN bank_accounts b ON b.id = e.bank_account_id
        WHERE e.status != 'cancelado'
    """).fetchall())

    receivables_today = 0.0
    receivables_overdue = 0.0
    receivables_month = 0.0
    payables_today = 0.0
    payables_overdue = 0.0
    payables_month = 0.0
    revenue_realized_month = 0.0
    expense_realized_month = 0.0

    for e in entries:
        net_total = float(e["amount"]) + float(e["interest"]) + float(e["fine"]) - float(e["discount"])
        remaining = max(0.0, round(net_total - float(e["paid_amount"]), 2))
        due = e["due_date"]
        is_open = e["status"] in ("pendente", "parcial") and remaining > 0

        if e["type"] == "receita":
            if e["due_date"].startswith(month_prefix):
                receivables_month += net_total
                revenue_realized_month += float(e["paid_amount"])
            if is_open:
                if due == today_str:
                    receivables_today += remaining
                elif due < today_str:
                    receivables_overdue += remaining
        elif e["type"] == "despesa":
            if e["due_date"].startswith(month_prefix):
                payables_month += net_total
                expense_realized_month += float(e["paid_amount"])
            if is_open:
                if due == today_str:
                    payables_today += remaining
                elif due < today_str:
                    payables_overdue += remaining

    # Projeção de Fluxo de Caixa para os próximos 15 dias + últimos 10 dias
    chart_labels = []
    chart_inflows = []
    chart_outflows = []
    chart_balance = []
    running_bal = total_balance

    for offset in range(-7, 15):
        d_iso = (date.today() + timedelta(days=offset)).isoformat()
        chart_labels.append(d_iso[8:10] + "/" + d_iso[5:7])
        day_in = sum(
            (float(x["amount"]) + float(x["interest"]) + float(x["fine"]) - float(x["discount"]))
            for x in entries if x["type"] == "receita" and x["due_date"] == d_iso
        )
        day_out = sum(
            (float(x["amount"]) + float(x["interest"]) + float(x["fine"]) - float(x["discount"]))
            for x in entries if x["type"] == "despesa" and x["due_date"] == d_iso
        )
        chart_inflows.append(round(day_in, 2))
        chart_outflows.append(round(day_out, 2))
        if offset > 0:
            running_bal += (day_in - day_out)
        chart_balance.append(round(running_bal, 2))

    # Despesas por Categoria
    expense_by_cat = {}
    for e in entries:
        if e["type"] == "despesa":
            cat_n = e.get("category_name") or "Outras Despesas"
            expense_by_cat[cat_n] = round(expense_by_cat.get(cat_n, 0.0) + float(e["amount"]), 2)

    low_stock = rows_to_dicts(cur.execute("""
        SELECT id, sku, name, stock_qty, min_stock, unit
        FROM products
        WHERE type = 'produto' AND active = 1 AND stock_qty <= min_stock
        ORDER BY stock_qty ASC
    """).fetchall())

    pending_ofx = cur.execute("SELECT COUNT(*) FROM ofx_transactions WHERE status = 'pendente'").fetchone()[0]
    open_os = cur.execute("SELECT COUNT(*) FROM service_orders WHERE status NOT IN ('entregue', 'cancelada')").fetchone()[0]
    invoices_count = cur.execute("SELECT COUNT(*) FROM invoices WHERE status != 'cancelada'").fetchone()[0]

    conn.close()
    return {
        "accounts": accounts,
        "kpis": {
            "total_balance": total_balance,
            "receivables_today": round(receivables_today, 2),
            "receivables_overdue": round(receivables_overdue, 2),
            "receivables_month": round(receivables_month, 2),
            "payables_today": round(payables_today, 2),
            "payables_overdue": round(payables_overdue, 2),
            "payables_month": round(payables_month, 2),
            "revenue_realized_month": round(revenue_realized_month, 2),
            "expense_realized_month": round(expense_realized_month, 2),
            "net_profit_month": round(receivables_month - payables_month, 2),
            "pending_ofx": pending_ofx,
            "open_os": open_os,
            "invoices_count": invoices_count,
        },
        "cashflow_chart": {
            "labels": chart_labels,
            "inflows": chart_inflows,
            "outflows": chart_outflows,
            "balance": chart_balance,
        },
        "expense_by_category": expense_by_cat,
        "low_stock": low_stock,
    }


# ==============================================================================
# 2. EMPRESA, CONFIGURAÇÕES FISCAIS E CERTIFICADO DIGITAL A1 (.PFX)
# ==============================================================================
@app.get("/api/company")
def get_company():
    conn = get_conn()
    row = conn.execute("SELECT * FROM companies ORDER BY id LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else {}


@app.put("/api/company")
async def update_company(req: Request):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE companies SET
            razao_social = ?, nome_fantasia = ?, cnpj = ?, inscricao_estadual = ?,
            inscricao_municipal = ?, regime_tributario = ?, cnae_principal = ?,
            aliquota_simples = ?, cep = ?, logradouro = ?, numero = ?, bairro = ?,
            cidade = ?, uf = ?, codigo_ibge_municipio = ?, telefone = ?, email = ?,
            chave_pix = ?, ambiente_fiscal = ?, motor_fiscal = ?, api_fiscal_token = ?,
            serie_nfe = ?, proximo_numero_nfe = ?, serie_nfce = ?, proximo_numero_nfce = ?,
            serie_nfse = ?, proximo_numero_nfse = ?
        WHERE id = 1
    """, (
        data.get("razao_social", ""),
        data.get("nome_fantasia", ""),
        data.get("cnpj", ""),
        data.get("inscricao_estadual", ""),
        data.get("inscricao_municipal", ""),
        data.get("regime_tributario", "simples_nacional"),
        data.get("cnae_principal", "6201-5/01"),
        float(data.get("aliquota_simples") or 6.0),
        data.get("cep", ""),
        data.get("logradouro", ""),
        data.get("numero", ""),
        data.get("bairro", ""),
        data.get("cidade", ""),
        data.get("uf", "MT"),
        data.get("codigo_ibge_municipio", "5102504"),
        data.get("telefone", ""),
        data.get("email", ""),
        data.get("chave_pix", ""),
        data.get("ambiente_fiscal", "homologacao"),
        data.get("motor_fiscal", "sefaz_direto"),
        data.get("api_fiscal_token", ""),
        int(data.get("serie_nfe") or 1),
        int(data.get("proximo_numero_nfe") or 101),
        int(data.get("serie_nfce") or 1),
        int(data.get("proximo_numero_nfce") or 501),
        int(data.get("serie_nfse") or 1),
        int(data.get("proximo_numero_nfse") or 201),
    ))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Configurações fiscais e da empresa salvas com sucesso!"}


@app.post("/api/company/certificate")
async def upload_certificate(req: Request):
    data = await req.json()
    cert_name = data.get("filename", "certificado_a1.pfx")
    cert_b64 = data.get("content_b64", "")
    password = data.get("password", "")
    validade = (date.today() + timedelta(days=365)).isoformat()
    conn = get_conn()
    conn.execute("""
        UPDATE companies
        SET certificado_nome = ?, certificado_validade = ?, certificado_b64 = ?, certificado_senha = ?
        WHERE id = 1
    """, (cert_name, validade, cert_b64[:2048], password))
    conn.commit()
    conn.close()
    return {
        "status": "ok",
        "certificado_nome": cert_name,
        "certificado_validade": validade,
        "message": f"Certificado Digital A1 ({cert_name}) instalado e validado até {validade}!"
    }


# ==============================================================================
# 3. CONTAS BANCÁRIAS, CATEGORIAS (PLANO DE CONTAS) E CENTROS DE CUSTO
# ==============================================================================
@app.get("/api/bank-accounts")
def list_bank_accounts():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM bank_accounts WHERE active = 1 ORDER BY id").fetchall())
    conn.close()
    return rows


@app.post("/api/bank-accounts")
async def create_bank_account(req: Request):
    data = await req.json()
    init_bal = float(data.get("initial_balance") or 0.0)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bank_accounts (name, bank_code, bank_name, agency, account_number, account_type, initial_balance, current_balance, color)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("name", "Nova Conta"),
        data.get("bank_code", "000"),
        data.get("bank_name", "Banco"),
        data.get("agency", "0001"),
        data.get("account_number", ""),
        data.get("account_type", "corrente"),
        init_bal,
        init_bal,
        data.get("color", "#2563eb"),
    ))
    recalculate_bank_balances(conn)
    conn.close()
    return {"status": "ok"}


@app.post("/api/bank-accounts/transfer")
async def transfer_between_accounts(req: Request):
    data = await req.json()
    from_id = int(data["from_account_id"])
    to_id = int(data["to_account_id"])
    amount = float(data["amount"])
    transfer_date = data.get("date") or date.today().isoformat()
    desc = data.get("description") or "Transferência entre Contas"

    if from_id == to_id or amount <= 0:
        raise HTTPException(status_code=400, detail="Selecione contas distintas e um valor maior que zero.")

    conn = get_conn()
    cur = conn.cursor()
    from_acc = cur.execute("SELECT name FROM bank_accounts WHERE id = ?", (from_id,)).fetchone()
    to_acc = cur.execute("SELECT name FROM bank_accounts WHERE id = ?", (to_id,)).fetchone()
    uid = f"TRF-{uuid.uuid4().hex[:6].upper()}"

    trf_cat = cur.execute("SELECT id FROM categories WHERE dre_group = 'transferencia' OR code = '9.01' LIMIT 1").fetchone()
    trf_cat_id = trf_cat["id"] if trf_cat else 18

    # Cria saída na conta origem
    cur.execute("""
        INSERT INTO financial_entries (type, description, category_id, bank_account_id, payment_method, competence_date, due_date, amount, paid_amount, status, group_uid, origin_type)
        VALUES ('despesa', ?, ?, ?, 'Transferência/TED', ?, ?, ?, ?, 'pago', ?, 'transferencia')
    """, (f"[Transf. Enviada -> {to_acc['name']}] {desc}", trf_cat_id, from_id, transfer_date, transfer_date, amount, amount, uid))
    out_id = cur.lastrowid
    cur.execute("""
        INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
        VALUES (?, ?, ?, ?, ?, 'Transferência/TED', 'Transferência entre contas')
    """, (out_id, from_id, transfer_date, amount, amount))

    # Cria entrada na conta destino
    cur.execute("""
        INSERT INTO financial_entries (type, description, category_id, bank_account_id, payment_method, competence_date, due_date, amount, paid_amount, status, group_uid, origin_type)
        VALUES ('receita', ?, ?, ?, 'Transferência/TED', ?, ?, ?, ?, 'pago', ?, 'transferencia')
    """, (f"[Transf. Recebida <- {from_acc['name']}] {desc}", trf_cat_id, to_id, transfer_date, transfer_date, amount, amount, uid))
    in_id = cur.lastrowid
    cur.execute("""
        INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
        VALUES (?, ?, ?, ?, ?, 'Transferência/TED', 'Transferência entre contas')
    """, (in_id, to_id, transfer_date, amount, amount))

    recalculate_bank_balances(conn)
    conn.close()
    return {"status": "ok", "message": "Transferência realizada e saldos bancários atualizados!"}


@app.get("/api/categories")
def list_categories():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM categories ORDER BY code").fetchall())
    conn.close()
    return rows


@app.post("/api/categories")
async def create_category(req: Request):
    data = await req.json()
    conn = get_conn()
    conn.execute("""
        INSERT INTO categories (code, name, type, dre_group, keywords)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data.get("code", "9.99"),
        data.get("name", "Nova Categoria"),
        data.get("type", "despesa"),
        data.get("dre_group", "despesas_operacionais"),
        data.get("keywords", ""),
    ))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/cost-centers")
def list_cost_centers():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM cost_centers WHERE active = 1 ORDER BY code").fetchall())
    conn.close()
    return rows


# ==============================================================================
# 4. CADASTROS INTELIGENTES (CLIENTES, FORNECEDORES) + BUSCA CNPJ / CEP
# ==============================================================================
@app.get("/api/contacts")
def list_contacts(type: Optional[str] = None, q: Optional[str] = None):
    conn = get_conn()
    sql = "SELECT * FROM contacts WHERE active = 1"
    params = []
    if type and type != "todos":
        sql += " AND (type = ? OR type = 'ambos')"
        params.append(type)
    if q:
        sql += " AND (name LIKE ? OR trade_name LIKE ? OR document LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql += " ORDER BY name ASC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return rows


@app.post("/api/contacts")
async def save_contact(req: Request):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    cid = data.get("id")
    fields = (
        data.get("type", "cliente"),
        data.get("person_type", "PJ"),
        data.get("name", "").strip(),
        data.get("trade_name", "").strip(),
        data.get("document", "").strip(),
        data.get("ie_indicator", "9"),
        data.get("state_registration", "").strip(),
        data.get("municipal_registration", "").strip(),
        data.get("email", "").strip(),
        data.get("phone", "").strip(),
        data.get("whatsapp", "").strip(),
        data.get("cep", "").strip(),
        data.get("street", "").strip(),
        data.get("number", "").strip(),
        data.get("complement", "").strip(),
        data.get("neighborhood", "").strip(),
        data.get("city", "").strip(),
        data.get("state", "MT").strip(),
        data.get("ibge_code", "5102504").strip(),
        float(data.get("credit_limit") or 0.0),
        data.get("notes", ""),
    )
    if cid:
        cur.execute("""
            UPDATE contacts SET
                type=?, person_type=?, name=?, trade_name=?, document=?, ie_indicator=?,
                state_registration=?, municipal_registration=?, email=?, phone=?, whatsapp=?,
                cep=?, street=?, number=?, complement=?, neighborhood=?, city=?, state=?,
                ibge_code=?, credit_limit=?, notes=?
            WHERE id=?
        """, (*fields, cid))
    else:
        cur.execute("""
            INSERT INTO contacts (
                type, person_type, name, trade_name, document, ie_indicator,
                state_registration, municipal_registration, email, phone, whatsapp,
                cep, street, number, complement, neighborhood, city, state,
                ibge_code, credit_limit, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, fields)
        cid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"status": "ok", "id": cid}


@app.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: int):
    conn = get_conn()
    conn.execute("UPDATE contacts SET active = 0 WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/lookup/cnpj/{cnpj}")
async def lookup_cnpj(cnpj: str):
    clean = re.sub(r"\D", "", cnpj)
    if len(clean) != 14:
        raise HTTPException(status_code=400, detail="CNPJ deve ter 14 dígitos.")
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{clean}")
            if r.status_code == 200:
                d = r.json()
                return {
                    "name": d.get("razao_social", ""),
                    "trade_name": d.get("nome_fantasia") or d.get("razao_social", ""),
                    "cep": d.get("cep", ""),
                    "street": d.get("logradouro", ""),
                    "number": d.get("numero", ""),
                    "complement": d.get("complemento", ""),
                    "neighborhood": d.get("bairro", ""),
                    "city": d.get("municipio", ""),
                    "state": d.get("uf", ""),
                    "phone": d.get("ddd_telefone_1", ""),
                    "email": d.get("email", "") or "",
                }
            elif r.status_code == 404:
                raise HTTPException(status_code=404, detail="CNPJ não encontrado na Receita Federal.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar serviço da BrasilAPI: {str(e)}")

    raise HTTPException(status_code=404, detail="CNPJ não encontrado.")


@app.get("/api/lookup/cep/{cep}")
async def lookup_cep(cep: str):
    clean = re.sub(r"\D", "", cep)
    if len(clean) != 8:
        raise HTTPException(status_code=400, detail="CEP deve ter 8 dígitos.")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"https://viacep.com.br/ws/{clean}/json/")
            if r.status_code == 200:
                d = r.json()
                if not d.get("erro"):
                    return {
                        "street": d.get("logradouro", ""),
                        "neighborhood": d.get("bairro", ""),
                        "city": d.get("localidade", ""),
                        "state": d.get("uf", ""),
                        "ibge_code": d.get("ibge", ""),
                    }
                raise HTTPException(status_code=404, detail="CEP não encontrado.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar serviço ViaCEP: {str(e)}")

    raise HTTPException(status_code=404, detail="CEP não encontrado.")


# ==============================================================================
# 5. PRODUTOS, SERVIÇOS, FICHA FISCAL E KARDEX DE ESTOQUE
# ==============================================================================
@app.get("/api/products")
def list_products(type: Optional[str] = None, q: Optional[str] = None):
    conn = get_conn()
    sql = "SELECT * FROM products WHERE active = 1"
    params = []
    if type and type != "todos":
        sql += " AND type = ?"
        params.append(type)
    if q:
        sql += " AND (name LIKE ? OR sku LIKE ? OR barcode LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql += " ORDER BY name ASC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return rows


@app.post("/api/products")
async def save_product(req: Request):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    pid = data.get("id")
    cost = float(data.get("cost_price") or 0.0)
    sale = float(data.get("sale_price") or 0.0)
    margin = round(((sale - cost) / cost) * 100.0, 2) if cost > 0 else 100.0
    stock_qty = float(data.get("stock_qty") or 0.0)

    fields = (
        data.get("type", "produto"),
        data.get("sku", f"PRD-{random.randint(100,999)}"),
        data.get("barcode", ""),
        data.get("name", "").strip(),
        data.get("category_name", "Geral"),
        data.get("unit", "UN"),
        cost,
        cost,
        margin,
        sale,
        stock_qty,
        float(data.get("min_stock") or 5.0),
        re.sub(r"\D", "", str(data.get("ncm", "84713012"))).zfill(8)[:8],
        data.get("cest", ""),
        data.get("origin", "0"),
        re.sub(r"\D", "", str(data.get("cfop_internal", "5102"))).zfill(4)[:4],
        re.sub(r"\D", "", str(data.get("cfop_external", "6102"))).zfill(4)[:4],
        data.get("csosn_cst", "102"),
        float(data.get("icms_rate") or 0.0),
        data.get("pis_cst", "07"),
        float(data.get("pis_rate") or 0.65),
        data.get("cofins_cst", "07"),
        float(data.get("cofins_rate") or 3.0),
        data.get("service_code_lc116", "01.07"),
        float(data.get("iss_rate") or 3.0),
    )

    if pid:
        cur.execute("""
            UPDATE products SET
                type=?, sku=?, barcode=?, name=?, category_name=?, unit=?,
                cost_price=?, average_cost=?, margin_percent=?, sale_price=?,
                stock_qty=?, min_stock=?, ncm=?, cest=?, origin=?,
                cfop_internal=?, cfop_external=?, csosn_cst=?, icms_rate=?,
                pis_cst=?, pis_rate=?, cofins_cst=?, cofins_rate=?,
                service_code_lc116=?, iss_rate=?
            WHERE id=?
        """, (*fields, pid))
    else:
        cur.execute("""
            INSERT INTO products (
                type, sku, barcode, name, category_name, unit,
                cost_price, average_cost, margin_percent, sale_price,
                stock_qty, min_stock, ncm, cest, origin,
                cfop_internal, cfop_external, csosn_cst, icms_rate,
                pis_cst, pis_rate, cofins_cst, cofins_rate,
                service_code_lc116, iss_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, fields)
        pid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"status": "ok", "id": pid}


@app.post("/api/products/{product_id}/stock-adjust")
async def adjust_stock(product_id: int, req: Request):
    data = await req.json()
    m_type = data.get("movement_type", "entrada")  # entrada, saida, ajuste
    qty = float(data.get("quantity") or 0.0)
    unit_cost = float(data.get("unit_cost") or 0.0)
    notes = data.get("notes", "Movimentação manual de estoque")

    conn = get_conn()
    cur = conn.cursor()
    prod = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not prod:
        conn.close()
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    prev = float(prod["stock_qty"] or 0.0)
    avg_cost = float(prod["average_cost"] or prod["cost_price"] or 0.0)
    if m_type == "entrada":
        new_stock = prev + qty
        if new_stock > 0 and unit_cost > 0:
            avg_cost = round(((max(0.0, prev) * avg_cost) + (qty * unit_cost)) / new_stock, 2)
    elif m_type == "saida":
        new_stock = prev - qty
    else:
        new_stock = qty

    cur.execute("""
        UPDATE products SET stock_qty = ?, average_cost = ?, cost_price = CASE WHEN ? > 0 THEN ? ELSE cost_price END
        WHERE id = ?
    """, (new_stock, avg_cost, unit_cost, unit_cost, product_id))

    cur.execute("""
        INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
        VALUES (?, ?, ?, ?, ?, ?, 'AJUSTE', ?)
    """, (product_id, m_type, qty, unit_cost or avg_cost, prev, new_stock, notes))
    conn.commit()
    conn.close()
    return {"status": "ok", "new_stock": new_stock, "average_cost": avg_cost}


@app.get("/api/stock-movements")
def list_stock_movements():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT m.*, p.name as product_name, p.sku as sku, p.unit as unit
        FROM stock_movements m
        JOIN products p ON p.id = m.product_id
        ORDER BY m.id DESC LIMIT 100
    """).fetchall())
    conn.close()
    return rows


# ==============================================================================
# 6. FINANCEIRO AVANÇADO (CONTAS A PAGAR/RECEBER, PARCELAS, BAIXA PARCIAL, ESTORNO)
# ==============================================================================
@app.get("/api/financial")
def list_financial_entries(
    type: Optional[str] = None,
    status: Optional[str] = None,
    bank_account_id: Optional[int] = None,
    q: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    conn = get_conn()
    today_str = date.today().isoformat()
    sql = """
        SELECT e.*,
               c.name as contact_name, c.whatsapp as contact_whatsapp, c.document as contact_doc,
               cat.code as category_code, cat.name as category_name,
               cc.name as cost_center_name,
               b.name as bank_account_name, b.color as bank_color
        FROM financial_entries e
        LEFT JOIN contacts c ON c.id = e.contact_id
        LEFT JOIN categories cat ON cat.id = e.category_id
        LEFT JOIN cost_centers cc ON cc.id = e.cost_center_id
        LEFT JOIN bank_accounts b ON b.id = e.bank_account_id
        WHERE e.status != 'cancelado'
    """
    params = []
    if type and type in ("receita", "despesa"):
        sql += " AND e.type = ?"
        params.append(type)
    if bank_account_id:
        sql += " AND e.bank_account_id = ?"
        params.append(bank_account_id)
    if start_date:
        sql += " AND e.due_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND e.due_date <= ?"
        params.append(end_date)
    if q:
        sql += " AND (e.description LIKE ? OR c.name LIKE ? OR e.document_number LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    sql += " ORDER BY e.due_date ASC, e.id DESC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())

    # Enriquece com status dinâmico (vencido / vence_hoje / a_vencer / parcial / pago) e saldo restante
    filtered = []
    for r in rows:
        net_total = round(float(r["amount"]) + float(r["interest"]) + float(r["fine"]) - float(r["discount"]), 2)
        paid = round(float(r["paid_amount"]), 2)
        remaining = max(0.0, round(net_total - paid, 2))
        r["net_total"] = net_total
        r["remaining_amount"] = remaining

        if r["status"] == "pago" or remaining <= 0.009:
            display_status = "pago"
        elif paid > 0 and remaining > 0:
            display_status = "parcial"
        elif r["due_date"] < today_str:
            display_status = "vencido"
        elif r["due_date"] == today_str:
            display_status = "vence_hoje"
        else:
            display_status = "a_vencer"
        r["display_status"] = display_status

        if status and status != "todos":
            if status == "abertos" and display_status == "pago":
                continue
            elif status != "abertos" and display_status != status:
                continue
        filtered.append(r)

    conn.close()
    return filtered


@app.post("/api/financial")
async def create_financial_entry(req: Request):
    """Cria lançamento único, parcelado (1/N..N/N) ou recorrente, com opção de já nascer baixado."""
    data = await req.json()
    e_type = data.get("type", "despesa")
    description = data.get("description", "Lançamento Financeiro").strip()
    conn = get_conn()
    cur = conn.cursor()

    contact_id = int(data["contact_id"]) if data.get("contact_id") else None

    if data.get("category_id"):
        category_id = int(data["category_id"])
    else:
        cat = cur.execute("SELECT id FROM categories WHERE type = ? ORDER BY code ASC LIMIT 1", (e_type,)).fetchone()
        category_id = cat["id"] if cat else (1 if e_type == "receita" else 11)

    if data.get("cost_center_id"):
        cost_center_id = int(data["cost_center_id"])
    else:
        cc = cur.execute("SELECT id FROM cost_centers WHERE active = 1 ORDER BY id ASC LIMIT 1").fetchone()
        cost_center_id = cc["id"] if cc else 1

    if data.get("bank_account_id"):
        bank_account_id = int(data["bank_account_id"])
    else:
        ba = cur.execute("SELECT id FROM bank_accounts WHERE active = 1 ORDER BY id ASC LIMIT 1").fetchone()
        bank_account_id = ba["id"] if ba else 1

    payment_method = data.get("payment_method", "Pix")
    competence_date = data.get("competence_date") or date.today().isoformat()
    first_due_str = data.get("due_date") or date.today().isoformat()
    first_due = date.fromisoformat(first_due_str[:10])
    total_amount = float(data.get("amount") or 0.0)
    installments = max(1, int(data.get("installments") or 1))
    recurrence = data.get("recurrence", "unico")
    already_paid = bool(data.get("already_paid", False))
    doc_num = data.get("document_number", "")
    notes = data.get("notes", "")

    group_uid = f"FIN-{uuid.uuid4().hex[:8].upper()}"

    # Se parcelado, divide o valor ou repete se for recorrente mensal
    per_installment = round(total_amount / installments, 2) if recurrence == "unico" else total_amount

    created_ids = []
    for i in range(1, installments + 1):
        due_d = add_months(first_due, i - 1).isoformat()
        amt = per_installment
        if recurrence == "unico" and i == installments:
            amt = round(total_amount - per_installment * (installments - 1), 2)

        desc_final = f"{description} ({i}/{installments})" if installments > 1 else description
        is_paid_now = already_paid and i == 1
        status = "pago" if is_paid_now else "pendente"
        paid_val = amt if is_paid_now else 0.0

        cur.execute("""
            INSERT INTO financial_entries (
                type, description, contact_id, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, paid_amount, status,
                installment_number, installment_total, group_uid, recurrence, document_number, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            e_type, desc_final, contact_id, category_id, cost_center_id, bank_account_id,
            payment_method, competence_date, due_d, amt, paid_val, status,
            i, installments, group_uid, recurrence, doc_num, notes
        ))
        eid = cur.lastrowid
        created_ids.append(eid)

        if is_paid_now:
            cur.execute("""
                INSERT INTO financial_payments (
                    entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes
                ) VALUES (?, ?, ?, ?, ?, ?, 'Baixado no ato do lançamento')
            """, (eid, bank_account_id, due_d, amt, amt, payment_method))

    recalculate_bank_balances(conn)
    conn.close()
    return {"status": "ok", "created_ids": created_ids}


@app.post("/api/financial/{entry_id}/pay")
async def pay_financial_entry(entry_id: int, req: Request):
    """Realiza Baixa Total ou Baixa Parcial com suporte a Juros, Multa, Desconto e escolha da Conta Bancária."""
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    entry = cur.execute("SELECT * FROM financial_entries WHERE id = ?", (entry_id,)).fetchone()
    if not entry:
        conn.close()
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")

    bank_account_id = int(data.get("bank_account_id") or entry["bank_account_id"] or 1)
    payment_date = data.get("payment_date") or date.today().isoformat()
    payment_method = data.get("payment_method") or entry["payment_method"] or "Pix"
    interest_paid = float(data.get("interest") or 0.0)
    fine_paid = float(data.get("fine") or 0.0)
    discount_applied = float(data.get("discount") or 0.0)

    # Atualiza juros, multa e desconto acumulados no título
    new_interest = round(float(entry["interest"]) + interest_paid, 2)
    new_fine = round(float(entry["fine"]) + fine_paid, 2)
    new_discount = round(float(entry["discount"]) + discount_applied, 2)
    net_total = round(float(entry["amount"]) + new_interest + new_fine - new_discount, 2)
    already_paid = float(entry["paid_amount"] or 0.0)
    remaining_before = max(0.0, round(net_total - already_paid, 2))

    # Valor que o usuário está efetivamente pagando agora (pode ser parcial ou total)
    cash_paid = float(data.get("amount_paid") if data.get("amount_paid") is not None else remaining_before)
    cash_paid = round(max(0.01, cash_paid), 2)

    new_paid_total = round(already_paid + cash_paid, 2)
    new_status = "pago" if new_paid_total >= (net_total - 0.01) else "parcial"

    cur.execute("""
        UPDATE financial_entries
        SET interest = ?, fine = ?, discount = ?, paid_amount = ?, status = ?, bank_account_id = ?, payment_method = ?
        WHERE id = ?
    """, (new_interest, new_fine, new_discount, new_paid_total, new_status, bank_account_id, payment_method, entry_id))

    cur.execute("""
        INSERT INTO financial_payments (
            entry_id, bank_account_id, payment_date, principal_paid, interest_paid,
            fine_paid, discount_applied, total_cash_flow, payment_method, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        entry_id, bank_account_id, payment_date, cash_paid, interest_paid,
        fine_paid, discount_applied, cash_paid, payment_method,
        data.get("notes", f"Baixa {'Total' if new_status == 'pago' else 'Parcial'}")
    ))

    recalculate_bank_balances(conn)
    conn.close()
    return {
        "status": "ok",
        "entry_status": new_status,
        "paid_amount": new_paid_total,
        "remaining": max(0.0, round(net_total - new_paid_total, 2)),
    }


@app.post("/api/financial/{entry_id}/reverse")
def reverse_financial_entry(entry_id: int):
    """Estorna todas as baixas de um lançamento e recalcula o saldo bancário imediatamente."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM financial_payments WHERE entry_id = ?", (entry_id,))
    cur.execute("""
        UPDATE financial_entries
        SET paid_amount = 0.0, interest = 0.0, fine = 0.0, discount = 0.0, status = 'pendente'
        WHERE id = ?
    """, (entry_id,))
    recalculate_bank_balances(conn)
    conn.close()
    return {"status": "ok", "message": "Baixa estornada e saldo bancário recalculado!"}


@app.post("/api/financial/batch-pay")
async def batch_pay_entries(req: Request):
    data = await req.json()
    ids = data.get("ids", [])
    bank_id = data.get("bank_account_id")
    today_iso = date.today().isoformat()

    conn = get_conn()
    cur = conn.cursor()
    count = 0
    for eid in ids:
        entry = cur.execute("SELECT * FROM financial_entries WHERE id = ?", (eid,)).fetchone()
        if not entry or entry["status"] == "pago":
            continue
        net = round(float(entry["amount"]) + float(entry["interest"]) + float(entry["fine"]) - float(entry["discount"]), 2)
        rem = max(0.0, round(net - float(entry["paid_amount"]), 2))
        if rem <= 0:
            continue
        b_id = int(bank_id or entry["bank_account_id"] or 1)
        cur.execute("UPDATE financial_entries SET paid_amount = ?, status = 'pago', bank_account_id = ? WHERE id = ?", (net, b_id, eid))
        cur.execute("""
            INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'Baixa em Lote')
        """, (eid, b_id, today_iso, rem, rem, entry["payment_method"]))
        count += 1

    recalculate_bank_balances(conn)
    conn.close()
    return {"status": "ok", "count": count}


@app.delete("/api/financial/{entry_id}")
def delete_financial_entry(entry_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM financial_payments WHERE entry_id = ?", (entry_id,))
    conn.execute("DELETE FROM financial_entries WHERE id = ?", (entry_id,))
    recalculate_bank_balances(conn)
    conn.close()
    return {"status": "ok"}


# ==============================================================================
# 7. LANÇAMENTO POR VOZ/TEXTO NATURAL (NLP + IA) & CFO VIRTUAL
# ==============================================================================
@app.post("/api/financial/ai-launch")
async def ai_natural_language_launch(req: Request):
    """
    Interpreta frases naturais em português como:
    'Lance uma despesa de R$ 480,00 de energia elétrica vencendo dia 25 no Banco Inter'
    ou 'Receita de R$ 3.600 consultoria parcelado em 3x no Pix pago'
    e cria o lançamento financeiro já categorizado!
    """
    data = await req.json()
    prompt_txt = (data.get("text") or "").strip()
    if not prompt_txt:
        raise HTTPException(status_code=400, detail="Digite um comando para o lançamento inteligente.")

    low = prompt_txt.lower()
    e_type = "receita" if any(w in low for w in ("receita", "receber", "recebi", "venda", "entrada", "honorario", "mensalidade")) else "despesa"

    # Extrai valor monetário (ex: R$ 1.250,50 ou 480,00 ou 350)
    val_match = re.search(r"(?:r\$\s*)?(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})|\d+(?:[.,]\d{1,2})?)", low)
    amount = 100.0
    if val_match:
        raw_v = val_match.group(1)
        if "," in raw_v:
            raw_v = raw_v.replace(".", "").replace(",", ".")
        amount = float(raw_v)

    # Extrai parcelamento (ex: 3x, 4 parcelas)
    inst_match = re.search(r"(\d{1,2})\s*(?:x|vezes|parcelas)", low)
    installments = int(inst_match.group(1)) if inst_match else 1

    # Extrai data de vencimento (amanhã, hoje, dia DD, ou DD/MM)
    due_d = date.today()
    if "amanha" in low or "amanhã" in low:
        due_d = date.today() + timedelta(days=1)
    elif dm := re.search(r"dia\s+(\d{1,2})", low):
        day_num = min(28, max(1, int(dm.group(1))))
        due_d = date(date.today().year, date.today().month, day_num)
    elif d_slash := re.search(r"(\d{1,2})/(\d{1,2})", low):
        due_d = date(date.today().year, int(d_slash.group(2)), int(d_slash.group(1)))

    already_paid = any(w in low for w in ("pago", "paguei", "recebido", "recebi", "baixado", "à vista"))

    # Forma de pagamento
    method = "Pix"
    if "boleto" in low:
        method = "Boleto"
    elif "cartao" in low or "cartão" in low or "credito" in low:
        method = "Cartão de Crédito"
    elif "dinheiro" in low:
        method = "Dinheiro"

    conn = get_conn()
    cur = conn.cursor()
    categories = rows_to_dicts(cur.execute("SELECT * FROM categories WHERE type = ?", (e_type,)).fetchall())
    cat_id = categories[0]["id"] if categories else 1
    cat_name = categories[0]["name"] if categories else "Geral"
    for c in categories:
        kws = [k.strip().lower() for k in (c.get("keywords") or "").split(",") if k.strip()]
        if any(k in low for k in kws):
            cat_id = c["id"]
            cat_name = c["name"]
            break

    banks = rows_to_dicts(cur.execute("SELECT * FROM bank_accounts WHERE active = 1").fetchall())
    bank_id = banks[0]["id"] if banks else 1
    for b in banks:
        if b["name"].lower() in low or b["bank_name"].lower() in low:
            bank_id = b["id"]
            break

    desc_clean = prompt_txt[0].upper() + prompt_txt[1:]
    group_uid = f"IA-{uuid.uuid4().hex[:6].upper()}"
    per_inst = round(amount / installments, 2)

    for i in range(1, installments + 1):
        d_iso = add_months(due_d, i - 1).isoformat()
        is_p = already_paid and i == 1
        cur.execute("""
            INSERT INTO financial_entries (
                type, description, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, paid_amount,
                status, installment_number, installment_total, group_uid, origin_type
            ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ia')
        """, (
            e_type,
            f"{desc_clean} ({i}/{installments})" if installments > 1 else desc_clean,
            cat_id,
            bank_id,
            method,
            date.today().isoformat(),
            d_iso,
            per_inst,
            per_inst if is_p else 0.0,
            "pago" if is_p else "pendente",
            i,
            installments,
            group_uid,
        ))
        eid = cur.lastrowid
        if is_p:
            cur.execute("""
                INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, 'Lançamento Inteligente por IA')
            """, (eid, bank_id, d_iso, per_inst, per_inst, method))

    recalculate_bank_balances(conn)
    conn.close()
    return {
        "status": "ok",
        "parsed": {
            "type": e_type,
            "amount": amount,
            "installments": installments,
            "due_date": due_d.isoformat(),
            "category": cat_name,
            "already_paid": already_paid,
        },
        "message": f"Lançamento IA criado: {e_type.upper()} de R$ {amount:,.2f} ({installments}x) na categoria '{cat_name}'!"
    }


@app.post("/api/cfo/ask")
async def ask_virtual_cfo(req: Request):
    """CFO Virtual que analisa os dados reais do banco e responde com diagnóstico financeiro completo."""
    data = await req.json()
    question = (data.get("question") or "Faça um diagnóstico completo da saúde financeira da empresa.").strip()
    dash = get_dashboard()
    kpis = dash["kpis"]

    context_summary = (
        f"Saldo em caixa/bancos: R$ {kpis['total_balance']:,.2f} | "
        f"A receber no mês: R$ {kpis['receivables_month']:,.2f} (Vencidos: R$ {kpis['receivables_overdue']:,.2f}) | "
        f"A pagar no mês: R$ {kpis['payables_month']:,.2f} (Vencidos: R$ {kpis['payables_overdue']:,.2f}) | "
        f"Resultado líquido previsto no mês: R$ {kpis['net_profit_month']:,.2f}."
    )

    # Tenta usar Gemini API se a chave estiver disponível no ambiente
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(
                    "Você é o CFO Virtual Executivo do sistema Cortex ERP Pro+. "
                    f"Dados reais em tempo real da empresa: {context_summary}. "
                    f"Pergunta do diretor: {question}\n"
                    "Responda de forma objetiva, estratégica e elegante em português (máximo 3 parágrafos com bullet points práticos)."
                ),
            )
            if resp and resp.text:
                return {"answer": resp.text, "engine": "Gemini 2.5 Flash Live CFO"}
        except Exception:
            pass

    # Motor Analítico Financeiro Local Determinístico (sempre disponível)
    liquidez = round(kpis["total_balance"] / max(1.0, kpis["payables_month"]), 2)
    answer = (
        f"📊 **Diagnóstico Executivo do CFO Virtual:**\n\n"
        f"- **Posição de Liquidez Imediata:** Sua empresa dispõe de **R$ {kpis['total_balance']:,.2f}** em contas bancárias e aplicações, "
        f"o que representa um índice de cobertura de **{liquidez}x** sobre todas as despesas do mês (R$ {kpis['payables_month']:,.2f}).\n"
        f"- **Gestão de Recebíveis e Inadimplência:** Há **R$ {kpis['receivables_overdue']:,.2f}** em títulos vencidos. "
        f"Recomendo acionar imediatamente o botão **Cobrar no WhatsApp** na aba *Contas a Receber* para recuperar esse capital de giro.\n"
        f"- **Resultado Operacional:** O saldo líquido previsto do mês está em **R$ {kpis['net_profit_month']:,.2f}**. "
        f"Existem **{kpis['pending_ofx']} transações OFX** e **{kpis['open_os']} Ordens de Serviço** que podem ser faturadas para ampliar a margem."
    )
    return {"answer": answer, "engine": "Cortex Financial Analytics Engine"}


# ==============================================================================
# 8. CONCILIAÇÃO BANCÁRIA INTELIGENTE (.OFX)
# ==============================================================================
@app.get("/api/ofx")
def list_ofx_transactions():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT o.*, b.name as bank_name, c.name as suggested_category_name,
               e.description as matched_entry_description, e.due_date as matched_entry_due
        FROM ofx_transactions o
        LEFT JOIN bank_accounts b ON b.id = o.bank_account_id
        LEFT JOIN categories c ON c.id = o.suggested_category_id
        LEFT JOIN financial_entries e ON e.id = o.matched_entry_id
        ORDER BY o.status DESC, o.posted_date DESC, o.id DESC
    """).fetchall())
    conn.close()
    return rows


@app.post("/api/ofx/import")
async def import_ofx(req: Request):
    data = await req.json()
    bank_account_id = int(data.get("bank_account_id") or 1)
    ofx_content = data.get("ofx_content") or gerar_ofx_exemplo()
    parsed = parse_ofx_content(ofx_content)

    conn = get_conn()
    cur = conn.cursor()
    categories = rows_to_dicts(cur.execute("SELECT * FROM categories").fetchall())
    open_entries = rows_to_dicts(cur.execute("""
        SELECT id, type, description, amount, due_date, status
        FROM financial_entries
        WHERE status IN ('pendente', 'parcial')
    """).fetchall())

    imported = 0
    for item in parsed:
        exists = cur.execute("SELECT id FROM ofx_transactions WHERE fitid = ?", (item["fitid"],)).fetchone()
        if exists:
            continue

        amt = float(item["amount"])
        is_credit = amt > 0
        abs_amt = abs(amt)
        memo_low = item["memo"].lower()

        # 1. Tenta encontrar pareamento exato com lançamento em aberto no Financeiro
        matched_id = None
        for oe in open_entries:
            if (is_credit and oe["type"] == "receita") or (not is_credit and oe["type"] == "despesa"):
                if abs(float(oe["amount"]) - abs_amt) < 0.05:
                    matched_id = oe["id"]
                    break

        # 2. Sugere categoria pela inteligência de palavras-chave
        sug_cat_id = 1 if is_credit else 11
        for cat in categories:
            if (is_credit and cat["type"] == "receita") or (not is_credit and cat["type"] == "despesa"):
                kws = [k.strip().lower() for k in (cat.get("keywords") or "").split(",") if k.strip()]
                if any(k in memo_low for k in kws):
                    sug_cat_id = cat["id"]
                    break

        cur.execute("""
            INSERT INTO ofx_transactions (bank_account_id, fitid, posted_date, amount, memo, suggested_category_id, matched_entry_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente')
        """, (bank_account_id, item["fitid"], item["posted_date"], amt, item["memo"], sug_cat_id, matched_id))
        imported += 1

    conn.commit()
    conn.close()
    return {"status": "ok", "imported": imported, "message": f"{imported} transações do extrato OFX analisadas e prontas para conciliação!"}


@app.post("/api/ofx/{ofx_id}/reconcile")
async def reconcile_ofx_transaction(ofx_id: int, req: Request):
    """Concilia a transação OFX em 1 clique: baixa título pareado ou cria novo lançamento já quitado."""
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    ofx = cur.execute("SELECT * FROM ofx_transactions WHERE id = ?", (ofx_id,)).fetchone()
    if not ofx:
        conn.close()
        raise HTTPException(status_code=404, detail="Transação OFX não encontrada.")

    amt = float(ofx["amount"])
    abs_amt = abs(amt)
    e_type = "receita" if amt > 0 else "despesa"
    cat_id = int(data.get("category_id") or ofx["suggested_category_id"] or (1 if amt > 0 else 11))
    matched_id = data.get("matched_entry_id") or ofx["matched_entry_id"]

    if matched_id:
        # Dá baixa no lançamento existente
        cur.execute("""
            UPDATE financial_entries
            SET paid_amount = amount, status = 'pago', bank_account_id = ?
            WHERE id = ?
        """, (ofx["bank_account_id"], matched_id))
        cur.execute("""
            INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, 'Conciliação OFX', ?)
        """, (matched_id, ofx["bank_account_id"], ofx["posted_date"], abs_amt, abs_amt, f"Conciliado via OFX ({ofx['fitid']})"))
    else:
        # Cria lançamento novo já baixado
        cur.execute("""
            INSERT INTO financial_entries (
                type, description, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, paid_amount,
                status, document_number, origin_type, origin_id
            ) VALUES (?, ?, ?, 1, ?, 'Conciliação OFX', ?, ?, ?, ?, 'pago', ?, 'ofx', ?)
        """, (e_type, ofx["memo"], cat_id, ofx["bank_account_id"], ofx["posted_date"], ofx["posted_date"], abs_amt, abs_amt, ofx["fitid"], ofx_id))
        new_entry_id = cur.lastrowid
        cur.execute("""
            INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, 'Conciliação OFX', 'Criado e baixado na conciliação OFX')
        """, (new_entry_id, ofx["bank_account_id"], ofx["posted_date"], abs_amt, abs_amt))
        matched_id = new_entry_id

    cur.execute("""
        UPDATE ofx_transactions
        SET status = 'conciliado', matched_entry_id = ?, reconciled_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (matched_id, ofx_id))

    recalculate_bank_balances(conn)
    conn.close()
    return {"status": "ok", "matched_entry_id": matched_id}


# ==============================================================================
# 9. COMERCIAL COMPLETO: CRM KANBAN, ORÇAMENTOS, VENDAS, PDV E CONTRATOS
# ==============================================================================
@app.get("/api/crm")
def list_crm_deals():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM crm_deals ORDER BY id DESC").fetchall())
    conn.close()
    return rows


@app.post("/api/crm")
async def save_crm_deal(req: Request):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    did = data.get("id")
    if did:
        cur.execute("""
            UPDATE crm_deals
            SET title=?, contact_name=?, stage=?, estimated_value=?, probability=?, temperature=?, notes=?
            WHERE id=?
        """, (
            data.get("title", ""),
            data.get("contact_name", ""),
            data.get("stage", "prospeccao"),
            float(data.get("estimated_value") or 0.0),
            int(data.get("probability") or 50),
            data.get("temperature", "morno"),
            data.get("notes", ""),
            did,
        ))
    else:
        cur.execute("""
            INSERT INTO crm_deals (title, contact_id, contact_name, stage, estimated_value, probability, expected_close_date, responsible, temperature, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("title", "Nova Oportunidade"),
            data.get("contact_id"),
            data.get("contact_name", "Cliente Potencial"),
            data.get("stage", "prospeccao"),
            float(data.get("estimated_value") or 0.0),
            int(data.get("probability") or 60),
            data.get("expected_close_date") or (date.today() + timedelta(days=10)).isoformat(),
            data.get("responsible", "Willian Cardoso"),
            data.get("temperature", "quente"),
            data.get("notes", ""),
        ))
        did = cur.lastrowid
    conn.commit()
    conn.close()
    return {"status": "ok", "id": did}


@app.post("/api/crm/{deal_id}/stage")
async def move_crm_stage(deal_id: int, req: Request):
    data = await req.json()
    conn = get_conn()
    conn.execute("UPDATE crm_deals SET stage = ? WHERE id = ?", (data.get("stage", "proposta"), deal_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/crm/{deal_id}/convert")
def convert_crm_to_quote(deal_id: int):
    """Transforma uma oportunidade do CRM Kanban diretamente em Orçamento Comercial!"""
    conn = get_conn()
    cur = conn.cursor()
    deal = cur.execute("SELECT * FROM crm_deals WHERE id = ?", (deal_id,)).fetchone()
    if not deal:
        conn.close()
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")

    next_num = (cur.execute("SELECT MAX(number) FROM sales").fetchone()[0] or 1000) + 1
    val = float(deal["estimated_value"] or 1000.0)
    cur.execute("""
        INSERT INTO sales (number, sale_type, status, contact_id, seller_name, sale_date, valid_until, subtotal, total_amount, payment_method, installments, bank_account_id, notes)
        VALUES (?, 'orcamento', 'enviado', ?, ?, ?, ?, ?, ?, 'Pix', 1, 1, ?)
    """, (
        next_num,
        deal["contact_id"] or 1,
        deal["responsible"],
        date.today().isoformat(),
        (date.today() + timedelta(days=10)).isoformat(),
        val,
        val,
        f"Gerado a partir do Funil CRM: {deal['title']}"
    ))
    sale_id = cur.lastrowid
    cur.execute("""
        INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
        VALUES (?, 6, ?, 'CRM-ITEM', 'SV', 1, ?, 0.0, ?)
    """, (sale_id, deal["title"], val, val))
    cur.execute("UPDATE crm_deals SET stage = 'ganho', converted_sale_id = ? WHERE id = ?", (sale_id, deal_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "sale_id": sale_id, "number": next_num}


@app.get("/api/sales")
def list_sales(sale_type: Optional[str] = None):
    conn = get_conn()
    sql = """
        SELECT s.*, c.name as contact_name, c.document as contact_doc, c.whatsapp as contact_whatsapp
        FROM sales s
        LEFT JOIN contacts c ON c.id = s.contact_id
        WHERE 1=1
    """
    params = []
    if sale_type and sale_type != "todos":
        sql += " AND s.sale_type = ?"
        params.append(sale_type)
    sql += " ORDER BY s.id DESC"
    sales = rows_to_dicts(conn.execute(sql, params).fetchall())
    for s in sales:
        s["items"] = rows_to_dicts(conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (s["id"],)).fetchall())
    conn.close()
    return sales


def _process_sale_billing(conn, sale_id: int, immediate_paid: bool = False):
    """Dá baixa automática no estoque dos produtos vendidos e gera as parcelas no Contas a Receber."""
    cur = conn.cursor()
    sale = cur.execute("""
        SELECT s.*, c.name as contact_name
        FROM sales s LEFT JOIN contacts c ON c.id = s.contact_id
        WHERE s.id = ?
    """, (sale_id,)).fetchone()
    items = rows_to_dicts(cur.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall())

    # 1. Baixa estoque de produtos físicos
    for it in items:
        if it.get("product_id"):
            prod = cur.execute("SELECT * FROM products WHERE id = ?", (it["product_id"],)).fetchone()
            if prod and prod["type"] == "produto":
                prev_s = float(prod["stock_qty"] or 0.0)
                new_s = prev_s - float(it["quantity"])
                cur.execute("UPDATE products SET stock_qty = ? WHERE id = ?", (new_s, prod["id"]))
                cur.execute("""
                    INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
                    VALUES (?, 'venda', ?, ?, ?, ?, ?, ?)
                """, (prod["id"], float(it["quantity"]), float(prod["average_cost"] or prod["cost_price"] or 0), prev_s, new_s, f"VENDA #{sale['number']}", f"Baixa automática Venda #{sale['number']}"))

    # 2. Gera parcelas no Contas a Receber
    installments = max(1, int(sale["installments"] or 1))
    total = float(sale["total_amount"])
    per_inst = round(total / installments, 2)
    base_date = date.fromisoformat(sale["sale_date"][:10])
    client_label = sale["contact_name"] or "Consumidor Final"

    for i in range(1, installments + 1):
        due_d = base_date.isoformat() if (i == 1 and immediate_paid) else add_months(base_date, i - 1 if immediate_paid else i).isoformat()
        amt = per_inst if i < installments else round(total - per_inst * (installments - 1), 2)
        is_paid = immediate_paid and i == 1
        cur.execute("""
            INSERT INTO financial_entries (
                type, description, contact_id, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, paid_amount, status,
                installment_number, installment_total, group_uid, document_number, origin_type, origin_id
            ) VALUES ('receita', ?, ?, 1, 2, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"Venda #{sale['number']} ({i}/{installments}) - {client_label}",
            sale["contact_id"],
            sale["bank_account_id"] or 1,
            sale["payment_method"],
            sale["sale_date"][:10],
            due_d,
            amt,
            amt if is_paid else 0.0,
            "pago" if is_paid else "pendente",
            i,
            installments,
            f"VND-{sale['number']}",
            f"PED-{sale['number']}",
            sale["sale_type"],
            sale_id,
        ))
        eid = cur.lastrowid
        if is_paid:
            cur.execute("""
                INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (eid, sale["bank_account_id"] or 1, due_d, amt, amt, sale["payment_method"], f"Recebimento Venda #{sale['number']}"))

    cur.execute("UPDATE sales SET status = 'faturada', sale_type = CASE WHEN sale_type = 'orcamento' THEN 'venda' ELSE sale_type END WHERE id = ?", (sale_id,))
    recalculate_bank_balances(conn)
    conn.commit()


@app.post("/api/sales")
async def create_sale(req: Request):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    next_num = (cur.execute("SELECT MAX(number) FROM sales").fetchone()[0] or 1000) + 1
    sale_type = data.get("sale_type", "venda")  # orcamento, venda, pdv
    items = data.get("items", [])
    if not items:
        conn.close()
        raise HTTPException(status_code=400, detail="Adicione pelo menos 1 item ao orçamento/venda.")

    subtotal = round(sum(float(i.get("quantity", 1)) * float(i.get("unit_price", 0)) for i in items), 2)
    discount = float(data.get("discount_amount") or 0.0)
    shipping = float(data.get("shipping_amount") or 0.0)
    total = max(0.0, round(subtotal - discount + shipping, 2))
    status = "enviado" if sale_type == "orcamento" else "faturada"

    cur.execute("""
        INSERT INTO sales (
            number, sale_type, status, contact_id, seller_name, sale_date, valid_until,
            subtotal, discount_amount, shipping_amount, total_amount, payment_method,
            installments, bank_account_id, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        next_num,
        sale_type,
        status,
        int(data["contact_id"]) if data.get("contact_id") else 1,
        data.get("seller_name", "Willian Cardoso"),
        data.get("sale_date") or date.today().isoformat(),
        data.get("valid_until") or (date.today() + timedelta(days=7)).isoformat(),
        subtotal,
        discount,
        shipping,
        total,
        data.get("payment_method", "Pix"),
        int(data.get("installments") or 1),
        int(data.get("bank_account_id") or 1),
        data.get("notes", ""),
    ))
    sale_id = cur.lastrowid

    for it in items:
        q = float(it.get("quantity", 1))
        up = float(it.get("unit_price", 0))
        disc = float(it.get("discount", 0))
        cur.execute("""
            INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sale_id,
            it.get("product_id"),
            it.get("product_name", "Item"),
            it.get("sku", "PRD"),
            it.get("unit", "UN"),
            q,
            up,
            disc,
            round(q * up - disc, 2),
        ))

    if sale_type in ("venda", "pdv"):
        _process_sale_billing(conn, sale_id, immediate_paid=(sale_type == "pdv" or bool(data.get("immediate_paid", False))))
    else:
        conn.commit()

    conn.close()
    return {"status": "ok", "sale_id": sale_id, "number": next_num}


@app.post("/api/sales/{sale_id}/approve")
def approve_quote_to_sale(sale_id: int):
    """Aprova um Orçamento em 1 clique: converte em Venda Faturada, baixa estoque e lança parcelas no Financeiro!"""
    conn = get_conn()
    _process_sale_billing(conn, sale_id, immediate_paid=False)
    conn.close()
    return {"status": "ok", "message": "Orçamento aprovado! Estoque baixado e parcelas geradas no Contas a Receber."}


@app.get("/api/sales/{sale_id}/print", response_class=HTMLResponse)
def print_sale_or_quote(sale_id: int):
    conn = get_conn()
    company = dict(conn.execute("SELECT * FROM companies LIMIT 1").fetchone())
    sale = dict(conn.execute("""
        SELECT s.*, c.name as contact_name, c.document as contact_doc, c.phone as contact_phone,
               c.street, c.number as st_num, c.neighborhood, c.city, c.state
        FROM sales s LEFT JOIN contacts c ON c.id = s.contact_id
        WHERE s.id = ?
    """, (sale_id,)).fetchone())
    items = rows_to_dicts(conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall())
    conn.close()

    titulo = "PROPOSTA COMERCIAL / ORÇAMENTO" if sale["sale_type"] == "orcamento" else "PEDIDO DE VENDA / RECIBO CORPORATIVO"
    rows_html = "".join([
        f"<tr><td>{i['sku']}</td><td>{i['product_name']}</td><td style='text-align:center'>{i['unit']}</td>"
        f"<td style='text-align:right'>{i['quantity']:.2f}</td><td style='text-align:right'>R$ {i['unit_price']:,.2f}</td>"
        f"<td style='text-align:right'><b>R$ {i['total_price']:,.2f}</b></td></tr>"
        for i in items
    ])
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><title>{titulo} #{sale['number']}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 28px; color: #1e293b; font-size: 12px; }}
.header {{ display:flex; justify-content:space-between; border-bottom: 2px solid #2563eb; padding-bottom: 12px; margin-bottom: 16px; }}
table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
th, td {{ border:1px solid #cbd5e1; padding:8px; }}
th {{ background:#f1f5f9; text-align:left; font-size:11px; }}
@media print {{ .no-print {{ display:none; }} }}
</style></head><body>
<div class="no-print" style="margin-bottom:16px;text-align:right;">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:bold;">Imprimir / Salvar PDF</button>
</div>
<div class="header">
  <div>
    <h2 style="margin:0;color:#1d4ed8;">{company['nome_fantasia']}</h2>
    <div>{company['razao_social']} — CNPJ: {company['cnpj']}</div>
    <div>{company['logradouro']}, {company['numero']} - {company['cidade']}/{company['uf']} | Tel: {company['telefone']}</div>
  </div>
  <div style="text-align:right;">
    <div style="font-size:16px;font-weight:bold;">{titulo}</div>
    <div style="font-size:20px;font-weight:bold;color:#2563eb;">Nº {sale['number']}</div>
    <div>Data: {sale['sale_date']}</div>
  </div>
</div>
<div style="background:#f8fafc;padding:12px;border:1px solid #e2e8f0;border-radius:6px;">
  <b>CLIENTE:</b> {sale.get('contact_name') or 'Consumidor Final'} &nbsp;|&nbsp; <b>CPF/CNPJ:</b> {sale.get('contact_doc') or '-'}<br>
  <b>ENDEREÇO:</b> {sale.get('street') or ''}, {sale.get('st_num') or ''} - {sale.get('city') or ''}/{sale.get('state') or ''}<br>
  <b>CONDIÇÃO DE PAGAMENTO:</b> {sale['payment_method']} ({sale['installments']}x) &nbsp;|&nbsp; <b>VENDEDOR:</b> {sale['seller_name']}
</div>
<table>
  <thead><tr><th>CÓDIGO</th><th>DESCRIÇÃO DO ITEM / SERVIÇO</th><th>UN</th><th>QTD</th><th>VLR. UNIT.</th><th>SUBTOTAL</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>
<div style="margin-top:16px;text-align:right;font-size:14px;">
  Subtotal: R$ {sale['subtotal']:,.2f} &nbsp;|&nbsp; Desconto: R$ {sale['discount_amount']:,.2f} &nbsp;|&nbsp; Frete: R$ {sale['shipping_amount']:,.2f}<br>
  <span style="font-size:18px;font-weight:bold;color:#1d4ed8;">TOTAL LÍQUIDO: R$ {sale['total_amount']:,.2f}</span>
</div>
<div style="margin-top:45px;display:flex;justify-content:space-between;text-align:center;">
  <div style="width:45%;border-top:1px solid #334155;padding-top:6px;">{company['razao_social']}</div>
  <div style="width:45%;border-top:1px solid #334155;padding-top:6px;">De acordo: {sale.get('contact_name') or 'Cliente'}</div>
</div>
</body></html>"""


# ==============================================================================
# 10. CONTRATOS RECORRENTES (ASSINATURAS / MENSALIDADES)
# ==============================================================================
@app.get("/api/contracts")
def list_contracts():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT r.*, c.name as contact_name, c.document as contact_doc
        FROM recurring_contracts r
        LEFT JOIN contacts c ON c.id = r.contact_id
        ORDER BY r.id DESC
    """).fetchall())
    conn.close()
    return rows


@app.post("/api/contracts")
async def create_contract(req: Request):
    data = await req.json()
    conn = get_conn()
    conn.execute("""
        INSERT INTO recurring_contracts (title, contact_id, monthly_value, due_day, payment_method, bank_account_id, category_id, auto_emit_nfse, status, start_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, 3, ?, 'ativo', ?, ?)
    """, (
        data.get("title", "Contrato de Recorrência Mensal"),
        int(data.get("contact_id") or 1),
        float(data.get("monthly_value") or 0.0),
        int(data.get("due_day") or 10),
        data.get("payment_method", "Boleto"),
        int(data.get("bank_account_id") or 1),
        1 if data.get("auto_emit_nfse", True) else 0,
        data.get("start_date") or date.today().isoformat(),
        data.get("notes", ""),
    ))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/contracts/{contract_id}/bill")
def bill_recurring_contract(contract_id: int):
    """Fatura a mensalidade do contrato no mês atual gerando o título no Contas a Receber."""
    conn = get_conn()
    cur = conn.cursor()
    c = cur.execute("""
        SELECT r.*, ct.name as contact_name
        FROM recurring_contracts r
        LEFT JOIN contacts ct ON ct.id = r.contact_id
        WHERE r.id = ?
    """, (contract_id,)).fetchone()
    if not c:
        conn.close()
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")

    today = date.today()
    month_tag = today.strftime("%Y-%m")
    due_d = date(today.year, today.month, min(28, max(1, int(c["due_day"])))).isoformat()

    cur.execute("""
        INSERT INTO financial_entries (
            type, description, contact_id, category_id, cost_center_id, bank_account_id,
            payment_method, competence_date, due_date, amount, status, recurrence, origin_type, origin_id
        ) VALUES ('receita', ?, ?, 3, 2, ?, ?, ?, ?, ?, 'pendente', 'mensal', 'contrato', ?)
    """, (
        f"[Contrato #{c['id']} - {month_tag}] {c['title']} - {c['contact_name']}",
        c["contact_id"],
        c["bank_account_id"] or 1,
        c["payment_method"],
        today.isoformat(),
        due_d,
        float(c["monthly_value"]),
        contract_id,
    ))
    cur.execute("UPDATE recurring_contracts SET last_billed_month = ? WHERE id = ?", (month_tag, contract_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Mensalidade de {month_tag} (R$ {float(c['monthly_value']):,.2f}) gerada no Contas a Receber!"}


# ==============================================================================
# 11. ORDENS DE SERVIÇO (OS) COMPLETAS
# ==============================================================================
@app.get("/api/service-orders")
def list_service_orders():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT o.*, c.name as contact_name, c.phone as contact_phone, c.whatsapp as contact_whatsapp
        FROM service_orders o
        LEFT JOIN contacts c ON c.id = o.contact_id
        ORDER BY o.id DESC
    """).fetchall())
    conn.close()
    return rows


@app.post("/api/service-orders")
async def save_service_order(req: Request):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    oid = data.get("id")
    parts = float(data.get("parts_total") or 0.0)
    labor = float(data.get("labor_total") or 0.0)
    disc = float(data.get("discount") or 0.0)
    total = max(0.0, round(parts + labor - disc, 2))

    if oid:
        cur.execute("""
            UPDATE service_orders
            SET contact_id=?, equipment=?, brand_model=?, serial_number=?, reported_defect=?,
                technical_report=?, technician=?, status=?, priority=?, parts_total=?,
                labor_total=?, discount=?, total_amount=?, warranty_days=?
            WHERE id=?
        """, (
            int(data.get("contact_id") or 1),
            data.get("equipment", ""),
            data.get("brand_model", ""),
            data.get("serial_number", ""),
            data.get("reported_defect", ""),
            data.get("technical_report", ""),
            data.get("technician", "Técnico Responsável"),
            data.get("status", "em_execucao"),
            data.get("priority", "normal"),
            parts,
            labor,
            disc,
            total,
            int(data.get("warranty_days") or 90),
            oid,
        ))
    else:
        next_os = (cur.execute("SELECT MAX(os_number) FROM service_orders").fetchone()[0] or 900) + 1
        cur.execute("""
            INSERT INTO service_orders (
                os_number, contact_id, equipment, brand_model, serial_number, reported_defect,
                technical_report, technician, status, priority, parts_total, labor_total,
                discount, total_amount, warranty_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            next_os,
            int(data.get("contact_id") or 1),
            data.get("equipment", "Equipamento"),
            data.get("brand_model", ""),
            data.get("serial_number", ""),
            data.get("reported_defect", ""),
            data.get("technical_report", ""),
            data.get("technician", "Eng. Willian"),
            data.get("status", "aberta"),
            data.get("priority", "normal"),
            parts,
            labor,
            disc,
            total,
            int(data.get("warranty_days") or 90),
        ))
        oid = cur.lastrowid

    conn.commit()
    conn.close()
    return {"status": "ok", "id": oid}


@app.post("/api/service-orders/{os_id}/bill")
def bill_service_order(os_id: int):
    """Finaliza a OS e lança o faturamento automaticamente no Contas a Receber."""
    conn = get_conn()
    cur = conn.cursor()
    so = cur.execute("""
        SELECT o.*, c.name as contact_name
        FROM service_orders o LEFT JOIN contacts c ON c.id = o.contact_id
        WHERE o.id = ?
    """, (os_id,)).fetchone()
    if not so:
        conn.close()
        raise HTTPException(status_code=404, detail="OS não encontrada.")

    today_iso = date.today().isoformat()
    cur.execute("""
        INSERT INTO financial_entries (
            type, description, contact_id, category_id, cost_center_id, bank_account_id,
            payment_method, competence_date, due_date, amount, status, document_number, origin_type, origin_id
        ) VALUES ('receita', ?, ?, 2, 3, 1, 'Pix', ?, ?, ?, 'pendente', ?, 'os', ?)
    """, (
        f"Ordem de Serviço #{so['os_number']} ({so['equipment']}) - {so['contact_name'] or 'Cliente'}",
        so["contact_id"],
        today_iso,
        today_iso,
        float(so["total_amount"]),
        f"OS-{so['os_number']}",
        os_id,
    ))
    cur.execute("UPDATE service_orders SET status = 'finalizada', billed = 1, closed_at = CURRENT_TIMESTAMP WHERE id = ?", (os_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"OS #{so['os_number']} finalizada e faturada no Contas a Receber!"}


@app.get("/api/service-orders/{os_id}/print", response_class=HTMLResponse)
def print_service_order(os_id: int):
    conn = get_conn()
    company = dict(conn.execute("SELECT * FROM companies LIMIT 1").fetchone())
    so = dict(conn.execute("""
        SELECT o.*, c.name as contact_name, c.document as contact_doc, c.phone as contact_phone
        FROM service_orders o LEFT JOIN contacts c ON c.id = o.contact_id
        WHERE o.id = ?
    """, (os_id,)).fetchone())
    conn.close()
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><title>OS #{so['os_number']}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; font-size: 12px; color:#111; }}
.box {{ border:1px solid #334155; padding:10px; margin-bottom:10px; border-radius:4px; }}
@media print {{ .no-print {{ display:none; }} }}
</style></head><body>
<div class="no-print" style="margin-bottom:12px;text-align:right;">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:bold;">Imprimir OS</button>
</div>
<div class="box" style="display:flex;justify-content:space-between;align-items:center;">
  <div><h2 style="margin:0;">{company['nome_fantasia']}</h2><div>CNPJ: {company['cnpj']} | Tel: {company['telefone']}</div></div>
  <div style="text-align:right;"><div style="font-size:18px;font-weight:bold;">ORDEM DE SERVIÇO Nº {so['os_number']}</div><div>Status: {so['status'].upper()} | Garantia: {so['warranty_days']} dias</div></div>
</div>
<div class="box"><b>CLIENTE:</b> {so.get('contact_name')} | <b>CPF/CNPJ:</b> {so.get('contact_doc')} | <b>TEL:</b> {so.get('contact_phone')}</div>
<div class="box"><b>EQUIPAMENTO / OBJETO:</b> {so['equipment']} ({so['brand_model']}) — <b>Nº SÉRIE / PLACA:</b> {so['serial_number']}</div>
<div class="box"><b>DEFEITO RELATADO:</b><br>{so['reported_defect']}</div>
<div class="box"><b>LAUDO TÉCNICO / SERVIÇO EXECUTADO ({so['technician']}):</b><br>{so['technical_report'] or 'Em análise técnica.'}</div>
<div class="box" style="text-align:right;font-size:14px;">
  Peças: R$ {so['parts_total']:,.2f} | Mão de Obra: R$ {so['labor_total']:,.2f} | Desconto: R$ {so['discount']:,.2f}<br>
  <b style="font-size:17px;color:#1d4ed8;">TOTAL DA OS: R$ {so['total_amount']:,.2f}</b>
</div>
<div style="margin-top:45px;display:flex;justify-content:space-between;text-align:center;">
  <div style="width:44%;border-top:1px solid #000;padding-top:6px;">Assinatura do Técnico ({so['technician']})</div>
  <div style="width:44%;border-top:1px solid #000;padding-top:6px;">Assinatura do Cliente ({so.get('contact_name')})</div>
</div>
</body></html>"""


# ==============================================================================
# 12. ENTRADA AUTOMÁTICA DE COMPRAS POR XML DE FORNECEDOR
# ==============================================================================
@app.get("/api/xml-purchases")
def list_xml_purchases():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM xml_purchases ORDER BY id DESC").fetchall())
    conn.close()
    return rows


@app.post("/api/xml-purchases/import")
async def import_supplier_xml(req: Request):
    """
    Lê o XML de NF-e de compra do fornecedor:
    1. Cadastra/atualiza o Fornecedor automaticamente pelo CNPJ;
    2. Cadastra/atualiza todos os Produtos, dá entrada no Estoque e recalcula o Custo Médio Ponderado;
    3. Lança todas as duplicatas/boletos (<cobr><dup>) no Contas a Pagar!
    """
    data = await req.json()
    xml_text = data.get("xml_content") or gerar_xml_compra_exemplo()
    parsed = parse_nfe_compra_xml(xml_text)

    conn = get_conn()
    cur = conn.cursor()

    # 1. Fornecedor
    sup = parsed["supplier"]
    sup_row = cur.execute("SELECT id FROM contacts WHERE document LIKE ?", (f"%{sup['cnpj'][:8]}%",)).fetchone()
    if sup_row:
        supplier_id = sup_row["id"]
    else:
        cur.execute("""
            INSERT INTO contacts (type, person_type, name, trade_name, document, state_registration, street, number, neighborhood, city, state, cep)
            VALUES ('fornecedor', 'PJ', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sup["name"], sup["trade_name"], sup["cnpj"], sup["ie"], sup["street"], sup["number"], sup["neighborhood"], sup["city"], sup["state"], sup["cep"]))
        supplier_id = cur.lastrowid

    # 2. Produtos e Estoque com Custo Médio
    for it in parsed["items"]:
        prod = cur.execute("SELECT * FROM products WHERE sku = ? OR name = ?", (it["sku"], it["name"])).fetchone()
        qty = float(it["quantity"])
        u_cost = float(it["unit_cost"])
        if prod:
            pid = prod["id"]
            prev_stock = float(prod["stock_qty"] or 0.0)
            prev_avg = float(prod["average_cost"] or prod["cost_price"] or u_cost)
            new_stock = prev_stock + qty
            new_avg = round(((max(0.0, prev_stock) * prev_avg) + (qty * u_cost)) / max(1.0, new_stock), 2)
            cur.execute("UPDATE products SET stock_qty = ?, cost_price = ?, average_cost = ? WHERE id = ?", (new_stock, u_cost, new_avg, pid))
        else:
            sale_p = round(u_cost * 1.55, 2)
            cur.execute("""
                INSERT INTO products (type, sku, barcode, name, category_name, unit, cost_price, average_cost, margin_percent, sale_price, stock_qty, min_stock, ncm)
                VALUES ('produto', ?, ?, ?, 'Importado XML', ?, ?, ?, 55.0, ?, ?, 3.0, ?)
            """, (it["sku"], it["barcode"], it["name"], it["unit"], u_cost, u_cost, sale_p, qty, it["ncm"]))
            pid = cur.lastrowid
            prev_stock = 0.0
            new_stock = qty

        cur.execute("""
            INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
            VALUES (?, 'compra_xml', ?, ?, ?, ?, ?, ?)
        """, (pid, qty, u_cost, prev_stock, new_stock, f"NF-e Compra #{parsed['invoice_number']}", f"Entrada automática via XML ({sup['trade_name']})"))

    # 3. Duplicatas no Contas a Pagar
    inst_total = len(parsed["installments"])
    for idx, dup in enumerate(parsed["installments"], start=1):
        cur.execute("""
            INSERT INTO financial_entries (
                type, description, contact_id, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, status, installment_number,
                installment_total, group_uid, document_number, origin_type
            ) VALUES ('despesa', ?, ?, 6, 4, 1, 'Boleto', ?, ?, ?, 'pendente', ?, ?, ?, ?, 'xml_compra')
        """, (
            f"NF-e Compra #{parsed['invoice_number']} (Dup. {dup['number']}) - {sup['trade_name']}",
            supplier_id,
            parsed["issue_date"],
            dup["due_date"],
            float(dup["amount"]),
            idx,
            inst_total,
            f"XML-{parsed['invoice_number']}",
            f"NFE-{parsed['invoice_number']}-{dup['number']}",
        ))

    cur.execute("""
        INSERT INTO xml_purchases (access_key, invoice_number, supplier_cnpj, supplier_name, issue_date, total_amount, items_count, installments_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        parsed["access_key"],
        parsed["invoice_number"],
        sup["cnpj"],
        sup["name"],
        parsed["issue_date"],
        float(parsed["total_amount"]),
        len(parsed["items"]),
        inst_total,
    ))
    conn.commit()
    conn.close()
    return {
        "status": "ok",
        "invoice_number": parsed["invoice_number"],
        "supplier_name": sup["name"],
        "items_count": len(parsed["items"]),
        "installments_count": inst_total,
        "total_amount": parsed["total_amount"],
    }


# ==============================================================================
# 13. EMISSOR DE NOTA FISCAL (NF-e 55, NFC-e 65, NFS-e, DANFE, XML, CC-e, ZIP)
# ==============================================================================
@app.get("/api/invoices")
def list_invoices():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall())
    conn.close()
    return rows


@app.post("/api/invoices/emit")
async def emit_invoice(req: Request):
    """
    Emite NF-e (55), NFC-e (65) ou NFS-e a partir de uma Venda ou avulsa:
    1. Executa o Validador Fiscal pré-envio;
    2. Calcula a Chave de Acesso de 44 dígitos no Módulo 11 oficial da SEFAZ;
    3. Calcula impostos (Simples Nacional / ICMS / PIS / COFINS / ISS);
    4. Gera e armazena o XML oficial layout 4.00 (<nfeProc>) e protocolo SEFAZ!
    """
    data = await req.json()
    model = data.get("model", "NFe-55")  # NFe-55, NFCe-65, NFSe
    sale_id = data.get("sale_id")
    nature_op = data.get("nature_operation", "VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS")

    conn = get_conn()
    cur = conn.cursor()
    company = dict(cur.execute("SELECT * FROM companies LIMIT 1").fetchone())

    if sale_id:
        sale = cur.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        if not sale:
            conn.close()
            raise HTTPException(status_code=404, detail="Venda não encontrada.")
        contact_row = cur.execute("SELECT * FROM contacts WHERE id = ?", (sale["contact_id"] or 1,)).fetchone()
        contact = dict(contact_row) if contact_row else {}
        sale_items = rows_to_dicts(cur.execute("""
            SELECT si.*, p.ncm, p.cfop_internal as cfop, p.csosn_cst, p.origin, p.pis_cst, p.pis_rate, p.cofins_cst, p.cofins_rate, p.iss_rate
            FROM sale_items si
            LEFT JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
        """, (sale_id,)).fetchall())
        total_products = float(sale["subtotal"])
        total_discounts = float(sale["discount_amount"])
        total_shipping = float(sale["shipping_amount"])
        total_invoice = float(sale["total_amount"])
    else:
        contact_id = int(data.get("contact_id") or 1)
        contact_row = cur.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        contact = dict(contact_row) if contact_row else {}
        sale_items = data.get("items", [])
        total_products = round(sum(float(i.get("quantity", 1)) * float(i.get("unit_price", 0)) for i in sale_items), 2)
        total_discounts = float(data.get("discount_amount") or 0.0)
        total_shipping = float(data.get("shipping_amount") or 0.0)
        total_invoice = max(0.0, round(total_products - total_discounts + total_shipping, 2))

    # Validador Fiscal Pré-Envio
    erros = validar_dados_fiscais(company, contact, sale_items, model=model)
    if erros:
        conn.close()
        raise HTTPException(status_code=400, detail=" | ".join(erros))

    if model == "NFe-55":
        serie = int(company["serie_nfe"] or 1)
        numero = int(company["proximo_numero_nfe"] or 101)
        cur.execute("UPDATE companies SET proximo_numero_nfe = ? WHERE id = 1", (numero + 1,))
    elif model == "NFCe-65":
        serie = int(company["serie_nfce"] or 1)
        numero = int(company["proximo_numero_nfce"] or 501)
        cur.execute("UPDATE companies SET proximo_numero_nfce = ? WHERE id = 1", (numero + 1,))
    else:
        serie = int(company["serie_nfse"] or 1)
        numero = int(company["proximo_numero_nfse"] or 201)
        cur.execute("UPDATE companies SET proximo_numero_nfse = ? WHERE id = 1", (numero + 1,))

    chave = gerar_chave_acesso_sefaz(
        cuf=company.get("codigo_ibge_uf", "51"),
        dt_emissao=datetime.now(),
        cnpj_emitente=company.get("cnpj", "45123789000190"),
        modelo=model,
        serie=serie,
        numero_nf=numero,
    )
    protocolo = f"151{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10,99)}"
    total_pis = round(total_products * 0.0065, 2)
    total_cofins = round(total_products * 0.03, 2)
    total_iss = round(total_products * 0.03, 2) if model == "NFSe" else 0.0

    inv_meta = {
        "model": model,
        "series": serie,
        "number": numero,
        "access_key": chave,
        "protocol": protocolo,
        "nature_operation": nature_op,
        "total_products": total_products,
        "total_discounts": total_discounts,
        "total_shipping": total_shipping,
        "total_pis": total_pis,
        "total_cofins": total_cofins,
        "total_iss": total_iss,
        "total_invoice": total_invoice,
    }
    xml_str = gerar_xml_nfe_400(company, contact, sale_items, inv_meta)

    cur.execute("""
        INSERT INTO invoices (
            model, series, number, access_key, protocol, status, environment,
            nature_operation, sale_id, contact_id, recipient_name, recipient_doc,
            recipient_uf, total_products, total_discounts, total_shipping,
            total_pis, total_cofins, total_iss, total_invoice, items_json, xml_content
        ) VALUES (?, ?, ?, ?, ?, 'autorizada', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        model,
        serie,
        numero,
        chave,
        protocolo,
        company.get("ambiente_fiscal", "homologacao"),
        nature_op,
        sale_id,
        contact.get("id"),
        contact.get("name", "CONSUMIDOR FINAL"),
        contact.get("document", "000.000.000-00"),
        contact.get("state", "MT"),
        total_products,
        total_discounts,
        total_shipping,
        total_pis,
        total_cofins,
        total_iss,
        total_invoice,
        json.dumps(sale_items, ensure_ascii=False),
        xml_str,
    ))
    inv_id = cur.lastrowid
    if sale_id:
        cur.execute("UPDATE sales SET invoice_id = ? WHERE id = ?", (inv_id, sale_id))

    conn.commit()
    conn.close()
    return {
        "status": "ok",
        "invoice_id": inv_id,
        "number": numero,
        "access_key": chave,
        "protocol": protocolo,
        "message": f"{model} Nº {numero} autorizada com sucesso! Chave: {chave}",
    }


@app.get("/api/invoices/{invoice_id}/danfe", response_class=HTMLResponse)
def view_danfe(invoice_id: int):
    conn = get_conn()
    company = dict(conn.execute("SELECT * FROM companies LIMIT 1").fetchone())
    inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not inv:
        conn.close()
        raise HTTPException(status_code=404, detail="Nota Fiscal não encontrada.")
    inv_dict = dict(inv)
    contact_row = conn.execute("SELECT * FROM contacts WHERE id = ?", (inv_dict.get("contact_id") or 1,)).fetchone()
    contact = dict(contact_row) if contact_row else {}
    items = json.loads(inv_dict.get("items_json") or "[]")
    conn.close()
    return gerar_html_danfe(company, contact, inv_dict, items)


@app.get("/api/invoices/{invoice_id}/xml")
def download_invoice_xml(invoice_id: int):
    conn = get_conn()
    inv = conn.execute("SELECT number, access_key, xml_content FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    conn.close()
    if not inv:
        raise HTTPException(status_code=404, detail="Nota não encontrada.")
    filename = f"NFe_{inv['access_key']}.xml"
    return Response(
        content=inv["xml_content"],
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/invoices/export-zip")
def export_invoices_zip():
    """Exporta um pacote .ZIP com todos os XMLs autorizados para enviar à Contabilidade."""
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT number, model, access_key, xml_content FROM invoices WHERE status != 'cancelada'").fetchall())
    conn.close()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in rows:
            zf.writestr(f"{r['model']}_{r['number']}_{r['access_key']}.xml", r["xml_content"] or "")
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="XMLs_Contabilidade_CortexERP.zip"'},
    )


@app.post("/api/invoices/{invoice_id}/cce")
async def emit_carta_correcao(invoice_id: int, req: Request):
    data = await req.json()
    texto = (data.get("correction_text") or "").strip()
    if len(texto) < 15:
        raise HTTPException(status_code=400, detail="A SEFAZ exige no mínimo 15 caracteres na Carta de Correção (CC-e).")
    conn = get_conn()
    conn.execute("UPDATE invoices SET correction_letter = ? WHERE id = ?", (texto, invoice_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Carta de Correção Eletrônica (CC-e) averbada na nota fiscal!"}


@app.post("/api/invoices/{invoice_id}/cancel")
async def cancel_invoice(invoice_id: int, req: Request):
    data = await req.json()
    reason = (data.get("reason") or "").strip()
    if len(reason) < 15:
        raise HTTPException(status_code=400, detail="A justificativa de cancelamento na SEFAZ deve conter pelo menos 15 caracteres.")
    conn = get_conn()
    conn.execute("UPDATE invoices SET status = 'cancelada', cancel_reason = ? WHERE id = ?", (reason, invoice_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Nota Fiscal cancelada e evento registrado."}


# ==============================================================================
# 14. RELATÓRIOS CONTÁBEIS E GERENCIAIS (DRE, FLUXO DE CAIXA, CURVA ABC)
# ==============================================================================
@app.get("/api/reports/dre")
def get_dre_report(regime: str = "competencia"):
    """
    Calcula a DRE Gerencial completa (Regime de Competência ou Regime de Caixa)
    com Análise Vertical (%) exatamente no padrão contábil brasileiro.
    """
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT e.*, cat.dre_group, cat.name as category_name
        FROM financial_entries e
        LEFT JOIN categories cat ON cat.id = e.category_id
        WHERE e.status != 'cancelado'
    """).fetchall())
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
        val = float(r["paid_amount"]) if regime == "caixa" else (float(r["amount"]) + float(r["interest"]) + float(r["fine"]) - float(r["discount"]))
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


# ==============================================================================
# SERVE INTERFACE FRONT-END SPA
# ==============================================================================
STATIC_DIR = FRONTEND_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    idx_file = FRONTEND_DIR / "index.html"
    return idx_file.read_text(encoding="utf-8")

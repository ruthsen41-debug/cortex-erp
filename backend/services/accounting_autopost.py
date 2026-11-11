"""
Serviço de lançamentos contábeis automáticos.
Executado após cada baixa financeira para gerar as partidas dobradas.
"""
from datetime import date


# Mapa de forma de pagamento → conta contábil de caixa/banco
_PAYMENT_METHOD_ACCOUNT = {
    "dinheiro": "1.1.01",
    "caixa":    "1.1.01",
}
_DEFAULT_BANK_ACCOUNT_CODE = "1.1.02"  # Bancos c/ Movimento

# Contas fixas usadas nos lançamentos automáticos
_CODE_CLIENTES        = "1.1.04"   # Clientes / Contas a Receber
_CODE_FORNECEDORES    = "2.1.01"   # Fornecedores / Contas a Pagar
_CODE_JUROS_ATIVOS    = "3.3.01"   # Juros Ativos e Descontos Obtidos
_CODE_JUROS_PASSIVOS  = "5.4.02"   # Juros e Multas Passivos
_CODE_DESC_CONCEDIDO  = "5.4.03"   # Descontos Concedidos


def _get_account_id(conn, code: str, company_id: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM accounting_accounts WHERE code = ? AND company_id = ? AND active = 1",
        (code, company_id)
    ).fetchone()
    return row["id"] if row else None


def _resolve_cash_account(conn, payment_method: str, company_id: int) -> int | None:
    method_lower = (payment_method or "").lower()
    code = _PAYMENT_METHOD_ACCOUNT.get(method_lower, _DEFAULT_BANK_ACCOUNT_CODE)
    return _get_account_id(conn, code, company_id)


def _create_accounting_entry(conn, company_id: int, entry_date: str,
                              description: str, document_number: str,
                              lines: list[dict], origin_id: int | None = None) -> int | None:
    """Cria lançamento contábil (cabeçalho + linhas) e retorna o id."""
    total_debit = round(sum(ln.get("debit", 0.0) for ln in lines), 2)
    total_credit = round(sum(ln.get("credit", 0.0) for ln in lines), 2)

    if abs(total_debit - total_credit) > 0.02:
        return None  # não gera lançamento desbalanceado

    # Verifica se todas as contas existem
    for ln in lines:
        if not ln.get("account_id"):
            return None

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO accounting_entries
            (company_id, entry_date, description, document_number, entry_type, origin_id, total_debit, total_credit)
        VALUES (?, ?, ?, ?, 'automatico', ?, ?, ?)
    """, (company_id, entry_date, description, document_number or "", origin_id, total_debit, total_credit))
    ae_id = cur.lastrowid

    for ln in lines:
        cur.execute("""
            INSERT INTO accounting_entry_lines (entry_id, account_id, debit, credit, description)
            VALUES (?, ?, ?, ?, ?)
        """, (ae_id, ln["account_id"], round(ln.get("debit", 0.0), 2),
              round(ln.get("credit", 0.0), 2), ln.get("description", "")))
    return ae_id


def autopost_payment(conn, entry_id: int, payment_id: int, company_id: int) -> int | None:
    """
    Gera lançamento contábil automático para uma baixa financeira.
    Retorna o id do lançamento contábil criado (ou None se não foi possível).
    """
    entry = conn.execute("SELECT * FROM financial_entries WHERE id = ?", (entry_id,)).fetchone()
    payment = conn.execute("SELECT * FROM financial_payments WHERE id = ?", (payment_id,)).fetchone()
    if not entry or not payment:
        return None

    entry = dict(entry)
    payment = dict(payment)

    e_type        = entry["type"]          # receita / despesa
    description   = entry["description"]
    doc_number    = entry.get("document_number") or ""
    payment_date  = payment["payment_date"] or date.today().isoformat()
    principal     = round(float(payment["principal_paid"] or 0.0), 2)
    interest      = round(float(payment.get("interest_paid") or 0.0), 2)
    fine          = round(float(payment.get("fine_paid") or 0.0), 2)
    discount      = round(float(payment.get("discount_applied") or 0.0), 2)
    total_cash    = round(float(payment["total_cash_flow"] or 0.0), 2)
    pay_method    = payment.get("payment_method") or entry.get("payment_method") or "Pix"

    cash_acc_id  = _resolve_cash_account(conn, pay_method, company_id)
    if not cash_acc_id:
        return None

    ae_desc = f"Baixa automática: {description}"

    if e_type == "receita":
        cliente_id = _get_account_id(conn, _CODE_CLIENTES, company_id)
        if not cliente_id:
            return None

        lines = []
        # Banco/Caixa recebe o valor total pago
        lines.append({"account_id": cash_acc_id, "debit": total_cash, "credit": 0.0,
                       "description": f"Recebimento via {pay_method}"})
        # Baixa o contas a receber pelo principal
        lines.append({"account_id": cliente_id, "debit": 0.0, "credit": principal,
                       "description": "Baixa Clientes"})

        # Desconto concedido (D: Descontos Concedidos / C já foi no cliente acima)
        if discount > 0:
            desc_id = _get_account_id(conn, _CODE_DESC_CONCEDIDO, company_id)
            if desc_id:
                lines.append({"account_id": desc_id, "debit": discount, "credit": 0.0,
                               "description": "Desconto concedido"})
                # Ajusta o crédito em clientes para incluir o desconto
                lines[1]["credit"] = round(principal + discount, 2)

        # Juros/Multa ativos recebidos
        juros_total = round(interest + fine, 2)
        if juros_total > 0:
            juros_id = _get_account_id(conn, _CODE_JUROS_ATIVOS, company_id)
            if juros_id:
                lines.append({"account_id": juros_id, "debit": 0.0, "credit": juros_total,
                               "description": "Juros e multa recebidos"})

    elif e_type == "despesa":
        fornecedor_id = _get_account_id(conn, _CODE_FORNECEDORES, company_id)
        if not fornecedor_id:
            return None

        lines = []
        # Baixa o contas a pagar
        lines.append({"account_id": fornecedor_id, "debit": principal, "credit": 0.0,
                       "description": "Baixa Fornecedores"})
        # Banco/Caixa paga o valor total
        lines.append({"account_id": cash_acc_id, "debit": 0.0, "credit": total_cash,
                       "description": f"Pagamento via {pay_method}"})

        # Juros/Multa passivos pagos
        juros_total = round(interest + fine, 2)
        if juros_total > 0:
            juros_id = _get_account_id(conn, _CODE_JUROS_PASSIVOS, company_id)
            if juros_id:
                lines.append({"account_id": juros_id, "debit": juros_total, "credit": 0.0,
                               "description": "Juros e multa pagos"})
                # Ajusta débito do fornecedor
                lines[0]["debit"] = round(principal - juros_total, 2)

        # Desconto obtido
        if discount > 0:
            desc_id = _get_account_id(conn, _CODE_JUROS_ATIVOS, company_id)
            if desc_id:
                lines.append({"account_id": desc_id, "debit": 0.0, "credit": discount,
                               "description": "Desconto obtido"})
                lines[0]["debit"] = round(lines[0]["debit"] + discount, 2)
    else:
        return None

    return _create_accounting_entry(
        conn, company_id, payment_date, ae_desc, doc_number, lines, origin_id=entry_id
    )


def autopost_reversal(conn, entry_id: int, company_id: int) -> int | None:
    """
    Gera lançamento de estorno para todos os lançamentos automáticos de uma baixa.
    Chamado quando o router financeiro faz o estorno (reverse).
    """
    # Busca todos os lançamentos automáticos originados deste entry
    auto_entries = conn.execute("""
        SELECT id FROM accounting_entries
        WHERE origin_id = ? AND company_id = ? AND entry_type = 'automatico'
    """, (entry_id, company_id)).fetchall()

    if not auto_entries:
        return None

    last_id = None
    for ae_row in auto_entries:
        ae_id = ae_row["id"]
        orig = dict(conn.execute("SELECT * FROM accounting_entries WHERE id = ?", (ae_id,)).fetchone())
        lines_raw = conn.execute(
            "SELECT * FROM accounting_entry_lines WHERE entry_id = ?", (ae_id,)
        ).fetchall()

        # Inverte débito/crédito de cada linha
        reversed_lines = []
        for ln in lines_raw:
            ln = dict(ln)
            reversed_lines.append({
                "account_id": ln["account_id"],
                "debit":  round(float(ln["credit"] or 0.0), 2),
                "credit": round(float(ln["debit"] or 0.0), 2),
                "description": f"ESTORNO: {ln['description']}",
            })

        last_id = _create_accounting_entry(
            conn, company_id,
            date.today().isoformat(),
            f"ESTORNO: {orig['description']}",
            orig.get("document_number") or "",
            reversed_lines,
            origin_id=entry_id,
        )

    return last_id

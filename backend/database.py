import sqlite3
import json
from pathlib import Path
from datetime import datetime, date, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "cortex_erp.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    # 1. Empresas / Configurações Fiscais e Certificado Digital A1
    cur.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        razao_social TEXT NOT NULL,
        nome_fantasia TEXT NOT NULL,
        cnpj TEXT NOT NULL,
        inscricao_estadual TEXT DEFAULT '',
        inscricao_municipal TEXT DEFAULT '',
        regime_tributario TEXT DEFAULT 'simples_nacional', -- simples_nacional, lucro_presumido, lucro_real, mei
        cnae_principal TEXT DEFAULT '6201-5/01',
        aliquota_simples REAL DEFAULT 6.0,
        cep TEXT DEFAULT '',
        logradouro TEXT DEFAULT '',
        numero TEXT DEFAULT '',
        complemento TEXT DEFAULT '',
        bairro TEXT DEFAULT '',
        cidade TEXT DEFAULT 'Cáceres',
        uf TEXT DEFAULT 'MT',
        codigo_ibge_uf TEXT DEFAULT '51',
        codigo_ibge_municipio TEXT DEFAULT '5102504',
        telefone TEXT DEFAULT '',
        email TEXT DEFAULT '',
        chave_pix TEXT DEFAULT '',
        ambiente_fiscal TEXT DEFAULT 'homologacao', -- homologacao, producao
        motor_fiscal TEXT DEFAULT 'sefaz_direto', -- sefaz_direto, nuvem_fiscal, focus_nfe
        api_fiscal_token TEXT DEFAULT '',
        serie_nfe INTEGER DEFAULT 1,
        proximo_numero_nfe INTEGER DEFAULT 101,
        serie_nfce INTEGER DEFAULT 1,
        proximo_numero_nfce INTEGER DEFAULT 501,
        serie_nfse INTEGER DEFAULT 1,
        proximo_numero_nfse INTEGER DEFAULT 201,
        csc_id TEXT DEFAULT '000001',
        csc_token TEXT DEFAULT 'CORTEX-ERP-CSC-HOMOLOGACAO',
        certificado_nome TEXT DEFAULT '',
        certificado_validade TEXT DEFAULT '',
        certificado_titular TEXT DEFAULT '',
        certificado_b64 TEXT DEFAULT '',
        certificado_senha TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Contas Bancárias / Caixas / Cartões
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bank_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        bank_code TEXT DEFAULT '000',
        bank_name TEXT NOT NULL,
        agency TEXT DEFAULT '',
        account_number TEXT DEFAULT '',
        account_type TEXT DEFAULT 'corrente', -- corrente, caixa, poupanca, investimento, cartao_credito
        initial_balance REAL DEFAULT 0.0,
        current_balance REAL DEFAULT 0.0,
        color TEXT DEFAULT '#2563eb',
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Categorias Financeiras (Plano de Contas DRE)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL, -- receita, despesa
        dre_group TEXT NOT NULL,
        -- receita_bruta, deducoes_impostos, custos_mercadorias_servicos,
        -- despesas_pessoal, despesas_operacionais, despesas_comerciais,
        -- receitas_financeiras, despesas_financeiras, investimentos
        keywords TEXT DEFAULT ''
    );
    """)

    # 4. Centros de Custo
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cost_centers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        monthly_budget REAL DEFAULT 0.0,
        active INTEGER DEFAULT 1
    );
    """)

    # 5. Contatos (Clientes, Fornecedores, Transportadoras)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT DEFAULT 'cliente', -- cliente, fornecedor, ambos, transportadora
        person_type TEXT DEFAULT 'PJ', -- PF, PJ
        name TEXT NOT NULL,
        trade_name TEXT DEFAULT '',
        document TEXT DEFAULT '', -- CPF ou CNPJ
        ie_indicator TEXT DEFAULT '9', -- 1=Contribuinte, 2=Isento, 9=Não Contribuinte
        state_registration TEXT DEFAULT '',
        municipal_registration TEXT DEFAULT '',
        email TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        whatsapp TEXT DEFAULT '',
        cep TEXT DEFAULT '',
        street TEXT DEFAULT '',
        number TEXT DEFAULT '',
        complement TEXT DEFAULT '',
        neighborhood TEXT DEFAULT '',
        city TEXT DEFAULT '',
        state TEXT DEFAULT '',
        ibge_code TEXT DEFAULT '5102504',
        credit_limit REAL DEFAULT 0.0,
        notes TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. Produtos e Serviços (com Ficha Fiscal completa e Estoque/Custo Médio)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT DEFAULT 'produto', -- produto, servico
        sku TEXT NOT NULL,
        barcode TEXT DEFAULT '',
        name TEXT NOT NULL,
        category_name TEXT DEFAULT 'Geral',
        unit TEXT DEFAULT 'UN', -- UN, KG, CX, MT, HR, SV, LT
        cost_price REAL DEFAULT 0.0,
        average_cost REAL DEFAULT 0.0,
        margin_percent REAL DEFAULT 50.0,
        sale_price REAL DEFAULT 0.0,
        stock_qty REAL DEFAULT 0.0,
        min_stock REAL DEFAULT 5.0,
        -- Ficha Fiscal (NF-e / NFC-e / NFS-e)
        ncm TEXT DEFAULT '84713012',
        cest TEXT DEFAULT '',
        origin TEXT DEFAULT '0', -- 0=Nacional, 1=Estrangeira importação direta, 2=Estrangeira mercado interno
        cfop_internal TEXT DEFAULT '5102',
        cfop_external TEXT DEFAULT '6102',
        csosn_cst TEXT DEFAULT '102', -- 102, 101, 500 (Simples) ou 00, 20, 60 (Normal)
        icms_rate REAL DEFAULT 0.0,
        pis_cst TEXT DEFAULT '07',
        pis_rate REAL DEFAULT 0.65,
        cofins_cst TEXT DEFAULT '07',
        cofins_rate REAL DEFAULT 3.0,
        ipi_rate REAL DEFAULT 0.0,
        service_code_lc116 TEXT DEFAULT '01.07',
        iss_rate REAL DEFAULT 3.0,
        iss_retained INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 7. Kardex / Movimentações de Estoque
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        movement_type TEXT NOT NULL, -- entrada, saida, ajuste, compra_xml, venda
        quantity REAL NOT NULL,
        unit_cost REAL DEFAULT 0.0,
        previous_stock REAL DEFAULT 0.0,
        new_stock REAL DEFAULT 0.0,
        reference TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );
    """)

    # 8. Lançamentos Financeiros (Contas a Pagar / Contas a Receber / Transferências)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS financial_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL, -- receita, despesa, transferencia
        description TEXT NOT NULL,
        contact_id INTEGER,
        category_id INTEGER,
        cost_center_id INTEGER,
        bank_account_id INTEGER,
        payment_method TEXT DEFAULT 'Pix', -- Pix, Boleto, Cartão de Crédito, Cartão de Débito, Transferência/TED, Dinheiro
        competence_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        amount REAL NOT NULL, -- Valor original da parcela
        interest REAL DEFAULT 0.0, -- Juros acumulados
        fine REAL DEFAULT 0.0, -- Multa acumulada
        discount REAL DEFAULT 0.0, -- Desconto concedido
        paid_amount REAL DEFAULT 0.0, -- Total já baixado (suporta baixa parcial!)
        status TEXT DEFAULT 'pendente', -- pendente, parcial, pago, cancelado
        installment_number INTEGER DEFAULT 1,
        installment_total INTEGER DEFAULT 1,
        group_uid TEXT DEFAULT '',
        recurrence TEXT DEFAULT 'unico', -- unico, mensal, semanal, anual
        document_number TEXT DEFAULT '',
        barcode TEXT DEFAULT '',
        origin_type TEXT DEFAULT 'manual', -- manual, venda, pdv, os, xml_compra, ofx, contrato, ia
        origin_id INTEGER,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
        FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id) ON DELETE SET NULL,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE SET NULL
    );
    """)

    # 9. Histórico de Baixas (Suporte a Baixas Parciais, Juros/Multa por Baixa e Estornos)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS financial_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER NOT NULL,
        bank_account_id INTEGER NOT NULL,
        payment_date TEXT NOT NULL,
        principal_paid REAL NOT NULL, -- Valor abatido do principal
        interest_paid REAL DEFAULT 0.0,
        fine_paid REAL DEFAULT 0.0,
        discount_applied REAL DEFAULT 0.0,
        total_cash_flow REAL NOT NULL, -- Valor efetivo que saiu/entrou no banco
        payment_method TEXT DEFAULT 'Pix',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (entry_id) REFERENCES financial_entries(id) ON DELETE CASCADE,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE
    );
    """)

    # 10. Conciliação Bancária OFX
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ofx_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_account_id INTEGER NOT NULL,
        fitid TEXT NOT NULL,
        posted_date TEXT NOT NULL,
        amount REAL NOT NULL, -- positivo = crédito, negativo = débito
        memo TEXT NOT NULL,
        suggested_category_id INTEGER,
        matched_entry_id INTEGER,
        status TEXT DEFAULT 'pendente', -- pendente, conciliado, ignorado
        reconciled_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE
    );
    """)

    # 11. CRM Funil de Vendas (Kanban)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS crm_deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        contact_id INTEGER,
        contact_name TEXT DEFAULT '',
        stage TEXT DEFAULT 'prospeccao', -- prospeccao, qualificacao, proposta, negociacao, ganho, perdido
        estimated_value REAL DEFAULT 0.0,
        probability INTEGER DEFAULT 50,
        expected_close_date TEXT DEFAULT '',
        responsible TEXT DEFAULT 'Consultor Comercial',
        temperature TEXT DEFAULT 'morno', -- frio, morno, quente
        notes TEXT DEFAULT '',
        converted_sale_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 12. Orçamentos, Vendas e Frente de Caixa (PDV)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number INTEGER NOT NULL,
        sale_type TEXT DEFAULT 'venda', -- orcamento, venda, pdv
        status TEXT DEFAULT 'aprovada', -- rascunho, enviado, aprovada, faturada, cancelada
        contact_id INTEGER,
        seller_name TEXT DEFAULT 'Consultor Padrão',
        sale_date TEXT NOT NULL,
        valid_until TEXT DEFAULT '',
        subtotal REAL DEFAULT 0.0,
        discount_amount REAL DEFAULT 0.0,
        shipping_amount REAL DEFAULT 0.0,
        total_amount REAL DEFAULT 0.0,
        payment_method TEXT DEFAULT 'Pix',
        installments INTEGER DEFAULT 1,
        bank_account_id INTEGER DEFAULT 1,
        invoice_id INTEGER,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT NOT NULL,
        sku TEXT DEFAULT '',
        unit TEXT DEFAULT 'UN',
        quantity REAL NOT NULL,
        unit_price REAL NOT NULL,
        discount REAL DEFAULT 0.0,
        total_price REAL NOT NULL,
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
    );
    """)

    # 13. Contratos Recorrentes (Assinaturas / Mensalidades)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recurring_contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        contact_id INTEGER NOT NULL,
        product_id INTEGER,
        monthly_value REAL NOT NULL,
        due_day INTEGER DEFAULT 10,
        payment_method TEXT DEFAULT 'Boleto',
        bank_account_id INTEGER DEFAULT 1,
        category_id INTEGER DEFAULT 1,
        auto_emit_nfse INTEGER DEFAULT 1,
        status TEXT DEFAULT 'ativo', -- ativo, suspenso, encerrado
        last_billed_month TEXT DEFAULT '',
        start_date TEXT NOT NULL,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
    );
    """)

    # 14. Ordens de Serviço (OS)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS service_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        os_number INTEGER NOT NULL,
        contact_id INTEGER,
        equipment TEXT NOT NULL,
        brand_model TEXT DEFAULT '',
        serial_number TEXT DEFAULT '',
        reported_defect TEXT NOT NULL,
        technical_report TEXT DEFAULT '',
        technician TEXT DEFAULT 'Técnico Responsável',
        status TEXT DEFAULT 'aberta', -- aberta, em_analise, aguardando_aprovacao, em_execucao, finalizada, entregue, cancelada
        priority TEXT DEFAULT 'normal', -- baixa, normal, alta, urgente
        parts_total REAL DEFAULT 0.0,
        labor_total REAL DEFAULT 0.0,
        discount REAL DEFAULT 0.0,
        total_amount REAL DEFAULT 0.0,
        warranty_days INTEGER DEFAULT 90,
        items_json TEXT DEFAULT '[]',
        billed INTEGER DEFAULT 0,
        opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
        closed_at TEXT
    );
    """)

    # 15. Notas Fiscais Emitidas (NF-e 55, NFC-e 65, NFS-e)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model TEXT NOT NULL, -- NFe-55, NFCe-65, NFSe
        series INTEGER DEFAULT 1,
        number INTEGER NOT NULL,
        access_key TEXT NOT NULL,
        protocol TEXT DEFAULT '',
        status TEXT DEFAULT 'autorizada', -- autorizada, homologacao, cancelada, rejeitada
        environment TEXT DEFAULT 'homologacao',
        nature_operation TEXT DEFAULT 'VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS',
        sale_id INTEGER,
        contact_id INTEGER,
        recipient_name TEXT NOT NULL,
        recipient_doc TEXT NOT NULL,
        recipient_uf TEXT DEFAULT 'MT',
        total_products REAL DEFAULT 0.0,
        total_discounts REAL DEFAULT 0.0,
        total_shipping REAL DEFAULT 0.0,
        total_icms REAL DEFAULT 0.0,
        total_pis REAL DEFAULT 0.0,
        total_cofins REAL DEFAULT 0.0,
        total_iss REAL DEFAULT 0.0,
        total_invoice REAL NOT NULL,
        items_json TEXT DEFAULT '[]',
        xml_content TEXT DEFAULT '',
        correction_letter TEXT DEFAULT '',
        cancel_reason TEXT DEFAULT '',
        issued_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 16. Compras Importadas via XML de Fornecedor
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xml_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        access_key TEXT NOT NULL,
        invoice_number TEXT NOT NULL,
        supplier_cnpj TEXT NOT NULL,
        supplier_name TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        total_amount REAL NOT NULL,
        items_count INTEGER DEFAULT 0,
        installments_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 18. Usuários do Sistema & Permissões
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'admin', -- admin, financeiro, vendas, fiscal, operador
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    );
    """)

    # 19. Auditoria de Alterações
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER DEFAULT 1,
        user_id INTEGER,
        action TEXT NOT NULL, -- create, update, delete, pay, cancel, approve
        entity TEXT NOT NULL, -- financial_entries, sales, invoices, etc.
        entity_id INTEGER,
        old_data TEXT,
        new_data TEXT,
        ip_address TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    migrate_db(conn)

    # Seed Admin User se não existir
    admin_exists = cur.execute("SELECT id FROM users WHERE email = 'admin@cortex.com.br'").fetchone()
    if not admin_exists:
        try:
            import bcrypt
            pwd_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        except Exception:
            import hashlib
            pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()

        cur.execute("""
            INSERT INTO users (company_id, name, email, password_hash, role)
            VALUES (1, 'Administrador Cortex', 'admin@cortex.com.br', ?, 'admin')
        """, (pwd_hash,))
        conn.commit()

    seed_initial_data(conn)
    conn.close()


def migrate_db(conn: sqlite3.Connection) -> None:
    """Migração automática para suporte multiempresa (company_id em todas as tabelas)."""
    cur = conn.cursor()
    tables = [
        "financial_entries",
        "products",
        "contacts",
        "categories",
        "cost_centers",
        "sales",
        "crm_deals",
        "service_orders",
        "recurring_contracts",
        "invoices",
        "ofx_transactions",
        "xml_purchases",
    ]
    for tbl in tables:
        try:
            cols = [c["name"] for c in cur.execute(f"PRAGMA table_info({tbl})").fetchall()]
            if "company_id" not in cols:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN company_id INTEGER DEFAULT 1")
        except Exception:
            pass
    conn.commit()


def recalculate_bank_balances(conn: sqlite3.Connection) -> None:
    """Recalcula o saldo atual de todas as contas bancárias com base no saldo inicial + todas as baixas efetivadas."""
    cur = conn.cursor()
    accounts = cur.execute("SELECT id, initial_balance FROM bank_accounts").fetchall()
    for acc in accounts:
        acc_id = acc["id"]
        init_bal = float(acc["initial_balance"] or 0.0)
        # Soma receitas baixadas e subtrai despesas baixadas nesta conta
        rows = cur.execute("""
            SELECT p.total_cash_flow, e.type
            FROM financial_payments p
            JOIN financial_entries e ON e.id = p.entry_id
            WHERE p.bank_account_id = ?
        """, (acc_id,)).fetchall()
        delta = 0.0
        for r in rows:
            if r["type"] == "receita":
                delta += float(r["total_cash_flow"])
            elif r["type"] == "despesa":
                delta -= float(r["total_cash_flow"])
        new_bal = round(init_bal + delta, 2)
        cur.execute("UPDATE bank_accounts SET current_balance = ? WHERE id = ?", (new_bal, acc_id))
    conn.commit()


def seed_initial_data(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    if count > 0:
        return

    today = date.today()
    d_str = lambda delta: (today + timedelta(days=delta)).isoformat()

    # 1. Empresa Padrão
    cur.execute("""
        INSERT INTO companies (
            razao_social, nome_fantasia, cnpj, inscricao_estadual, inscricao_municipal,
            regime_tributario, cnae_principal, aliquota_simples, cep, logradouro, numero,
            bairro, cidade, uf, codigo_ibge_uf, codigo_ibge_municipio, telefone, email,
            chave_pix, ambiente_fiscal, motor_fiscal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "CORTEX TECNOLOGIA E GESTAO EMPRESARIAL LTDA",
        "Cortex ERP Solutions",
        "45.123.789/0001-90",
        "13.849.201-5",
        "984120",
        "simples_nacional",
        "6201-5/01",
        6.0,
        "78200-000",
        "Avenida Sete de Setembro",
        "1250",
        "Centro",
        "Cáceres",
        "MT",
        "51",
        "5102504",
        "(65) 99988-7766",
        "financeiro@cortexerp.com.br",
        "45.123.789/0001-90",
        "homologacao",
        "sefaz_direto"
    ))

    # 2. Contas Bancárias
    banks = [
        ("Banco Inter PJ", "077", "Banco Inter", "0001", "984512-3", "corrente", 28500.00, "#ea580c"),
        ("Banco Itaú Empresas", "341", "Itaú Unibanco", "4312", "44510-9", "corrente", 14200.00, "#2563eb"),
        ("Cora Sociedade de Crédito", "403", "Banco Cora", "0001", "112098-1", "corrente", 6800.00, "#db2777"),
        ("Caixa Físico (Tesouraria)", "000", "Caixa Interno", "-", "-", "caixa", 1500.00, "#16a34a"),
        ("Reserva CDI Liquidez Diária", "077", "Inter Invest", "0001", "984512-INV", "investimento", 45000.00, "#7c3aed"),
    ]
    for b in banks:
        cur.execute("""
            INSERT INTO bank_accounts (name, bank_code, bank_name, agency, account_number, account_type, initial_balance, current_balance, color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[6], b[7]))

    # 3. Plano de Contas Completo (Padrão Conta Azul + DRE Gerencial)
    categories = [
        ("1.01", "Venda de Produtos (Mercadorias)", "receita", "receita_bruta", "venda,mercadoria,produto,pdv,loja"),
        ("1.02", "Prestação de Serviços / Consultoria", "receita", "receita_bruta", "servico,consultoria,manutencao,os,mensalidade,contrato"),
        ("1.03", "Receitas de Assinaturas / Recorrência SaaS", "receita", "receita_bruta", "assinatura,recorrencia,plano,licenca"),
        ("1.04", "Rendimentos de Aplicações Financeiras", "receita", "receitas_financeiras", "rendimento,cdi,juros ativo,aplicacao"),
        ("2.01", "DAS - Simples Nacional / Impostos s/ Vendas", "despesa", "deducoes_impostos", "das,simples nacional,iss,icms,pis,cofins,darf"),
        ("3.01", "Compra de Mercadorias para Revenda (CMV)", "despesa", "custos_mercadorias_servicos", "fornecedor,mercadoria,estoque,compra,nfe,insumo"),
        ("3.02", "Fretes e Transportes sobre Compras/Vendas", "despesa", "custos_mercadorias_servicos", "frete,transportadora,correios,jadlog,logistica"),
        ("4.01", "Salários, Pró-Labore e Folha de Pagamento", "despesa", "despesas_pessoal", "salario,folha,pro-labore,adiantamento,funcionario"),
        ("4.02", "FGTS, INSS e Encargos Trabalhistas", "despesa", "despesas_pessoal", "fgts,inss,encargos,vale transporte,alimentacao"),
        ("5.01", "Aluguel, Condomínio e IPTU", "despesa", "despesas_operacionais", "aluguel,condominio,iptu,imobiliaria"),
        ("5.02", "Energia Elétrica, Água e Saneamento", "despesa", "despesas_operacionais", "energia,luz,energisa,cemig,agua,sanecap"),
        ("5.03", "Internet, Telefonia e Servidores Cloud / SaaS", "despesa", "despesas_operacionais", "internet,vivo,claro,aws,google cloud,software,dominio"),
        ("5.04", "Honorários Contábeis e Jurídicos", "despesa", "despesas_operacionais", "contabilidade,contador,advogado,juridico"),
        ("5.05", "Combustível, Pedágio e Manutenção Veicular", "despesa", "despesas_operacionais", "posto,combustivel,gasolina,diesel,uber,99,oficina"),
        ("6.01", "Marketing, Tráfego Pago (Meta/Google Ads) e Comissões", "despesa", "despesas_comerciais", "marketing,google ads,facebook ads,meta,comissao,publicidade"),
        ("7.01", "Tarifas Bancárias, IOF, Taxas de Boleto/Maquininha", "despesa", "despesas_financeiras", "tarifa,taxa bancaria,iof,manutencao conta,juros"),
        ("8.01", "Aquisição de Equipamentos, Computadores e Móveis", "despesa", "investimentos", "computador,notebook,movel, Reforma,maquina,investimento"),
        ("9.01", "Transferência entre Contas", "despesa", "transferencia", "transferencia"),
    ]
    for c in categories:
        cur.execute("""
            INSERT INTO categories (code, name, type, dre_group, keywords)
            VALUES (?, ?, ?, ?, ?)
        """, c)

    # 4. Centros de Custo
    cost_centers = [
        ("CC-01", "Administrativo & Financeiro", 8500.00),
        ("CC-02", "Comercial, Vendas & Marketing", 6000.00),
        ("CC-03", "Operações, Suporte & Assistência Técnica", 12000.00),
        ("CC-04", "Logística & Estoque", 5000.00),
    ]
    for cc in cost_centers:
        cur.execute("INSERT INTO cost_centers (code, name, monthly_budget) VALUES (?, ?, ?)", cc)

    # 5. Contatos (Clientes, Fornecedores e Transportadoras)
    contacts = [
        ("cliente", "PJ", "AGROPECUARIA PANTANAL FORTE LTDA", "Pantanal Forte Agro", "12.456.789/0001-10", "1", "13.550.112-0", "", "compras@pantanalforte.com.br", "(65) 3223-1000", "5565999112233", "78200-000", "Av. Getúlio Vargas", "890", "Sala 02", "Centro", "Cáceres", "MT", "5102504", 50000.0),
        ("cliente", "PJ", "SUPERMERCADO CENTRAL DO VALE LTDA", "Supermercado Central", "23.987.654/0001-55", "1", "13.998.221-8", "", "financeiro@supercentral.com.br", "(65) 3222-4500", "5565999445566", "78005-000", "Av. Fernando Corrêa da Costa", "2100", "", "Boa Esperança", "Cuiabá", "MT", "5103403", 35000.0),
        ("cliente", "PF", "CARLOS EDUARDO MENDES", "Dr. Carlos Mendes", "412.889.301-20", "9", "", "", "carlos.mendes@email.com.br", "(65) 99812-3344", "5565998123344", "78200-000", "Rua Comandante Balduíno", "415", "", "Centro", "Cáceres", "MT", "5102504", 10000.0),
        ("fornecedor", "PJ", "DISTRIBUIDORA NACIONAL DE HARDWARE E TI S.A.", "Nacional Tech Distribuidora", "08.777.123/0001-88", "1", "110.445.998.112", "", "faturamento@nacionaltech.com.br", "(11) 4002-8922", "5511988776655", "01310-100", "Av. Paulista", "1578", "10º Andar", "Bela Vista", "São Paulo", "SP", "3550308", 0.0),
        ("fornecedor", "PJ", "ENERGISA MATO GROSSO - DISTRIBUIDORA DE ENERGIA S.A.", "Energisa MT", "03.467.321/0001-99", "1", "13.188.001-1", "", "atendimento@energisa.com.br", "0800 646 4196", "", "78000-000", "Rua Vereador João Barbosa Caramuru", "184", "", "Bandeirantes", "Cuiabá", "MT", "5103403", 0.0),
        ("transportadora", "PJ", "EXPRESSO RODOVIARIO CENTRO OESTE LTDA", "Expresso Centro Oeste", "19.222.333/0001-44", "1", "13.700.400-2", "", "coletas@expressoco.com.br", "(65) 3661-9000", "5565996001122", "78098-000", "Rodovia BR-364", "KM 12", "Galpão 4", "Distrito Industrial", "Cuiabá", "MT", "5103403", 0.0),
    ]
    for ct in contacts:
        cur.execute("""
            INSERT INTO contacts (
                type, person_type, name, trade_name, document, ie_indicator, state_registration,
                municipal_registration, email, phone, whatsapp, cep, street, number, complement,
                neighborhood, city, state, ibge_code, credit_limit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ct)

    # 6. Produtos e Serviços com Ficha Fiscal completa
    products = [
        ("produto", "PRD-001", "7891234560012", "Notebook Corporativo Intel Core i7 16GB SSD 512GB", "Informática", "UN", 3100.00, 3100.00, 45.0, 4495.00, 12.0, 3.0, "84713012", "2103100", "0", "5102", "6102", "102", 0.0, "07", 0.65, "07", 3.0, "01.07", 0.0),
        ("produto", "PRD-002", "7891234560029", "Monitor Profissional 27\" IPS 4K Ultra HD", "Periféricos", "UN", 1150.00, 1150.00, 46.9, 1690.00, 18.0, 5.0, "85285220", "2106800", "0", "5102", "6102", "102", 0.0, "07", 0.65, "07", 3.0, "01.07", 0.0),
        ("produto", "PRD-003", "7891234560036", "Leitor de Código de Barras Laser Sem Fio USB", "Automação Comercial", "UN", 140.00, 140.00, 77.8, 249.00, 25.0, 5.0, "84719012", "", "0", "5102", "6102", "102", 0.0, "07", 0.65, "07", 3.0, "01.07", 0.0),
        ("produto", "PRD-004", "7891234560043", "Impressora Térmica Não Fiscal Cupom/DANFE 80mm", "Automação Comercial", "UN", 420.00, 420.00, 64.2, 690.00, 4.0, 5.0, "84433239", "", "0", "5102", "6102", "102", 0.0, "07", 0.65, "07", 3.0, "01.07", 0.0),
        ("produto", "PRD-005", "7891234560050", "Nobreak Senoidal 1500VA Bivolt Automático", "Energia & Redes", "UN", 780.00, 780.00, 52.5, 1190.00, 9.0, 3.0, "85044040", "", "0", "5102", "6102", "500", 0.0, "07", 0.65, "07", 3.0, "01.07", 0.0),
        ("servico", "SRV-001", "", "Implantação e Treinamento de Sistema ERP Completo", "Consultoria TI", "SV", 0.00, 0.00, 100.0, 2500.00, 0.0, 0.0, "00000000", "", "0", "5933", "6933", "102", 0.0, "07", 0.65, "07", 3.0, "01.07", 3.0),
        ("servico", "SRV-002", "", "Mensalidade Suporte Técnico e Monitoramento Cloud", "Recorrência", "SV", 0.00, 0.00, 100.0, 890.00, 0.0, 0.0, "00000000", "", "0", "5933", "6933", "102", 0.0, "07", 0.65, "07", 3.0, "01.07", 3.0),
        ("servico", "SRV-003", "", "Manutenção Preventiva e Corretiva de Servidor/Estação", "Assistência Técnica", "HR", 0.00, 0.00, 100.0, 220.00, 0.0, 0.0, "00000000", "", "0", "5933", "6933", "102", 0.0, "07", 0.65, "07", 3.0, "14.01", 3.0),
    ]
    for p in products:
        cur.execute("""
            INSERT INTO products (
                type, sku, barcode, name, category_name, unit, cost_price, average_cost,
                margin_percent, sale_price, stock_qty, min_stock, ncm, cest, origin,
                cfop_internal, cfop_external, csosn_cst, icms_rate, pis_cst, pis_rate,
                cofins_cst, cofins_rate, service_code_lc116, iss_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, p)

    # 7. Venda inicial e Nota Fiscal Autorizada de exemplo
    cur.execute("""
        INSERT INTO sales (number, sale_type, status, contact_id, seller_name, sale_date, subtotal, discount_amount, shipping_amount, total_amount, payment_method, installments, bank_account_id, notes)
        VALUES (1001, 'venda', 'faturada', 1, 'Willian Cardoso', ?, 6185.00, 85.00, 0.00, 6100.00, 'Pix', 2, 1, 'Venda corporativa com entrega imediata')
    """, (d_str(-5),))
    sale_id = cur.lastrowid
    cur.execute("""
        INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
        VALUES (?, 1, 'Notebook Corporativo Intel Core i7 16GB SSD 512GB', 'PRD-001', 'UN', 1, 4495.00, 50.00, 4445.00)
    """, (sale_id,))
    cur.execute("""
        INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
        VALUES (?, 2, 'Monitor Profissional 27\" IPS 4K Ultra HD', 'PRD-002', 'UN', 1, 1690.00, 35.00, 1655.00)
    """, (sale_id,))

    # Orçamento de exemplo (pronto para aprovar em 1 clique)
    cur.execute("""
        INSERT INTO sales (number, sale_type, status, contact_id, seller_name, sale_date, valid_until, subtotal, discount_amount, shipping_amount, total_amount, payment_method, installments, bank_account_id, notes)
        VALUES (1002, 'orcamento', 'enviado', 2, 'Willian Cardoso', ?, ?, 3880.00, 0.00, 90.00, 3970.00, 'Boleto', 3, 2, 'Proposta de modernização de frente de caixa')
    """, (d_str(-1), d_str(7)))
    orc_id = cur.lastrowid
    cur.execute("""
        INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
        VALUES (?, 4, 'Impressora Térmica Não Fiscal Cupom/DANFE 80mm', 'PRD-004', 'UN', 2, 690.00, 0.00, 1380.00)
    """, (orc_id,))
    cur.execute("""
        INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
        VALUES (?, 6, 'Implantação e Treinamento de Sistema ERP Completo', 'SRV-001', 'SV', 1, 2500.00, 0.00, 2500.00)
    """, (orc_id,))

    # 8. Lançamentos Financeiros (Receitas e Despesas: Pagos, Parciais, Vencendo Hoje, Vencidos e A Vencer)
    entries = [
        # Receita 1/2 já paga da Venda 1001
        ("receita", "Venda #1001 (Parcela 1/2) - Pantanal Forte Agro", 1, 1, 2, 1, "Pix", d_str(-5), d_str(-5), 3050.00, 0.0, 0.0, 0.0, 3050.00, "pago", 1, 2, "VND-1001", "unico", "NF-100", "venda", sale_id),
        # Receita 2/2 a vencer da Venda 1001
        ("receita", "Venda #1001 (Parcela 2/2) - Pantanal Forte Agro", 1, 1, 2, 1, "Boleto", d_str(-5), d_str(25), 3050.00, 0.0, 0.0, 0.0, 0.00, "pendente", 2, 2, "VND-1001", "unico", "NF-100", "venda", sale_id),
        # Receita de consultoria já recebida
        ("receita", "Implantação ERP & Consultoria - Supermercado Central", 2, 2, 3, 2, "Pix", d_str(-12), d_str(-10), 4800.00, 0.0, 0.0, 0.0, 4800.00, "pago", 1, 1, "SRV-50", "unico", "NFSE-200", "manual", None),
        # Receita com baixa parcial (Cliente pagou metade!)
        ("receita", "Contrato Suporte & Cloud Mensal - Supermercado Central", 2, 3, 3, 1, "Boleto", d_str(-3), d_str(0), 1780.00, 0.0, 0.0, 0.0, 890.00, "parcial", 1, 1, "CTR-01", "mensal", "BOL-8891", "contrato", 1),
        # Receita Vencida (para demonstrar régua de cobrança WhatsApp e cálculo de juros)
        ("receita", "Manutenção de Estações e Rede - Dr. Carlos Mendes", 3, 2, 3, 1, "Pix", d_str(-8), d_str(-4), 960.00, 0.0, 0.0, 0.0, 0.00, "pendente", 1, 1, "OS-901", "unico", "OS-901", "os", 1),
        # Despesas pagas e a pagar
        ("despesa", "Compra de Lote Notebooks e Monitores - Nacional Tech", 4, 6, 4, 1, "Boleto", d_str(-14), d_str(-10), 5400.00, 0.0, 0.0, 0.0, 5400.00, "pago", 1, 2, "CMP-77", "unico", "NFE-44910", "manual", None),
        ("despesa", "Compra de Lote Notebooks (Parcela 2/2) - Nacional Tech", 4, 6, 4, 1, "Boleto", d_str(-14), d_str(15), 5400.00, 0.0, 0.0, 0.0, 0.00, "pendente", 2, 2, "CMP-77", "unico", "NFE-44910", "manual", None),
        ("despesa", "Fatura Energia Elétrica Matriz - Energisa MT", 5, 11, 1, 2, "Boleto", d_str(-2), d_str(0), 645.90, 0.0, 0.0, 0.0, 0.00, "pendente", 1, 1, "ENE-10", "mensal", "FAT-00921", "manual", None),
        ("despesa", "Aluguel Sede Comercial & Galpão", None, 10, 1, 1, "Transferência/TED", d_str(-9), d_str(-5), 3200.00, 0.0, 0.0, 0.0, 3200.00, "pago", 1, 1, "ALU-10", "mensal", "REC-10", "manual", None),
        ("despesa", "Servidores Cloud AWS & Links Fibra Dedicada", None, 12, 3, 3, "Cartão de Crédito", d_str(-4), d_str(5), 890.00, 0.0, 0.0, 0.0, 0.00, "pendente", 1, 1, "CLD-10", "mensal", "INV-AWS", "manual", None),
        ("despesa", "DAS Simples Nacional Competência Anterior", None, 5, 1, 1, "Pix", d_str(-7), d_str(2), 1120.50, 0.0, 0.0, 0.0, 0.00, "pendente", 1, 1, "DAS-10", "mensal", "DAS-2026", "manual", None),
    ]
    for e in entries:
        cur.execute("""
            INSERT INTO financial_entries (
                type, description, contact_id, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, interest, fine, discount,
                paid_amount, status, installment_number, installment_total, group_uid,
                recurrence, document_number, origin_type, origin_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, e)
        entry_id = cur.lastrowid
        if e[13] > 0:
            cur.execute("""
                INSERT INTO financial_payments (
                    entry_id, bank_account_id, payment_date, principal_paid, interest_paid,
                    fine_paid, discount_applied, total_cash_flow, payment_method, notes
                ) VALUES (?, ?, ?, ?, 0.0, 0.0, 0.0, ?, ?, 'Baixa registrada')
            """, (entry_id, e[5], e[8], e[13], e[13], e[6]))

    # 9. CRM Funil de Vendas (Kanban)
    deals = [
        ("Implantação ERP + 5 Terminais PDV", 2, "Supermercado Central", "proposta", 14500.00, 75, d_str(7), "Willian Cardoso", "quente", "Cliente aprovou escopo técnico, aguardando assinatura da diretoria."),
        ("Renovação Parque de Notebooks (8 un.)", 1, "Pantanal Forte Agro", "negociacao", 35960.00, 85, d_str(5), "Willian Cardoso", "quente", "Negociando desconto de 4% para pagamento à vista no Pix."),
        ("Contrato Anual de Suporte & Backup Cloud", 3, "Dr. Carlos Mendes", "qualificacao", 10680.00, 60, d_str(14), "Consultor Comercial", "morno", "Levantamento de servidores concluído."),
        ("Automação de Estoque c/ Coletores Sem Fio", None, "Distribuidora São Lucas", "prospeccao", 8900.00, 40, d_str(20), "Consultor Comercial", "frio", "Primeiro contato realizado via WhatsApp."),
    ]
    for d in deals:
        cur.execute("""
            INSERT INTO crm_deals (title, contact_id, contact_name, stage, estimated_value, probability, expected_close_date, responsible, temperature, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, d)

    # 10. Contratos Recorrentes
    cur.execute("""
        INSERT INTO recurring_contracts (title, contact_id, product_id, monthly_value, due_day, payment_method, bank_account_id, category_id, auto_emit_nfse, status, start_date, notes)
        VALUES ('Contrato Mensal Suporte TI & Nuvem Corporativa', 1, 7, 1490.00, 10, 'Pix', 1, 3, 1, 'ativo', ?, 'Reajuste anual pelo IPCA')
    """, (d_str(-90),))
    cur.execute("""
        INSERT INTO recurring_contracts (title, contact_id, product_id, monthly_value, due_day, payment_method, bank_account_id, category_id, auto_emit_nfse, status, start_date, notes)
        VALUES ('Licenciamento Cortex ERP + Monitoramento Banco de Dados', 2, 7, 890.00, 15, 'Boleto', 2, 3, 1, 'ativo', ?, 'Inclui atendimento prioritário SLA 2h')
    """, (d_str(-60),))

    # 11. Ordens de Serviço (OS)
    os_items = json.dumps([
        {"type": "produto", "product_id": 5, "name": "Nobreak Senoidal 1500VA Bivolt Automático", "qty": 1, "unit_price": 1190.0, "total": 1190.0},
        {"type": "servico", "product_id": 8, "name": "Manutenção Preventiva e Corretiva de Servidor/Estação", "qty": 2, "unit_price": 220.0, "total": 440.0}
    ], ensure_ascii=False)
    cur.execute("""
        INSERT INTO service_orders (
            os_number, contact_id, equipment, brand_model, serial_number, reported_defect,
            technical_report, technician, status, priority, parts_total, labor_total,
            discount, total_amount, warranty_days, items_json, billed
        ) VALUES (901, 1, 'Servidor Dell PowerEdge T150 + Rack', 'Dell T150 Xeon', 'SN-9948120-BR',
            'Desligamento abrupto durante queda de tensão na fazenda/escritório.',
            'Substituição do Nobreak por modelo Senoidal Puro 1500VA e revisão completa da fonte redundante e RAID.',
            'Eng. Willian', 'em_execucao', 'alta', 1190.00, 440.00, 0.00, 1630.00, 90, ?, 0)
    """, (os_items,))

    recalculate_bank_balances(conn)
    conn.commit()

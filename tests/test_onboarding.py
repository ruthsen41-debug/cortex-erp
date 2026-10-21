import uuid
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_register_new_company_success():
    """Testa o onboarding completo de uma nova empresa e seu administrador."""
    payload = {
        "company_name": "Padaria & Confeitaria Estrela do Sul",
        "admin_name": "Maria da Silva",
        "email": f"maria_{uuid.uuid4().hex[:8]}@padariaestrela.com.br",
        "password": "senhaSegura123",
        "cnpj": "12.345.678/0001-99",
        "phone": "(11) 98888-7777",
        "city": "Campinas",
        "state": "SP",
    }
    res = client.post("/api/auth/register-company", json=payload)
    assert res.status_code == 200, f"Falha no onboarding: {res.text}"
    data = res.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["name"] == "Maria da Silva"
    assert data["user"]["email"] == payload["email"]
    assert data["user"]["role"] == "admin"
    assert data["company"]["name"] == "Padaria & Confeitaria Estrela do Sul"
    new_company_id = data["company"]["id"]
    assert new_company_id > 1

    # Valida que o token retornado ja permite autenticar no /api/auth/me
    token = data["access_token"]
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == payload["email"]
    assert me_data["company_id"] == new_company_id


def test_register_company_duplicate_email():
    """Nao permite cadastrar uma segunda empresa com o mesmo e-mail de administrador."""
    email = f"admin_duplicado_{uuid.uuid4().hex[:8]}@cortex.com.br"
    payload = {
        "company_name": "Empresa Alfa",
        "admin_name": "Carlos",
        "email": email,
        "password": "senhaSegura123",
    }
    res1 = client.post("/api/auth/register-company", json=payload)
    assert res1.status_code == 200

    payload2 = {
        "company_name": "Empresa Beta",
        "admin_name": "Carlos Outro",
        "email": email,
        "password": "outraSenha123",
    }
    res2 = client.post("/api/auth/register-company", json=payload2)
    assert res2.status_code == 400
    assert "já está cadastrado" in res2.text


def test_register_company_validation_rules():
    """Valida requisitos minimos de nome, email e tamanho de senha."""
    # Senha curta (< 6 caracteres)
    res_short = client.post("/api/auth/register-company", json={
        "company_name": "Empresa Curta",
        "admin_name": "Admin",
        "email": "curta@teste.com",
        "password": "123",
    })
    assert res_short.status_code == 400
    assert "no mínimo 6 caracteres" in res_short.text

    # Nome da empresa vazio
    res_no_name = client.post("/api/auth/register-company", json={
        "company_name": "   ",
        "admin_name": "Admin",
        "email": "sem_nome@teste.com",
        "password": "senhaValida123",
    })
    assert res_no_name.status_code == 400
    assert "nome da empresa é obrigatório" in res_no_name.text


def test_multi_tenant_data_isolation():
    """Garante que dados criados por uma empresa nao aparecem para outra empresa."""
    # 1. Cadastra Empresa A
    res_a = client.post("/api/auth/register-company", json={
        "company_name": "Tenant A Logistica",
        "admin_name": "Gestor A",
        "email": f"gestor_a_{uuid.uuid4().hex[:8]}@tenant-a.com.br",
        "password": "senhaSeguraTenantA",
    })
    assert res_a.status_code == 200
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Cadastra Empresa B
    res_b = client.post("/api/auth/register-company", json={
        "company_name": "Tenant B Comercio",
        "admin_name": "Gestor B",
        "email": f"gestor_b_{uuid.uuid4().hex[:8]}@tenant-b.com.br",
        "password": "senhaSeguraTenantB",
    })
    assert res_b.status_code == 200
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Empresa A cria um produto exclusivo
    prod_payload = {
        "name": "Serviço Exclusivo do Tenant A",
        "sku": "SERV-TENANT-A-01",
        "type": "servico",
        "cost_price": 50.0,
        "sale_price": 150.0,
        "stock_qty": 0,
    }
    create_res = client.post("/api/products", json=prod_payload, headers=headers_a)
    assert create_res.status_code == 200
    prod_a_id = create_res.json()["id"]

    # 4. Empresa B lista produtos: o produto do Tenant A NAO pode estar na listagem do Tenant B
    list_b = client.get("/api/products", headers=headers_b)
    assert list_b.status_code == 200
    items_b = list_b.json()
    b_product_ids = [p["id"] for p in items_b]
    assert prod_a_id not in b_product_ids, "Vazamento de dados entre empresas (multi-tenant fail)!"

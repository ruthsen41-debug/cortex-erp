"""Ficha completa do funcionário (padrão Domínio): campos estendidos, dependentes e S-2200."""
import sys
import uuid
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

client = TestClient(app)


def _h():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _cpf():
    import random
    n = [random.randint(0, 9) for _ in range(9)]
    for t in (9, 10):
        s = sum(n[i] * (t + 1 - i) for i in range(t))
        n.append((s * 10 % 11) % 10)
    return "".join(map(str, n))


def test_ficha_completa_dependentes_e_s2200():
    h = _h()
    cpf = _cpf()
    res = client.post("/api/dp/employees", headers=h, json={
        "name": "Maria Ficha Completa", "cpf": cpf, "admission_date": "2026-03-02",
        "role": "Analista Fiscal", "salary": 3500, "birth_date": "1990-05-10", "sexo": "F",
        "estado_civil": "2", "raca_cor": "3", "grau_instrucao": "09", "nome_mae": "Ana Ficha",
        "rg": "1234567", "rg_orgao": "SSP", "rg_uf": "MT", "ctps": "998877", "ctps_serie": "0012",
        "logradouro": "Rua das Flores", "numero": "100", "bairro": "Centro", "cidade": "Cuiabá",
        "uf": "MT", "cod_municipio": "5103403", "cep": "78000-000",
        "tipo_contrato": "experiencia", "experiencia_dias": 45, "experiencia_prorrogacao": 45,
        "sindicato_cnpj": "12.345.678/0001-90", "tipo_salario": "5", "horas_semana": 44,
        "horario_entrada": "08:00", "horario_saida": "18:00", "pix_tipo": "cpf", "pix_chave": cpf,
    })
    assert res.status_code == 201, res.text
    emp = res.json()
    eid = emp["id"]
    assert emp["nome_mae"] == "Ana Ficha" and emp["experiencia_dias"] == 45 and emp["pix_chave"] == cpf

    # Edição de campos da ficha + CPF não pode colidir com outro funcionário
    upd = client.put(f"/api/dp/employees/{eid}", headers=h, json={"cnh": "55566677788", "cnh_categoria": "B"})
    assert upd.status_code == 200 and upd.json()["cnh_categoria"] == "B"
    outro = client.post("/api/dp/employees", headers=h, json={
        "name": "Outro", "cpf": _cpf(), "admission_date": "2026-03-02", "role": "Aux", "salary": 2000}).json()
    assert client.put(f"/api/dp/employees/{outro['id']}", headers=h, json={"cpf": cpf}).status_code == 400

    # Dependentes recalculam IRRF e cotas de salário-família (filho até 14 anos)
    filho_novo = f"{date.today().year - 5}-01-15"
    filho_velho = f"{date.today().year - 17}-01-15"
    d1 = client.post(f"/api/dp/employees/{eid}/dependents", headers=h, json={
        "nome": "Pedro Filho", "data_nascimento": filho_novo, "parentesco": "03", "irrf": 1, "salario_familia": 1})
    assert d1.status_code == 201, d1.text
    client.post(f"/api/dp/employees/{eid}/dependents", headers=h, json={
        "nome": "Lucas Filho", "data_nascimento": filho_velho, "parentesco": "03", "irrf": 1, "salario_familia": 1})
    e = client.get(f"/api/dp/employees/{eid}", headers=h).json()
    assert e["dependents"] == 2 and e["filhos_sal_familia"] == 1

    deps = client.get(f"/api/dp/employees/{eid}/dependents", headers=h).json()
    assert len(deps) == 2
    client.delete(f"/api/dp/employees/{eid}/dependents/{d1.json()['id']}", headers=h)
    e = client.get(f"/api/dp/employees/{eid}", headers=h).json()
    assert e["dependents"] == 1 and e["filhos_sal_familia"] == 0

    xml = client.get(f"/api/dp/employees/{eid}/esocial/s2200", headers=h)
    assert xml.status_code == 200
    body = xml.text
    for trecho in ("<racaCor>3</racaCor>", "<estCiv>2</estCiv>", "<grauInstr>09</grauInstr>",
                   "<nrCtps>998877</nrCtps>", "<codMunic>5103403</codMunic>", "<nmDep>Lucas Filho</nmDep>",
                   "<tpContr>2</tpContr>", "<dtTerm>2026-04-15</dtTerm>", "<cnpjSindCategProf>12345678000190</cnpjSindCategProf>"):
        assert trecho in body, trecho

    # Ficha de Registro de Empregado (impressão)
    ficha = client.get(f"/api/dp/employees/{eid}/documento/ficha-registro", headers=h)
    assert ficha.status_code == 200 and ficha.headers["content-type"].startswith("text/html")
    for trecho in ("Ficha de Registro de Empregado", "Maria Ficha Completa", "Ana Ficha", "Casado(a)", "Parda",
                   "Superior completo", "02/03/2026", "R$ 3.500,00", "45 dias + 45 dias", "Lucas Filho",
                   "Rua das Flores, 100", "08:00 às 18:00"):
        assert trecho in ficha.text, trecho
    assert client.get(f"/api/dp/employees/{eid}/documento/ficha-registro").status_code == 401


def test_dependente_de_outra_empresa_bloqueado():
    h = _h()
    email = f"cli_{uuid.uuid4().hex[:8]}@teste.com.br"
    cid = client.post("/api/auth/register-company", json={
        "company_name": "Outra Ficha", "admin_name": "Dono", "email": email, "password": "senha123"}).json()["company"]["id"]
    client.post(f"/api/superadmin/companies/{cid}/approve", headers=h)
    tok = client.post("/api/auth/login", json={"email": email, "password": "senha123"}).json()["access_token"]
    h_cli = {"Authorization": f"Bearer {tok}"}
    emp = client.post("/api/dp/employees", headers=h, json={
        "name": "Func Matriz", "cpf": _cpf(), "admission_date": "2026-01-05", "role": "Aux", "salary": 2000}).json()
    assert client.get(f"/api/dp/employees/{emp['id']}/dependents", headers=h_cli).status_code == 404
    assert client.post(f"/api/dp/employees/{emp['id']}/dependents", headers=h_cli,
                       json={"nome": "Intruso"}).status_code == 404
    assert client.get(f"/api/dp/employees/{emp['id']}/documento/ficha-registro", headers=h_cli).status_code == 404

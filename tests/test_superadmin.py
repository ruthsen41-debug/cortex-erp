"""Painel do Super Administrador: aprovação/bloqueio de empresas, isolamento entre clientes,
tabelas legais globais, catálogo global de rubricas e solicitações de suporte."""
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.database import get_conn
from backend.services.payroll_tables import load_tables

client = TestClient(app)


def _login(email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _super():
    return _login("admin@cortex.com.br", "admin123")


def _novo_cliente(h_super):
    email = f"cli_{uuid.uuid4().hex[:8]}@teste.com.br"
    res = client.post("/api/auth/register-company", json={
        "company_name": "Cliente SA Teste", "admin_name": "Dono Cliente",
        "email": email, "password": "senha123",
    })
    assert res.status_code == 200, res.text
    cid = res.json()["company"]["id"]
    assert client.post(f"/api/superadmin/companies/{cid}/approve", headers=h_super).status_code == 200
    return cid, email, _login(email, "senha123")


def test_somente_superadmin_acessa_o_painel():
    h_super = _super()
    me = client.get("/api/auth/me", headers=h_super).json()
    assert me["is_superadmin"] == 1
    ov = client.get("/api/superadmin/overview", headers=h_super)
    assert ov.status_code == 200, ov.text
    assert "empresas" in ov.json()

    _, _, h_cli = _novo_cliente(h_super)
    assert client.get("/api/superadmin/overview", headers=h_cli).status_code == 403
    assert client.get("/api/superadmin/companies", headers=h_cli).status_code == 403


def test_bloqueio_derruba_sessao_e_isolamento_entre_clientes():
    h_super = _super()
    cid, email, h_cli = _novo_cliente(h_super)

    # Cliente não enxerga nem troca para a empresa principal ou de outros clientes
    lista = client.get("/api/company/list", headers=h_cli).json()["companies"]
    assert {c["id"] for c in lista} == {cid}
    assert client.post("/api/company/switch", headers=h_cli, json={"company_id": 1}).status_code == 403

    # Admin do cliente cria usuário: sempre dentro da própria empresa
    novo = client.post("/api/auth/register", headers=h_cli, json={
        "name": "Func", "email": f"f_{uuid.uuid4().hex[:6]}@t.com", "password": "senha123", "role": "dp"})
    assert novo.status_code == 200, novo.text
    assert novo.json()["company_id"] == cid

    # Bloqueio: token atual deixa de valer e login é recusado
    assert client.post(f"/api/superadmin/companies/{cid}/block", headers=h_super,
                       json={"motivo": "inadimplente"}).status_code == 200
    assert client.get("/api/auth/me", headers=h_cli).status_code == 401
    bloq = client.post("/api/auth/login", json={"email": email, "password": "senha123"})
    assert bloq.status_code == 403 and "bloqueado" in bloq.text

    assert client.post(f"/api/superadmin/companies/{cid}/reactivate", headers=h_super).status_code == 200
    assert client.get("/api/auth/me", headers=h_cli).status_code == 200

    det = client.get(f"/api/superadmin/companies/{cid}", headers=h_super).json()
    assert any(u["email"] == email for u in det["users"])


def test_tabelas_globais_valem_para_todos_e_cliente_nao_altera():
    h_super = _super()
    cid, _, h_cli = _novo_cliente(h_super)
    ano = 2031
    try:
        res = client.post("/api/superadmin/tax-tables", headers=h_super, json={
            "ano": ano, "tipo": "salario_minimo",
            "brackets": [{"faixa_de": 0, "faixa_ate": None, "aliquota": 1999.99, "deducao": 0}]})
        assert res.status_code == 201, res.text

        conn = get_conn()
        t = load_tables(conn, cid, f"{ano}-03")
        conn.close()
        assert t.salario_minimo == 1999.99
        assert t.origem["salario_minimo"] == f"global {ano}"

        # Cliente enxerga, mas não altera tabelas legais
        lst = client.get(f"/api/dp/tax-tables?ano={ano}", headers=h_cli).json()
        assert any(x["global"] and x["tipo"] == "salario_minimo" for x in lst)
        assert client.post("/api/dp/tax-tables", headers=h_cli,
                           json={"ano": ano, "tipo": "inss", "brackets": []}).status_code == 403
    finally:
        conn = get_conn()
        for r in conn.execute("SELECT id FROM tax_tables WHERE company_id = 0 AND ano = ?", (ano,)).fetchall():
            conn.execute("DELETE FROM tax_brackets WHERE tax_table_id = ?", (r[0],))
        conn.execute("DELETE FROM tax_tables WHERE company_id = 0 AND ano = ?", (ano,))
        conn.commit()
        conn.close()


def test_rubrica_global_publicada_e_protegida():
    h_super = _super()
    cid, _, h_cli = _novo_cliente(h_super)
    codigo = "G" + uuid.uuid4().hex[:4].upper()
    res = client.post("/api/superadmin/rubrics", headers=h_super, json={
        "codigo": codigo, "nome": "Gratificação Global", "tipo": "provento",
        "incide_inss": 1, "incide_irrf": 1, "incide_fgts": 1, "esocial_nat_rubrica": "1099"})
    assert res.status_code == 201, res.text
    gid = res.json()["id"]
    try:
        pub = client.post("/api/superadmin/rubrics/publish", headers=h_super, json={"company_ids": [cid]})
        assert pub.status_code == 200 and pub.json()["criadas"] >= 1

        rubs = client.get("/api/dp/rubrics", headers=h_cli).json()
        copia = next(r for r in rubs if r["codigo"] == codigo)
        assert copia["origem"] == "global"

        # Cliente não altera a rubrica do sistema, mas cria a sua
        assert client.put(f"/api/dp/rubrics/{copia['id']}", headers=h_cli, json={"nome": "X"}).status_code == 403
        assert client.post("/api/dp/rubrics", headers=h_cli,
                           json={"codigo": "P" + codigo[1:], "nome": "Própria"}).status_code == 201

        # Atualização do catálogo propaga para as cópias globais
        client.put(f"/api/superadmin/rubrics/{gid}", headers=h_super, json={"nome": "Gratificação Global v2"})
        client.post("/api/superadmin/rubrics/publish", headers=h_super,
                    json={"company_ids": [cid], "atualizar_existentes": True})
        rubs = client.get("/api/dp/rubrics", headers=h_cli).json()
        assert next(r for r in rubs if r["codigo"] == codigo)["nome"] == "Gratificação Global v2"
    finally:
        client.delete(f"/api/superadmin/rubrics/{gid}", headers=h_super)


def test_solicitacao_de_suporte_ida_e_volta():
    h_super = _super()
    cid, _, h_cli = _novo_cliente(h_super)
    res = client.post("/api/support", headers=h_cli, json={
        "categoria": "tabelas", "assunto": "Atualizar INSS 2027", "mensagem": "Saiu portaria nova."})
    assert res.status_code == 201, res.text
    rid = res.json()["id"]

    fila = client.get("/api/superadmin/support?status=aberto", headers=h_super).json()
    assert any(s["id"] == rid and s["company_id"] == cid for s in fila)

    assert client.put(f"/api/superadmin/support/{rid}", headers=h_super,
                      json={"status": "concluido", "resposta": "Tabela publicada."}).status_code == 200
    mine = client.get("/api/support", headers=h_cli).json()
    item = next(s for s in mine if s["id"] == rid)
    assert item["status"] == "concluido" and item["resposta"] == "Tabela publicada."

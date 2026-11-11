"""Testes para os módulos da Fase 12 — LALUR, Honorários, Certificados, Manifesto NF-e, CCT, DIRBI."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

client = TestClient(app)


def auth():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ── LALUR ────────────────────────────────────────────────────────────────────

def test_lalur_sugestoes():
    res = client.get("/api/lalur/sugestoes", headers=auth())
    assert res.status_code == 200
    data = res.json()
    assert "adicoes" in data and "exclusoes" in data
    assert len(data["adicoes"]) > 0


def test_lalur_lancamento_crud():
    h = auth()
    # Criar
    body = {"tipo": "adicao", "descricao": "Multas por infração de lei", "valor": 1000.0, "ano": 2026}
    res = client.post("/api/lalur/lancamentos", json=body, headers=h)
    assert res.status_code == 200
    lid = res.json()["id"]
    # Listar
    res = client.get("/api/lalur/lancamentos?ano=2026", headers=h)
    assert res.status_code == 200
    ids = [r["id"] for r in res.json()]
    assert lid in ids
    # Excluir
    res = client.delete(f"/api/lalur/lancamentos/{lid}", headers=h)
    assert res.status_code == 200


def test_lalur_apuracao():
    res = client.get("/api/lalur/apuracao?ano=2026", headers=auth())
    assert res.status_code == 200
    data = res.json()
    assert "lucro_real" in data
    assert "irpj_total" in data
    assert "total_tributos" in data


def test_lalur_parte_b():
    h = auth()
    res = client.post("/api/lalur/parte-b", json={"descricao": "Teste Parte B", "saldo_inicial": 5000.0, "ano": 2026}, headers=h)
    assert res.status_code == 200
    res = client.get("/api/lalur/parte-b?ano=2026", headers=h)
    assert res.status_code == 200


# ── HONORÁRIOS ───────────────────────────────────────────────────────────────

def test_honorarios_servicos():
    res = client.get("/api/honorarios/servicos", headers=auth())
    assert res.status_code == 200
    assert len(res.json()["servicos"]) > 0


def test_honorarios_contrato_crud():
    h = auth()
    body = {
        "client_name": "Empresa Teste Ltda",
        "cnpj_cpf": "12.345.678/0001-90",
        "regime": "simples_nacional",
        "valor_mensal": 500.0,
        "dia_vencimento": 10,
    }
    res = client.post("/api/honorarios/contratos", json=body, headers=h)
    assert res.status_code == 200
    cid = res.json()["id"]

    # Listar
    res = client.get("/api/honorarios/contratos", headers=h)
    assert res.status_code == 200
    ids = [r["id"] for r in res.json()]
    assert cid in ids

    # Update
    body["valor_mensal"] = 600.0
    res = client.put(f"/api/honorarios/contratos/{cid}", json=body, headers=h)
    assert res.status_code == 200

    # Faturar mês
    res = client.post("/api/honorarios/faturar-mes?competencia=2026-11", headers=h)
    assert res.status_code == 200
    assert res.json()["faturas_geradas"] >= 0

    # Summary
    res = client.get("/api/honorarios/summary", headers=h)
    assert res.status_code == 200
    data = res.json()
    assert "mrr" in data and "total_contratos_ativos" in data

    # Delete
    res = client.delete(f"/api/honorarios/contratos/{cid}", headers=h)
    assert res.status_code == 200


def test_honorarios_faturas_list():
    res = client.get("/api/honorarios/faturas?competencia=2026-11", headers=auth())
    assert res.status_code == 200


# ── CERTIFICADOS ─────────────────────────────────────────────────────────────

def test_certificates_list():
    res = client.get("/api/certificates", headers=auth())
    assert res.status_code == 200
    assert "certificates" in res.json()


def test_certificates_check_expiry():
    res = client.post("/api/certificates/check-expiry", headers=auth())
    assert res.status_code == 200
    assert "alerts" in res.json()


def test_certificates_generate_csr():
    res = client.get("/api/certificates/generate-csr", headers=auth())
    assert res.status_code == 200
    # Sem a lib cryptography no CI, retorna mensagem de aviso — ambos são aceitáveis
    data = res.json()
    assert "message" in data


# ── MANIFESTO NF-e ────────────────────────────────────────────────────────────

def test_nfe_manifest_list():
    res = client.get("/api/nfe-manifest/list", headers=auth())
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_nfe_manifest_summary():
    res = client.get("/api/nfe-manifest/summary", headers=auth())
    assert res.status_code == 200
    data = res.json()
    assert "total_nfe" in data


# ── CONVENÇÕES COLETIVAS ──────────────────────────────────────────────────────

def test_conventions_categorias():
    res = client.get("/api/conventions/categorias", headers=auth())
    assert res.status_code == 200
    assert len(res.json()["categorias"]) > 0


def test_conventions_crud():
    h = auth()
    body = {
        "categoria": "Comerciários",
        "sindicato_empregados": "SINDICOMERCIO SP",
        "sindicato_empregadores": "FECOMERCIO",
        "uf": "SP",
        "municipio": "São Paulo",
        "data_inicio": "2026-01-01",
        "data_fim": "2026-12-31",
        "piso_salarial": 1800.0,
        "reajuste_pct": 5.5,
        "jornada_semanal": 44,
        "intervalo_jornada_min": 60,
        "adicional_noturno_pct": 20.0,
        "adicional_hora_extra_pct": 50.0,
        "vale_refeicao_diario": 25.0,
        "vale_transporte": 1,
    }
    res = client.post("/api/conventions", json=body, headers=h)
    assert res.status_code == 200
    cid = res.json()["id"]

    # Listar
    res = client.get("/api/conventions/list", headers=h)
    assert res.status_code == 200
    ids = [r["id"] for r in res.json()]
    assert cid in ids

    # Alertas
    res = client.get(f"/api/conventions/{cid}/alertas", headers=h)
    assert res.status_code == 200
    assert "alerts" in res.json()

    # Summary
    res = client.get("/api/conventions/summary", headers=h)
    assert res.status_code == 200

    # Update
    body["piso_salarial"] = 1900.0
    res = client.put(f"/api/conventions/{cid}", json=body, headers=h)
    assert res.status_code == 200

    # Delete
    res = client.delete(f"/api/conventions/{cid}", headers=h)
    assert res.status_code == 200


# ── DIRBI ─────────────────────────────────────────────────────────────────────

def test_dirbi_beneficios_disponiveis():
    res = client.get("/api/dirbi/beneficios-disponiveis", headers=auth())
    assert res.status_code == 200
    assert "beneficios" in res.json()


def test_dirbi_lancamento_crud():
    h = auth()
    body = {
        "codigo_beneficio": "01001",
        "descricao": "SIMPLES NACIONAL — redução de alíquota",
        "competencia": "2026-11",
        "valor_beneficio": 1200.0,
        "base_calculo": 20000.0,
        "observacao": "Teste CI",
    }
    res = client.post("/api/dirbi/lancamentos", json=body, headers=h)
    assert res.status_code == 200
    lid = res.json()["id"] if "id" in res.json() else None

    # Listar
    res = client.get("/api/dirbi/lancamentos?competencia=2026-11", headers=h)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Preview
    res = client.get("/api/dirbi/preview?competencia=2026-11", headers=h)
    assert res.status_code == 200
    data = res.json()
    assert "total_beneficios_declarados" in data

    # Calendário (público)
    res = client.get("/api/dirbi/calendario?year=2026")
    assert res.status_code == 200
    assert len(res.json()["vencimentos"]) == 12

    # Delete
    if lid:
        res = client.delete(f"/api/dirbi/lancamentos/{lid}", headers=h)
        assert res.status_code == 200

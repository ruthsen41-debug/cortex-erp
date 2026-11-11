"""Testes extras para módulos da Fase 12 — Patrimônio, Simples Nacional, Auditoria, Portal Empregado."""
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


# ── PATRIMÔNIO ────────────────────────────────────────────────────────────────

def test_patrimony_asset_crud():
    h = auth()
    body = {
        "name": "Notebook Dell CI",
        "category": "equipamentos_informatica",
        "acquisition_date": "2026-01-01",
        "acquisition_value": 5000.0,
        "useful_life_months": 60,
        "residual_value": 500.0,
        "depreciation_method": "linear",
    }
    res = client.post("/api/patrimony", json=body, headers=h)
    assert res.status_code == 200
    aid = res.json()["id"]

    # Listar
    res = client.get("/api/patrimony", headers=h)
    assert res.status_code == 200
    ids = [a["id"] for a in res.json()]
    assert aid in ids

    # Resumo
    res = client.get("/api/patrimony/summary", headers=h)
    assert res.status_code == 200
    data = res.json()
    assert "total_assets" in data

    # Depreciar
    res = client.post("/api/patrimony/run-depreciation?competencia=2026-01", headers=h)
    assert res.status_code == 200

    # Histórico
    res = client.get(f"/api/patrimony/{aid}/depreciations", headers=h)
    assert res.status_code == 200

    # Delete
    res = client.delete(f"/api/patrimony/{aid}", headers=h)
    assert res.status_code == 200


# ── SIMPLES NACIONAL ──────────────────────────────────────────────────────────

def test_simples_config():
    h = auth()
    body = {"anexo": "III", "faturamento_12m": 300000.0}
    res = client.put("/api/simples/config", json=body, headers=h)
    assert res.status_code == 200

    res = client.get("/api/simples/config", headers=h)
    assert res.status_code == 200


def test_simples_das_calcular():
    h = auth()
    body = {"receita_bruta_mes": 50000.0, "rbt12": 500000.0, "anexo": "III", "competencia": "2026-11"}
    res = client.post("/api/simples/calculate-das", json=body, headers=h)
    assert res.status_code == 200
    data = res.json()
    assert "valor_das" in data
    assert data["valor_das"] > 0


def test_simples_pgdas_preview():
    res = client.get("/api/simples/pgdas-preview?competencia=2026-11", headers=auth())
    assert res.status_code == 200


def test_simples_das_history():
    res = client.get("/api/simples/history", headers=auth())
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ── AUDITORIA ─────────────────────────────────────────────────────────────────

def test_audit_log_list():
    res = client.get("/api/audit/logs", headers=auth())
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_audit_stats():
    res = client.get("/api/audit/stats", headers=auth())
    assert res.status_code == 200
    data = res.json()
    # stats retorna dict com chaves variadas
    assert isinstance(data, dict)


# ── LALUR extra ───────────────────────────────────────────────────────────────

def test_lalur_exclusao_lancamento():
    h = auth()
    body = {
        "tipo": "exclusao",
        "descricao": "Resultado positivo de equivalência patrimonial",
        "valor": 2000.0,
        "ano": 2026,
        "trimestre": 1,
    }
    res = client.post("/api/lalur/lancamentos", json=body, headers=h)
    assert res.status_code == 200
    lid = res.json()["id"]

    # Filtrar por tipo
    res = client.get("/api/lalur/lancamentos?ano=2026&tipo=exclusao", headers=h)
    assert res.status_code == 200
    tipos = [r["tipo"] for r in res.json()]
    assert all(t == "exclusao" for t in tipos)

    # Excluir
    res = client.delete(f"/api/lalur/lancamentos/{lid}", headers=h)
    assert res.status_code == 200


# ── DIRBI extra ───────────────────────────────────────────────────────────────

def test_dirbi_calendario():
    res = client.get("/api/dirbi/calendario?year=2026")
    assert res.status_code == 200
    data = res.json()
    assert data["ano"] == 2026
    assert len(data["vencimentos"]) == 12
    # Dezembro competencia vence em janeiro do ano seguinte
    dez = next(v for v in data["vencimentos"] if v["competencia"] == "2026-12")
    assert dez["vencimento"].startswith("2027-01")


# ── CONVENÇÕES extra ──────────────────────────────────────────────────────────

def test_conventions_summary_empty():
    res = client.get("/api/conventions/summary", headers=auth())
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "vigentes" in data
    assert "vencidas" in data

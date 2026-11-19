"""Atualização com chave de licença (servidor Cloudflare) e Painel do Sistema > Licenças."""
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.routers import atualizacao as atu
from backend.routers import licencas as lic
from backend.version import APP_VERSION

client = TestClient(app)
CHAVE = "CTX-AB2C-D3EF-G4HJ"


def _super():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


class _Resp(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_erro(url, codigo, corpo):
    return urllib.error.HTTPError(url, codigo, "x", {}, io.BytesIO(json.dumps(corpo).encode()))


@pytest.fixture
def instalado(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_RAIZ_INSTALACAO", str(tmp_path))
    monkeypatch.delenv("CORTEX_UPDATE_URL", raising=False)
    monkeypatch.delenv("CORTEX_LICENCA", raising=False)
    monkeypatch.setenv("CORTEX_ATUALIZACOES_URL", "https://atu.exemplo/")
    monkeypatch.setattr(atu, "_ultima_verificacao", {})
    return tmp_path


def test_sem_chave_pede_a_licenca(instalado):
    v = atu.verificar()
    assert v["ok"] is False and "chave de licença" in v["erro"]


def test_verifica_com_chave_e_manda_versao_e_instalacao(instalado, monkeypatch):
    enviados = []

    def urlopen(req, timeout=0):
        enviados.append((req.full_url, req.get_method(), json.loads(req.data)))
        return _Resp(json.dumps({
            "versao": "99.1.0", "sha256": "ABCD", "tamanho": 10, "notas": "PLR",
            "url": "https://atu.exemplo/v1/baixar/99.1.0?k=x&exp=1&sig=y",
            "licenca": {"cliente": "Escritório X", "expira_em": None},
        }).encode())

    monkeypatch.setattr(atu.urllib.request, "urlopen", urlopen)
    atu.gravar_config(licenca=CHAVE)
    v = atu.verificar()
    assert v["ok"] is True, v
    d = v["disponivel"]
    assert d["versao"] == "99.1.0" and d["nova"] is True and d["sha256"] == "abcd"
    assert d["url"].startswith("https://atu.exemplo/v1/baixar/")
    url, metodo, corpo = enviados[0]
    assert url == "https://atu.exemplo/v1/verificar" and metodo == "POST"
    assert corpo["chave"] == CHAVE and corpo["versao_atual"] == APP_VERSION
    # a instalação ganha um id fixo, o mesmo nas próximas verificações
    assert len(corpo["instalacao"]) == 32
    atu.verificar()
    assert enviados[1][2]["instalacao"] == corpo["instalacao"]


def test_licenca_suspensa_mostra_a_mensagem_do_servidor(instalado, monkeypatch):
    def urlopen(req, timeout=0):
        raise _http_erro(req.full_url, 403, {"erro": "Licença suspensa: as atualizações estão bloqueadas."})

    monkeypatch.setattr(atu.urllib.request, "urlopen", urlopen)
    atu.gravar_config(licenca=CHAVE)
    v = atu.verificar()
    assert v["ok"] is False and v["erro"].startswith("Licença suspensa")


def test_chave_pelo_env_quando_nao_digitada(instalado, monkeypatch):
    monkeypatch.setenv("CORTEX_LICENCA", CHAVE.lower())
    assert atu.chave_licenca() == CHAVE


def test_rota_grava_chave_valida_e_recusa_invalida(instalado, monkeypatch):
    h = _super()
    monkeypatch.setattr(atu, "verificar", lambda: {"ok": True, "disponivel": {"versao": APP_VERSION, "nova": False}})
    r = client.put("/api/system/update/licenca", headers=h, json={"chave": "abc"})
    assert r.status_code == 400

    r = client.put("/api/system/update/licenca", headers=h, json={"chave": " ctx-ab2c-d3ef-g4hj "})
    assert r.status_code == 200, r.text
    assert r.json()["licenca"] == "CTX-****-****-G4HJ"
    assert atu.ler_config()["licenca"] == CHAVE
    st = client.get("/api/system/update/status", headers=h).json()
    assert st["licenca"] == "CTX-****-****-G4HJ"  # a chave inteira não volta para o navegador


def test_rota_licenca_na_nuvem_recusa(monkeypatch):
    monkeypatch.delenv("CORTEX_RAIZ_INSTALACAO", raising=False)
    r = client.put("/api/system/update/licenca", headers=_super(), json={"chave": CHAVE})
    assert r.status_code == 400


# ── Painel do Sistema > Licenças (repasse ao Worker) ─────────────────────────
def test_painel_sem_token_avisa_configuracao(monkeypatch):
    monkeypatch.delenv("CORTEX_ATUALIZACOES_ADMIN_TOKEN", raising=False)
    r = client.get("/api/superadmin/licencas", headers=_super())
    assert r.status_code == 503 and "CORTEX_ATUALIZACOES_ADMIN_TOKEN" in r.json()["detail"]


def test_painel_repassa_ao_worker_com_token(monkeypatch):
    monkeypatch.setenv("CORTEX_ATUALIZACOES_ADMIN_TOKEN", "tok-secreto")
    monkeypatch.setenv("CORTEX_ATUALIZACOES_URL", "https://atu.exemplo")
    pedidos = []

    def urlopen(req, timeout=0):
        pedidos.append((req.get_method(), req.full_url, req.get_header("Authorization"),
                        json.loads(req.data) if req.data else None))
        if req.get_method() == "POST":
            return _Resp(json.dumps({"licenca": {"chave": CHAVE, "cliente": "Escritório X"}}).encode())
        if req.get_method() == "PATCH":
            raise _http_erro(req.full_url, 404, {"erro": "Licença não encontrada."})
        return _Resp(json.dumps({"licencas": []}).encode())

    monkeypatch.setattr(lic.urllib.request, "urlopen", urlopen)
    h = _super()
    assert client.get("/api/superadmin/licencas", headers=h).json() == {"licencas": []}
    r = client.post("/api/superadmin/licencas", headers=h,
                    json={"cliente": "Escritório X", "expira_em": "2027-12-31", "lixo": 1})
    assert r.status_code == 201 and r.json()["licenca"]["chave"] == CHAVE
    r = client.patch("/api/superadmin/licencas/ctx-0000-0000-0000", headers=h, json={"ativa": False})
    assert r.status_code == 404 and r.json()["detail"] == "Licença não encontrada."

    assert pedidos[0][:3] == ("GET", "https://atu.exemplo/v1/admin/licencas", "Bearer tok-secreto")
    assert pedidos[1][3] == {"cliente": "Escritório X", "expira_em": "2027-12-31"}  # campo estranho não passa
    assert pedidos[2][1].endswith("/v1/admin/licencas/CTX-0000-0000-0000")


def test_painel_licencas_so_para_superadmin():
    assert client.get("/api/superadmin/licencas").status_code in (401, 403)

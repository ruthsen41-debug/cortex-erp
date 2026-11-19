"""Aviso de nova versão (nuvem) e atualização do servidor instalado (Windows)."""
import hashlib
import io
import json
import sys
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.routers import atualizacao as atu
from backend.version import APP_VERSION, build_id, versao_tupla

client = TestClient(app)


def _super():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


class _Ret:
    returncode, stdout, stderr = 0, "", ""


@pytest.fixture
def instalado(tmp_path, monkeypatch):
    """Simula C:\\CortexERP numa pasta temporária, sem nunca chamar o schtasks."""
    monkeypatch.setenv("CORTEX_RAIZ_INSTALACAO", str(tmp_path))
    chamadas = []
    monkeypatch.setattr(atu, "_executar", lambda args: chamadas.append(args) or _Ret())
    monkeypatch.setattr(atu, "_ultima_verificacao", {})
    return tmp_path, chamadas


# ── versão / build ───────────────────────────────────────────────────────────
def test_versao_tupla():
    assert versao_tupla("4.10.2") > versao_tupla("4.9.9")
    assert versao_tupla("v4.5") == (4, 5, 0)
    assert versao_tupla("4.5.1-pro+x") == (4, 5, 1)
    assert versao_tupla("") == (0, 0, 0)


def test_api_version_index_e_service_worker_carregam_o_build():
    b = build_id()
    r = client.get("/api/version")
    assert r.status_code == 200
    assert r.json() == {"version": APP_VERSION, "build": b}
    assert r.headers["cache-control"] == "no-store"
    assert client.get("/api/health").json()["version"] == APP_VERSION

    html = client.get("/").text
    assert f'name="cortex-build" content="{b}"' in html
    assert f"/static/updater.js?v={b}" in html
    assert '/static/updater.js"' not in html

    sw = client.get("/static/sw.js")
    assert sw.status_code == 200
    assert "javascript" in sw.headers["content-type"]
    assert "__CORTEX_BUILD__" not in sw.text and b in sw.text


# ── painel (nuvem) ───────────────────────────────────────────────────────────
def test_status_na_nuvem_e_apply_recusado(monkeypatch):
    monkeypatch.delenv("CORTEX_RAIZ_INSTALACAO", raising=False)
    h = _super()
    st = client.get("/api/system/update/status", headers=h)
    assert st.status_code == 200, st.text
    d = st.json()
    assert d["modo"] == "nuvem" and d["versao_atual"] == APP_VERSION and d["auto"] is None
    assert client.post("/api/system/update/apply", headers=h).status_code == 400
    assert client.get("/api/system/update/status").status_code in (401, 403)


def test_check_sem_internet_nao_quebra(instalado, monkeypatch):
    def falha(req, timeout=0):
        raise urllib.error.URLError("offline")
    atu.gravar_config(licenca="CTX-AAAA-BBBB-CCCC")
    monkeypatch.setattr(atu.urllib.request, "urlopen", falha)
    r = client.post("/api/system/update/check", headers=_super())
    assert r.status_code == 200
    assert r.json()["ok"] is False and "conexão" in r.json()["erro"]


def _login(email, senha="senha123"):
    res = client.post("/api/auth/login", json={"email": email, "password": senha})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_admin_da_empresa_verifica_e_usuario_comum_nao(monkeypatch):
    """Como no celular: o admin de cada empresa também vê "Verificar atualizações"."""
    import uuid
    monkeypatch.delenv("CORTEX_RAIZ_INSTALACAO", raising=False)
    h_super = _super()
    email = f"upd_{uuid.uuid4().hex[:8]}@teste.com.br"
    res = client.post("/api/auth/register-company", json={
        "company_name": "Cliente Atualização", "admin_name": "Dono", "email": email, "password": "senha123"})
    assert res.status_code == 200, res.text
    cid = res.json()["company"]["id"]
    assert client.post(f"/api/superadmin/companies/{cid}/approve", headers=h_super).status_code == 200
    h_adm = _login(email)

    assert client.get("/api/system/update/status", headers=h_adm).status_code == 200
    chk = client.post("/api/system/update/check", headers=h_adm)
    assert chk.status_code == 200, chk.text
    disp = chk.json()["disponivel"]  # nuvem: devolve o que está no ar, sem consultar o GitHub
    assert chk.json()["ok"] is True and disp["modo"] == "nuvem"
    assert disp["versao"] == APP_VERSION and disp["build"] == build_id()

    email_dp = f"dp_{uuid.uuid4().hex[:6]}@t.com"
    assert client.post("/api/auth/register", headers=h_adm, json={
        "name": "DP", "email": email_dp, "password": "senha123", "role": "dp"}).status_code == 200
    h_dp = _login(email_dp)
    assert client.get("/api/system/update/status", headers=h_dp).status_code == 403
    assert client.post("/api/system/update/check", headers=h_dp).status_code == 403


# ── leitura da versão publicada ──────────────────────────────────────────────
GH = "https://api.github.com/repos/ruthsen41-debug/cortex-erp/releases/latest"

def test_consulta_release_do_github_com_manifesto(monkeypatch):
    respostas = {
        GH: {
            "tag_name": "v99.0.0", "body": "notas da release", "published_at": "2026-11-18T10:00:00Z",
            "assets": [
                {"name": atu.NOME_SETUP, "browser_download_url": "https://x/setup.exe", "size": 123},
                {"name": atu.NOME_MANIFESTO, "browser_download_url": "https://x/manifesto.json"},
            ],
        },
        "https://x/manifesto.json": {"versao": "99.0.0", "sha256": "ABC123", "notas": "o que mudou"},
    }
    monkeypatch.setenv("CORTEX_UPDATE_URL", GH)  # modo legado (Release do GitHub)
    monkeypatch.setattr(atu, "_baixar_json", lambda url: respostas[url])
    info = atu.consultar_ultima_versao()
    assert info["versao"] == "99.0.0" and info["nova"] is True
    assert info["sha256"] == "abc123" and info["notas"] == "o que mudou"
    assert info["url"] == "https://x/setup.exe" and info["tamanho"] == 123


def test_consulta_release_sem_manifesto_usa_digest_e_sem_setup_falha(monkeypatch):
    rel = {"tag_name": "v1.0.0", "assets": [
        {"name": atu.NOME_SETUP, "browser_download_url": "u", "size": 1, "digest": "sha256:FFEE"}]}
    monkeypatch.setenv("CORTEX_UPDATE_URL", GH)
    monkeypatch.setattr(atu, "_baixar_json", lambda url: rel)
    info = atu.consultar_ultima_versao()
    assert info["sha256"] == "ffee" and info["nova"] is False

    monkeypatch.setattr(atu, "_baixar_json", lambda url: {"tag_name": "v9", "assets": []})
    with pytest.raises(ValueError):
        atu.consultar_ultima_versao()


# ── servidor instalado ───────────────────────────────────────────────────────
def test_status_e_auto_no_servidor_instalado(instalado):
    raiz, _ = instalado
    h = _super()
    d = client.get("/api/system/update/status", headers=h).json()
    assert d["modo"] == "instalado" and d["auto"] == {"auto": False, "hora": "03:00"}

    r = client.put("/api/system/update/auto", headers=h, json={"ativo": True, "hora": "02:30"})
    assert r.status_code == 200, r.text
    cfg = json.loads((raiz / "Atualizacoes" / "config.json").read_text(encoding="utf-8"))
    assert cfg["auto"] is True and cfg["hora"] == "02:30"
    ruim = client.put("/api/system/update/auto", headers=h, json={"ativo": True, "hora": "25:00"})
    assert ruim.status_code == 422


def test_recusa_sem_sha_ja_atualizado_e_em_andamento(instalado):
    with pytest.raises(HTTPException) as e:
        atu.iniciar_atualizacao({"versao": "99.0.0", "nova": True, "url": "u", "sha256": ""})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException):
        atu.iniciar_atualizacao({"versao": APP_VERSION, "nova": False, "url": "u", "sha256": "x"})

    atu.gravar_status("instalando", "instalando…")
    assert atu.em_andamento() is True
    with pytest.raises(HTTPException) as e:
        atu.iniciar_atualizacao({"versao": "99.0.0", "nova": True, "url": "u", "sha256": "x"})
    assert e.value.status_code == 409

    # trava esquecida há mais de 1 hora é liberada
    arq = atu.pasta_atualizacoes() / "status.json"
    st = json.loads(arq.read_text(encoding="utf-8"))
    st["atualizado_em"] = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
    arq.write_text(json.dumps(st), encoding="utf-8")
    assert atu.em_andamento() is False


class _Resposta(io.BytesIO):
    def __init__(self, dados):
        super().__init__(dados)
        self.headers = {"Content-Length": str(len(dados))}


def test_download_confere_sha_e_agenda_atualizador(instalado, monkeypatch):
    raiz, chamadas = instalado
    conteudo = b"MZ instalador falso" * 1000
    monkeypatch.setattr(atu.urllib.request, "urlopen", lambda req, timeout=0: _Resposta(conteudo))
    (atu.pasta_atualizacoes() / "CortexERP-Setup-0.0.1.exe").write_bytes(b"velho")

    info = {"versao": "99.0.0", "nova": True, "url": "https://x/s.exe",
            "sha256": hashlib.sha256(conteudo).hexdigest(), "tamanho": len(conteudo)}
    atu._processo_atualizacao(info, "manual")

    pasta = raiz / "Atualizacoes"
    assert atu.ler_status()["fase"] == "agendada", atu.ler_status()
    assert (pasta / "CortexERP-Setup-99.0.0.exe").read_bytes() == conteudo
    assert not (pasta / "CortexERP-Setup-0.0.1.exe").exists()
    plano = json.loads((pasta / "plano.json").read_text(encoding="utf-8"))
    assert plano["versao"] == "99.0.0" and plano["versao_anterior"] == APP_VERSION
    assert [c[1] for c in chamadas] == ["/Create", "/Run"]
    assert "SYSTEM" in chamadas[0] and str(raiz / "atualizador.ps1") in chamadas[0][-1]


def test_download_com_sha_errado_nao_instala(instalado, monkeypatch):
    raiz, chamadas = instalado
    monkeypatch.setattr(atu.urllib.request, "urlopen", lambda req, timeout=0: _Resposta(b"adulterado"))
    atu._processo_atualizacao({"versao": "99.0.0", "url": "https://x/s.exe", "sha256": "0" * 64, "tamanho": 0}, "manual")
    st = atu.ler_status()
    assert st["fase"] == "erro" and "SHA-256" in st["mensagem"]
    pasta = raiz / "Atualizacoes"
    assert not list(pasta.glob("*.exe")) and not list(pasta.glob("*.part"))
    assert chamadas == []


def test_auto_de_madrugada_so_uma_vez_por_dia_na_janela(instalado, monkeypatch):
    disparos = []
    monkeypatch.setattr(atu, "verificar", lambda: {"ok": True, "disponivel": {"versao": "99.0.0", "nova": True}})
    monkeypatch.setattr(atu, "iniciar_atualizacao",
                        lambda info, origem="manual", usuario="": disparos.append(origem))

    atu._tentar_auto(datetime(2026, 11, 19, 3, 10))       # auto desligado
    assert disparos == []
    atu._gravar_json(atu.pasta_atualizacoes() / "config.json", {"auto": True, "hora": "03:00"})
    atu._tentar_auto(datetime(2026, 11, 19, 2, 59))       # antes da janela
    atu._tentar_auto(datetime(2026, 11, 19, 4, 30))       # depois da janela
    assert disparos == []
    atu._tentar_auto(datetime(2026, 11, 19, 3, 20))
    atu._tentar_auto(datetime(2026, 11, 19, 3, 40))       # mesmo dia: não repete
    assert disparos == ["automatica"]
    atu._tentar_auto(datetime(2026, 11, 20, 3, 5))
    assert disparos == ["automatica", "automatica"]

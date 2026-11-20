"""Atualização do Cortex ERP instalado no servidor do cliente ("Verificar atualizações").

Como funciona (servidor Windows instalado pelo CortexERP-Setup):

1. Cada versão nova é enviada ao servidor de atualizações (Cloudflare Worker em
   cloudflare/atualizacoes): o instalador fica guardado num depósito privado (R2)
   e o manifesto (versão, SHA-256, notas) vira a "versão atual".
   scripts/lancar_versao.ps1 faz essa publicação.
2. "Verificar" manda a chave de licença do escritório ao servidor. Se a licença
   estiver ativa, ele devolve o manifesto e um link de download assinado, que
   vale por pouco tempo. Licença suspensa ou vencida = sem atualização (o
   sistema continua funcionando normalmente).
   (Legado: com CORTEX_UPDATE_URL definido, lê uma Release do GitHub ou um
   manifesto JSON direto, sem licença.)
3. "Baixar e instalar" baixa o instalador para <instalação>\\Atualizacoes, confere o
   SHA-256 e entrega a instalação ao atualizador.ps1, que roda como tarefa agendada
   do Windows (fora do serviço, porque o serviço é parado durante a troca):
   backup do banco -> cópia da versão atual -> instalação silenciosa -> conferência
   em /api/health. Se a versão nova não subir, ele volta a anterior sozinho.
4. Opcional: atualização automática de madrugada (agendador abaixo).

Na nuvem (Render) não há o que instalar: o deploy já atualiza a cada push, e o
navegador mostra o aviso "Nova versão disponível" (frontend/static/updater.js).
"""

import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

try:
    from ..auth import get_current_user
    from ..config import BASE_DIR
    from ..version import APP_VERSION, build_id, versao_tupla
except ImportError:
    from auth import get_current_user
    from config import BASE_DIR
    from version import APP_VERSION, build_id, versao_tupla

router = APIRouter(prefix="/api/system/update", tags=["Sistema, Backup & Monitoramento"])

# Servidor de atualizações e licenças (Cloudflare Worker). Pode ser trocado por
# CORTEX_ATUALIZACOES_URL no .env da instalação.
SERVIDOR_PADRAO = "https://cortex-atualizacoes.ruthsen41.workers.dev"
RE_CHAVE = re.compile(r"^CTX(-[A-Z0-9]{4}){3}$")
NOME_SETUP = "CortexERP-Setup.exe"
NOME_MANIFESTO = "cortex-update.json"
TAREFA = "CortexERP_Atualizacao"
FASES_EM_ANDAMENTO = {"baixando", "verificando", "agendada", "preparando", "instalando", "conferindo", "revertendo"}

_lock = threading.Lock()
_ultima_verificacao: Dict[str, Any] = {}


# ── onde está instalado ──────────────────────────────────────────────────────
def raiz_instalacao() -> Optional[Path]:
    """Pasta do Cortex instalado (C:\\CortexERP) ou None se não for instalação Windows."""
    forcada = os.getenv("CORTEX_RAIZ_INSTALACAO")
    if forcada:
        return Path(forcada)
    raiz = BASE_DIR.parent
    if os.name == "nt" and (raiz / "CortexServico.exe").exists() and (raiz / "atualizador.ps1").exists():
        return raiz
    return None


def pasta_atualizacoes() -> Path:
    raiz = raiz_instalacao()
    if raiz is None:
        raise HTTPException(400, "Este servidor não é uma instalação do Cortex para Windows.")
    p = raiz / "Atualizacoes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ler_json(arq: Path, padrao: Any) -> Any:
    try:
        return json.loads(arq.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return padrao


def _gravar_json(arq: Path, dados: Any) -> None:
    tmp = arq.with_suffix(arq.suffix + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, arq)


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ler_status() -> Dict[str, Any]:
    raiz = raiz_instalacao()
    if raiz is None:
        return {}
    return _ler_json(raiz / "Atualizacoes" / "status.json", {})


def gravar_status(fase: str, mensagem: str, progresso: Optional[int] = None, **extra) -> None:
    arq = pasta_atualizacoes() / "status.json"
    atual = _ler_json(arq, {})
    atual.update({"fase": fase, "mensagem": mensagem, "progresso": progresso, "atualizado_em": _agora()})
    atual.update(extra)
    _gravar_json(arq, atual)


def ler_config() -> Dict[str, Any]:
    cfg = {"auto": False, "hora": "03:00", "ultima_auto": "", "licenca": "", "instalacao": ""}
    raiz = raiz_instalacao()
    if raiz is not None:
        cfg.update(_ler_json(raiz / "Atualizacoes" / "config.json", {}))
    return cfg


def gravar_config(**campos) -> Dict[str, Any]:
    cfg = ler_config()
    cfg.update(campos)
    _gravar_json(pasta_atualizacoes() / "config.json", cfg)
    return cfg


def servidor_atualizacoes() -> str:
    return (os.getenv("CORTEX_ATUALIZACOES_URL") or SERVIDOR_PADRAO).rstrip("/")


def chave_licenca() -> str:
    """Chave do escritório: a digitada em Atualizações ou CORTEX_LICENCA no .env."""
    return (ler_config().get("licenca") or os.getenv("CORTEX_LICENCA") or "").strip().upper()


def id_instalacao() -> str:
    """Identificador aleatório desta instalação (ajuda a notar uma chave usada em dois lugares)."""
    cfg = ler_config()
    if not cfg.get("instalacao"):
        cfg = gravar_config(instalacao=uuid.uuid4().hex)
    return cfg["instalacao"]


def mascarar_chave(chave: str) -> str:
    return chave[:4] + "****-****-" + chave[-4:] if RE_CHAVE.match(chave or "") else ""


def em_andamento(status: Optional[Dict[str, Any]] = None) -> bool:
    st = status if status is not None else ler_status()
    if st.get("fase") not in FASES_EM_ANDAMENTO:
        return False
    # trava esquecida (queda de energia no meio): libera depois de 1 hora
    try:
        idade = (datetime.now() - datetime.fromisoformat(st.get("atualizado_em", ""))).total_seconds()
    except ValueError:
        return False
    return idade < 3600


# ── consulta da última versão publicada ──────────────────────────────────────
def _baixar_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"CortexERP-Atualizador/{APP_VERSION}",
        "Accept": "application/vnd.github+json, application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


class ErroServidor(Exception):
    """Recusa explicada pelo servidor de atualizações (licença suspensa, vencida...)."""


def _postar_json(url: str, dados: Dict[str, Any]) -> Any:
    req = urllib.request.Request(url, data=json.dumps(dados).encode("utf-8"), method="POST", headers={
        "User-Agent": f"CortexERP-Atualizador/{APP_VERSION}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("erro")
        except Exception:
            msg = None
        if msg:
            raise ErroServidor(msg) from e
        raise


def consultar_com_licenca() -> Dict[str, Any]:
    chave = chave_licenca()
    if not chave:
        raise ErroServidor("Informe a chave de licença do escritório (campo abaixo) para receber atualizações.")
    d = _postar_json(servidor_atualizacoes() + "/v1/verificar", {
        "chave": chave, "versao_atual": APP_VERSION, "instalacao": id_instalacao(),
    })
    info = {
        "versao": str(d.get("versao") or ""),
        "notas": d.get("notas") or "",
        "publicada_em": d.get("publicada_em") or "",
        "url": d.get("url") or "",
        "sha256": (d.get("sha256") or "").lower(),
        "tamanho": int(d.get("tamanho") or 0),
        "licenca": d.get("licenca") or {},
    }
    info["nova"] = versao_tupla(info["versao"]) > versao_tupla(APP_VERSION)
    return info


def consultar_ultima_versao() -> Dict[str, Any]:
    """Pergunta ao servidor de atualizações (com a chave de licença).
    Legado: com CORTEX_UPDATE_URL, lê uma Release do GitHub ou um manifesto JSON direto."""
    url = os.getenv("CORTEX_UPDATE_URL")
    if not url:
        return consultar_com_licenca()
    dados = _baixar_json(url)

    if "versao" in dados:  # manifesto direto
        info = {
            "versao": str(dados["versao"]),
            "notas": dados.get("notas", ""),
            "publicada_em": dados.get("publicada_em", ""),
            "url": dados.get("url", ""),
            "sha256": (dados.get("sha256") or "").lower(),
            "tamanho": int(dados.get("tamanho") or 0),
        }
    else:  # Release do GitHub
        assets = {a.get("name"): a for a in dados.get("assets", [])}
        setup = assets.get(NOME_SETUP)
        if not setup:
            raise ValueError(f"A versão publicada não tem o arquivo {NOME_SETUP}.")
        info = {
            "versao": (dados.get("tag_name") or "").lstrip("vV"),
            "notas": dados.get("body") or "",
            "publicada_em": dados.get("published_at") or "",
            "url": setup.get("browser_download_url", ""),
            "sha256": "",
            "tamanho": int(setup.get("size") or 0),
        }
        manifesto = assets.get(NOME_MANIFESTO)
        if manifesto:
            m = _baixar_json(manifesto["browser_download_url"])
            info["sha256"] = (m.get("sha256") or "").lower()
            info["versao"] = str(m.get("versao") or info["versao"])
            info["notas"] = m.get("notas") or info["notas"]
        if not info["sha256"] and str(setup.get("digest", "")).startswith("sha256:"):
            info["sha256"] = setup["digest"].split(":", 1)[1].lower()

    info["nova"] = versao_tupla(info["versao"]) > versao_tupla(APP_VERSION)
    return info


def verificar() -> Dict[str, Any]:
    global _ultima_verificacao
    try:
        info = consultar_ultima_versao()
        _ultima_verificacao = {"ok": True, "em": _agora(), "disponivel": info}
    except Exception as e:  # sem internet, GitHub fora, sem Release ainda...
        _ultima_verificacao = {"ok": False, "em": _agora(), "erro": _mensagem_erro(e)}
    return _ultima_verificacao


def _mensagem_erro(e: Exception) -> str:
    if isinstance(e, ErroServidor):
        return str(e)
    if isinstance(e, urllib.error.HTTPError) and e.code == 404:
        return "Nenhuma versão publicada ainda."
    if isinstance(e, urllib.error.URLError):
        return "Sem conexão com o servidor de atualizações. Verifique a internet deste computador."
    return str(e) or e.__class__.__name__


# ── download + entrega ao atualizador.ps1 ────────────────────────────────────
def _baixar_instalador(info: Dict[str, Any]) -> Path:
    pasta = pasta_atualizacoes()
    destino = pasta / f"CortexERP-Setup-{info['versao']}.exe"
    parcial = destino.with_suffix(".part")
    req = urllib.request.Request(info["url"], headers={"User-Agent": f"CortexERP-Atualizador/{APP_VERSION}"})
    h = hashlib.sha256()
    baixado, total, ultimo = 0, info.get("tamanho") or 0, 0.0
    with urllib.request.urlopen(req, timeout=60) as r, open(parcial, "wb") as f:
        total = int(r.headers.get("Content-Length") or total)
        while True:
            bloco = r.read(1024 * 256)
            if not bloco:
                break
            f.write(bloco)
            h.update(bloco)
            baixado += len(bloco)
            if time.monotonic() - ultimo > 1:
                ultimo = time.monotonic()
                pct = int(baixado * 100 / total) if total else None
                gravar_status("baixando", f"Baixando a versão {info['versao']}… "
                              f"{baixado / 1048576:.0f} de {total / 1048576:.0f} MB" if total else
                              f"Baixando a versão {info['versao']}…", pct)
    gravar_status("verificando", "Conferindo se o arquivo chegou inteiro e é o original…", 100)
    if h.hexdigest().lower() != info["sha256"]:
        parcial.unlink(missing_ok=True)
        raise ValueError("O arquivo baixado não confere com a assinatura publicada (SHA-256). "
                         "Nada foi alterado; tente de novo mais tarde.")
    os.replace(parcial, destino)
    for velho in pasta.glob("CortexERP-Setup-*.exe"):
        if velho != destino:
            velho.unlink(missing_ok=True)
    return destino


def _executar(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=60,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _agendar_atualizador(setup: Path, info: Dict[str, Any]) -> None:
    """Roda o atualizador.ps1 como tarefa do Windows (conta SYSTEM), fora da árvore
    de processos do serviço — senão ele morreria junto quando o serviço parar."""
    raiz = raiz_instalacao()
    pasta = pasta_atualizacoes()
    _gravar_json(pasta / "plano.json", {
        "versao": info["versao"],
        "versao_anterior": APP_VERSION,
        "setup": str(setup),
        "sha256": info["sha256"],
        "porta": os.getenv("CORTEX_PORT", "47800"),
        "tipo": "mono" if os.getenv("CORTEX_MODO") == "mono" else "servidor",
        "criado_em": _agora(),
    })
    script = raiz / "atualizador.ps1"
    comando = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{script}"'
    cria = _executar(["schtasks", "/Create", "/F", "/TN", TAREFA, "/SC", "ONCE", "/ST", "23:59",
                      "/RU", "SYSTEM", "/RL", "HIGHEST", "/TR", comando])
    if cria.returncode != 0:
        raise RuntimeError("Não foi possível agendar a instalação: " + (cria.stderr or cria.stdout).strip())
    roda = _executar(["schtasks", "/Run", "/TN", TAREFA])
    if roda.returncode != 0:
        raise RuntimeError("Não foi possível iniciar a instalação: " + (roda.stderr or roda.stdout).strip())


def _processo_atualizacao(info: Dict[str, Any], origem: str) -> None:
    try:
        setup = _baixar_instalador(info)
        gravar_status("agendada", "Iniciando a instalação. O sistema fica fora do ar por 1 a 3 minutos…", None)
        _agendar_atualizador(setup, info)
    except Exception as e:
        gravar_status("erro", "A atualização não foi feita. " + _mensagem_erro(e), None, erro=_mensagem_erro(e))


def iniciar_atualizacao(info: Dict[str, Any], origem: str = "manual", usuario: str = "") -> None:
    with _lock:
        if em_andamento():
            raise HTTPException(409, "Já existe uma atualização em andamento.")
        if not info.get("nova"):
            raise HTTPException(400, "Este servidor já está na versão mais recente.")
        if not info.get("url") or not info.get("sha256"):
            raise HTTPException(400, "A versão publicada não tem assinatura SHA-256; instalação recusada por segurança.")
        arq = pasta_atualizacoes() / "status.json"
        _gravar_json(arq, {
            "fase": "baixando", "mensagem": f"Baixando a versão {info['versao']}…", "progresso": 0,
            "versao_destino": info["versao"], "versao_anterior": APP_VERSION, "origem": origem,
            "solicitado_por": usuario, "iniciado_em": _agora(), "atualizado_em": _agora(),
        })
    threading.Thread(target=_processo_atualizacao, args=(info, origem), daemon=True,
                     name="cortex-atualizacao").start()


# ── API ──────────────────────────────────────────────────────────────────────
def pode_atualizar(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dono do sistema ou administrador da empresa (como "Atualização de software"
    no celular: quem administra o aparelho pode verificar e instalar)."""
    if not (user.get("is_superadmin") or user.get("role") == "admin"):
        raise HTTPException(403, "Somente o administrador pode verificar e instalar atualizações.")
    return user


def verificar_nuvem() -> Dict[str, Any]:
    """Na nuvem não há instalador: a versão "disponível" é a que está no ar agora.
    O navegador compara com a versão em que a página foi aberta."""
    return {"ok": True, "em": _agora(), "disponivel": {
        "versao": APP_VERSION, "build": build_id(), "nova": False, "modo": "nuvem"}}


# ── rotas ──────────────────────────────────────────────────────────────────────
class AutoConfig(BaseModel):
    ativo: bool
    hora: str = Field("03:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class LicencaIn(BaseModel):
    chave: str = Field(..., max_length=40)


@router.get("/status")
def status(user: Dict[str, Any] = Depends(pode_atualizar)):
    instalado = raiz_instalacao() is not None
    verificacao = _ultima_verificacao if instalado else None
    st = ler_status() if instalado else {}
    return {
        "modo": "instalado" if instalado else "nuvem",
        "versao_atual": APP_VERSION,
        "build": build_id(),
        "verificacao": verificacao or None,
        "andamento": st or None,
        "em_andamento": em_andamento(st) if instalado else False,
        "auto": {k: v for k, v in ler_config().items() if k in ("auto", "hora")} if instalado else None,
        "licenca": mascarar_chave(chave_licenca()) if instalado else None,
    }


@router.post("/check")
def check(user: Dict[str, Any] = Depends(pode_atualizar)):
    if raiz_instalacao() is None:
        return verificar_nuvem()
    return verificar()


@router.post("/apply")
def apply(user: Dict[str, Any] = Depends(pode_atualizar)):
    if raiz_instalacao() is None:
        raise HTTPException(400, "Na nuvem a atualização é automática: cada publicação já entra no ar.")
    v = verificar()
    if not v.get("ok"):
        raise HTTPException(502, v.get("erro") or "Não foi possível consultar a versão publicada.")
    iniciar_atualizacao(v["disponivel"], "manual", user.get("email", ""))
    return {"ok": True, "versao": v["disponivel"]["versao"]}


@router.put("/auto")
def set_auto(cfg: AutoConfig, user: Dict[str, Any] = Depends(pode_atualizar)):
    gravar_config(auto=cfg.ativo, hora=cfg.hora)
    return {"auto": cfg.ativo, "hora": cfg.hora}


@router.put("/licenca")
def set_licenca(dados: LicencaIn, user: Dict[str, Any] = Depends(pode_atualizar)):
    """Grava a chave de licença do escritório e já verifica com ela."""
    chave = re.sub(r"\s+", "", dados.chave).upper()
    if not RE_CHAVE.match(chave):
        raise HTTPException(400, "Chave em formato inválido. Ela tem o formato CTX-XXXX-XXXX-XXXX.")
    if raiz_instalacao() is None:
        raise HTTPException(400, "Na nuvem não é preciso chave de licença.")
    gravar_config(licenca=chave)
    return {"licenca": mascarar_chave(chave), "verificacao": verificar()}


# ── atualização automática de madrugada ──────────────────────────────────────
def _tentar_auto(agora: datetime) -> None:
    cfg = ler_config()
    if not cfg.get("auto"):
        return
    hoje = agora.date().isoformat()
    if cfg.get("ultima_auto") == hoje:
        return
    h, m = (int(x) for x in cfg.get("hora", "03:00").split(":"))
    inicio = agora.replace(hour=h, minute=m, second=0, microsecond=0)
    if not (0 <= (agora - inicio).total_seconds() < 3600):  # janela de 1 hora
        return
    gravar_config(ultima_auto=hoje)
    v = verificar()
    if v.get("ok") and v["disponivel"].get("nova") and not em_andamento():
        try:
            iniciar_atualizacao(v["disponivel"], "automatica")
        except HTTPException:
            pass


def iniciar_agendador_atualizacao() -> None:
    if raiz_instalacao() is None or os.getenv("CORTEX_ATUALIZACAO", "1") == "0":
        return

    def laco():
        while True:
            try:
                _tentar_auto(datetime.now())
            except Exception as e:  # nunca derruba o servidor
                print(f"[atualizacao] agendador: {e}", flush=True)
            time.sleep(300)

    threading.Thread(target=laco, daemon=True, name="cortex-atualizacao-auto").start()

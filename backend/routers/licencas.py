"""Licenças dos escritórios (Painel do Sistema > Licenças).

As licenças moram no servidor de atualizações (Cloudflare Worker + D1, ver
cloudflare/atualizacoes). Este roteador só repassa os pedidos do dono do Cortex
para a área de administração do Worker, usando o token guardado no servidor:

    CORTEX_ATUALIZACOES_URL          endereço do Worker
    CORTEX_ATUALIZACOES_ADMIN_TOKEN  token do dono (o mesmo do `wrangler secret put ADMIN_TOKEN`)

O token nunca vai para o navegador.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

try:
    from ..auth import log_audit, require_superadmin
    from ..database import get_conn
    from ..version import APP_VERSION
    from .atualizacao import servidor_atualizacoes
except ImportError:
    from auth import log_audit, require_superadmin
    from database import get_conn
    from routers.atualizacao import servidor_atualizacoes
    from version import APP_VERSION

router = APIRouter(prefix="/api/superadmin/licencas", tags=["Super Administrador"])

CAMPOS = ("cliente", "cnpj", "email", "expira_em", "observacao", "ativa")


def _admin(metodo: str, caminho: str, dados: Optional[Dict[str, Any]] = None) -> Any:
    token = os.getenv("CORTEX_ATUALIZACOES_ADMIN_TOKEN", "")
    if not token:
        raise HTTPException(503, "Servidor de licenças não configurado: defina CORTEX_ATUALIZACOES_ADMIN_TOKEN "
                                 "(e CORTEX_ATUALIZACOES_URL) nas variáveis de ambiente.")
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    req = urllib.request.Request(servidor_atualizacoes() + caminho, data=corpo, method=metodo, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": f"CortexERP-Painel/{APP_VERSION}",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("erro")
        except Exception:
            msg = None
        raise HTTPException(e.code if e.code < 500 else 502, msg or f"Servidor de licenças respondeu {e.code}.")
    except urllib.error.URLError:
        raise HTTPException(502, "Sem conexão com o servidor de licenças.")


def _auditar(user: Dict[str, Any], acao: str, dados: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        log_audit(conn, action=acao, entity="licencas", entity_id=0, new_data=dados, user_id=user["id"])
    finally:
        conn.close()


def _limpar(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: d[k] for k in CAMPOS if k in d}


@router.get("")
def listar(user: Dict[str, Any] = Depends(require_superadmin)):
    return _admin("GET", "/v1/admin/licencas")


@router.post("", status_code=201)
def criar(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_superadmin)):
    res = _admin("POST", "/v1/admin/licencas", _limpar(data))
    lic = res.get("licenca") or {}
    _auditar(user, "superadmin_licenca_criada", {"cliente": lic.get("cliente"), "chave": lic.get("chave")})
    return res


@router.patch("/{chave}")
def alterar(chave: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_superadmin)):
    res = _admin("PATCH", "/v1/admin/licencas/" + urllib.parse.quote(chave.upper()), _limpar(data))
    _auditar(user, "superadmin_licenca_alterada", {"chave": chave, **_limpar(data)})
    return res


@router.get("/versoes")
def versoes(user: Dict[str, Any] = Depends(require_superadmin)):
    return _admin("GET", "/v1/admin/versoes")

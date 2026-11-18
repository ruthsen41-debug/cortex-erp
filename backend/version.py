"""Versão do Cortex ERP — fonte única.

APP_VERSION é o número que aparece para o usuário e no instalador
(installer/build_instalador.ps1 lê daqui). Para lançar uma versão nova use
scripts/lancar_versao.ps1, que sobe este número, gera o instalador e publica.

BUILD_ID muda sozinho a cada alteração no frontend (ou na versão): é o que o
navegador compara para mostrar "Nova versão disponível", mesmo em deploys que
não mudaram o número da versão.
"""

import hashlib
from functools import lru_cache
from pathlib import Path

APP_VERSION = "4.5.0"

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@lru_cache(maxsize=1)
def build_id() -> str:
    h = hashlib.sha256(APP_VERSION.encode())
    if _FRONTEND_DIR.exists():
        for arq in sorted(p for p in _FRONTEND_DIR.rglob("*") if p.is_file()):
            h.update(arq.relative_to(_FRONTEND_DIR).as_posix().encode())
            h.update(arq.read_bytes())
    return h.hexdigest()[:12]


def versao_tupla(v: str) -> tuple:
    """'4.10.2' -> (4, 10, 2); ignora prefixo 'v' e sufixos ('-pro+')."""
    v = (v or "").strip().lstrip("vV").split("-")[0].split("+")[0]
    partes = []
    for p in v.split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        partes.append(int(num) if num else 0)
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes)

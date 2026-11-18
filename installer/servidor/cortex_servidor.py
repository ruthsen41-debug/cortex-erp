"""Inicializador do Cortex ERP no servidor do escritório.

É executado pelo serviço do Windows "CortexERP" (WinSW) com o Python embutido
que vem no instalador. Não precisa de Python instalado na máquina.

Além do sistema (HTTP na porta CORTEX_PORT), responde à busca das estações na
porta UDP 47801: o programa Cortex.exe pergunta "onde está o servidor?" por
broadcast e recebe o nome da máquina e a porta. Assim ninguém precisa digitar IP.

Estrutura instalada (padrão C:\\CortexERP):
    python\\              Python embutido + dependências
    app\\                 código do Cortex (backend, frontend, scripts)
    app\\.env             configuração gerada na instalação (porta, segredo JWT)
    app\\data\\           banco de dados SQLite (nunca é apagado na desinstalação)
    cliente\\             programa Cortex.exe (também usado neste servidor)
    Backups\\             cópias diárias do banco
    logs\\                logs do serviço
"""

import json
import os
import socket
import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
APP = RAIZ / "app"

PORTA_DESCOBERTA = 47801
PERGUNTA = b"CORTEX_ERP_PROCURA_SERVIDOR"

sys.path.insert(0, str(APP))
os.chdir(APP)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(APP / ".env")

import uvicorn  # noqa: E402


def responder_descoberta(porta_http: int) -> None:
    """Responde às estações que procuram o servidor na rede local (UDP)."""
    resposta = json.dumps({"porta": porta_http, "nome": socket.gethostname()}).encode()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", PORTA_DESCOBERTA))
    except OSError as e:
        print(f"Busca automática pelas estações desativada (porta UDP {PORTA_DESCOBERTA}): {e}", flush=True)
        return
    print(f"Respondendo à busca das estações na porta UDP {PORTA_DESCOBERTA}", flush=True)
    while True:
        try:
            dados, origem = s.recvfrom(256)
            if dados.strip() == PERGUNTA:
                s.sendto(resposta, origem)
        except OSError:
            continue


def main() -> None:
    host = os.getenv("CORTEX_HOST", "0.0.0.0")
    porta = int(os.getenv("CORTEX_PORT", "47800"))
    if os.getenv("CORTEX_MODO") == "mono":
        host = "127.0.0.1"
    if os.getenv("CORTEX_MODO", "servidor") != "mono":  # monousuário: invisível na rede
        threading.Thread(target=responder_descoberta, args=(porta,), daemon=True, name="descoberta").start()
    print(f"Cortex ERP iniciando em http://{host}:{porta}", flush=True)
    uvicorn.run("backend.main:app", host=host, port=porta, workers=1, log_level="info")


if __name__ == "__main__":
    main()

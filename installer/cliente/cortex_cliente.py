"""Cortex.exe — programa do Cortex ERP para servidor e estações (janela própria).

Igual ao modelo do Domínio: o usuário só abre o programa. Ele
  1. usa o servidor salvo da última vez (ou o informado na instalação);
  2. se não responder, procura o servidor na rede local (UDP broadcast);
  3. se não achar, pede o nome ou IP do servidor (uma vez só).
A porta é descoberta automaticamente; o usuário nunca precisa saber dela.

Configuração:
  padrão da instalação:  <pasta do Cortex.exe>\\cortex.ini
  do usuário (gravável): %LOCALAPPDATA%\\CortexERP\\cortex.ini
"""

import configparser
import json
import os
import socket
import sys
import urllib.request
import webbrowser
from pathlib import Path

PORTA_DESCOBERTA = 47801
PORTA_PADRAO = 47800
PERGUNTA = b"CORTEX_ERP_PROCURA_SERVIDOR"
TITULO = "Cortex ERP"

PASTA_EXE = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
PASTA_USUARIO = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CortexERP"
INI_PADRAO = PASTA_EXE / "cortex.ini"
INI_USUARIO = PASTA_USUARIO / "cortex.ini"


# ── configuração ─────────────────────────────────────────────────────────────
def ler_endereco() -> str:
    for ini in (INI_USUARIO, INI_PADRAO):
        cp = configparser.ConfigParser()
        try:
            cp.read(ini, encoding="utf-8")
            end = cp.get("servidor", "endereco", fallback="").strip()
            if end:
                return end
        except (configparser.Error, OSError):
            pass
    return ""


def salvar_endereco(endereco: str) -> None:
    PASTA_USUARIO.mkdir(parents=True, exist_ok=True)
    cp = configparser.ConfigParser()
    cp["servidor"] = {"endereco": endereco}
    with open(INI_USUARIO, "w", encoding="utf-8") as f:
        cp.write(f)


# ── rede ─────────────────────────────────────────────────────────────────────
def responde(endereco: str, timeout: float = 2.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://{endereco}/api/health", timeout=timeout) as r:
            return json.loads(r.read().decode()).get("status") == "ok"
    except Exception:
        return False


def _alvos_broadcast() -> list[str]:
    alvos = {"255.255.255.255"}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")):
                alvos.add(ip.rsplit(".", 1)[0] + ".255")  # redes /24, as mais comuns em escritório
    except OSError:
        pass
    return sorted(alvos)


def procurar_servidores(destinos: list[str] | None = None, espera: float = 2.0) -> list[tuple[str, str]]:
    """Retorna [(endereco 'ip:porta', nome_do_servidor)] de quem respondeu."""
    achados: dict[str, str] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(espera)
        for alvo in destinos or _alvos_broadcast():
            try:
                s.sendto(PERGUNTA, (alvo, PORTA_DESCOBERTA))
            except OSError:
                pass
        while True:
            try:
                dados, (ip, _) = s.recvfrom(1024)
            except (socket.timeout, OSError):
                break
            try:
                info = json.loads(dados.decode())
                achados[f"{ip}:{int(info['porta'])}"] = info.get("nome", ip)
            except (ValueError, KeyError):
                continue
    return list(achados.items())


def resolver_digitado(texto: str) -> str | None:
    """Converte o que o usuário digitou (nome, IP ou nome:porta) num endereço que responde."""
    texto = texto.strip().removeprefix("http://").rstrip("/")
    if not texto:
        return None
    if ":" in texto:
        return texto if responde(texto) else None
    for end, _ in procurar_servidores([texto], espera=1.5):  # pergunta a porta direto ao servidor
        pelo_nome = f"{texto}:{end.rsplit(':', 1)[1]}"  # guarda o nome digitado: sobrevive à troca de IP
        if responde(pelo_nome):
            return pelo_nome
        if responde(end):
            return end
    end = f"{texto}:{PORTA_PADRAO}"
    return end if responde(end) else None


# ── diálogos (tkinter, só quando precisa perguntar algo) ───────────────────────
def _tk():
    import tkinter as tk

    raiz = tk.Tk()
    raiz.withdraw()
    raiz.attributes("-topmost", True)
    return raiz


def escolher_entre(achados: list[tuple[str, str]]) -> str | None:
    from tkinter import simpledialog

    raiz = _tk()
    lista = "\n".join(f"{i + 1} - {nome} ({end.split(':')[0]})" for i, (end, nome) in enumerate(achados))
    n = simpledialog.askinteger(TITULO, f"Foram encontrados vários servidores do Cortex:\n\n{lista}\n\nDigite o número:",
                                parent=raiz, minvalue=1, maxvalue=len(achados))
    raiz.destroy()
    return achados[n - 1][0] if n else None


def perguntar_servidor() -> str | None:
    from tkinter import messagebox, simpledialog

    raiz = _tk()
    try:
        while True:
            texto = simpledialog.askstring(
                TITULO,
                "Não foi possível localizar o servidor do Cortex automaticamente.\n\n"
                "Verifique se o computador servidor está ligado e na mesma rede.\n\n"
                "Nome ou IP do servidor:",
                parent=raiz,
            )
            if texto is None:
                return None
            end = resolver_digitado(texto)
            if end:
                return end
            messagebox.showerror(TITULO, f"O servidor \"{texto}\" não respondeu.\nConfira o nome e se ele está ligado.",
                                 parent=raiz)
    finally:
        raiz.destroy()


def _preferir_nome(end: str, nome: str) -> str:
    """Usa o nome da máquina servidora quando ele resolve na rede; senão fica com o IP."""
    pelo_nome = f"{nome}:{end.rsplit(':', 1)[1]}"
    return pelo_nome if nome and responde(pelo_nome, timeout=1.5) else end


def achar_servidor() -> str | None:
    salvo = ler_endereco()
    if salvo:
        if responde(salvo):
            return salvo
        if ":" not in salvo:  # instalação informou só o nome do servidor
            end = resolver_digitado(salvo)
            if end:
                salvar_endereco(end)
                return end
    achados = [(_preferir_nome(e, n), n) for e, n in procurar_servidores() if responde(e)]
    end = achados[0][0] if len(achados) == 1 else (escolher_entre(achados) if achados else perguntar_servidor())
    if end:
        salvar_endereco(end)
    return end


# ── janela ───────────────────────────────────────────────────────────────────
def abrir(endereco: str) -> None:
    import webview
    from webview.platforms import edgechromium

    origem = f"http://{endereco}"

    def nova_janela(self, sender, args):
        # Relatórios usam window.open('') e escrevem o HTML na janela: deixa o WebView2
        # criar a janela popup dele. Links externos (WhatsApp, sites) vão para o navegador.
        uri = str(args.get_Uri())
        if uri.startswith(("http://", "https://")) and not uri.startswith(origem):
            args.set_Handled(True)
            webbrowser.open(uri)

    edgechromium.EdgeChrome.on_new_window_request = nova_janela
    webview.settings["ALLOW_DOWNLOADS"] = True

    webview.create_window(TITULO, origem, width=1366, height=820, min_size=(1024, 640), maximized=True,
                          text_select=True, confirm_close=False)
    PASTA_USUARIO.mkdir(parents=True, exist_ok=True)
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(PASTA_USUARIO / "navegador"))


def main() -> None:
    endereco = achar_servidor()
    if not endereco:
        return
    abrir(endereco)


if __name__ == "__main__":
    main()

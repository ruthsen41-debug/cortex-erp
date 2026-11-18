"""Configuração pós-instalação do Cortex ERP (servidor do escritório).

Chamado pelo instalador (Inno Setup) com o Python embutido:
    python configurar.py --porta 47800 --modo servidor|mono [--arquivo-senha C:\\tmp\\senha.txt]

Modos:
  servidor  multiusuário: aceita as estações da rede (host 0.0.0.0) e responde à busca automática;
  mono      monousuário: só este computador acessa (host 127.0.0.1), nada fica aberto na rede.

O que faz:
  1. cria app\\.env na primeira instalação (porta, segredo JWT, host 0.0.0.0);
     em reinstalação/atualização só ajusta a porta e preserva o resto;
  2. cria/atualiza o banco SQLite (init_db);
  3. na primeira instalação troca a senha padrão do admin pela escolhida
     e substitui a chave de API de demonstração por uma aleatória;
  4. grava "ENDERECO_DAS_ESTACOES.txt" com o endereço que os outros PCs devem usar.
"""

import argparse
import os
import re
import secrets
import socket
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
APP = RAIZ / "app"
ENV = APP / ".env"
CHAVE_API_DEMO = "ctx_live_7a8b9c0d1e2f3a4b5c6d"


def ips_da_rede() -> list[str]:
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.add(ip)
    except OSError:
        pass
    try:  # IP da rota padrão (não envia nada pela rede)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(ips)


def escrever_env(porta: int, modo: str = "servidor") -> bool:
    """Cria ou atualiza o .env. Retorna True se era uma instalação nova."""
    mono = modo == "mono"
    host = "127.0.0.1" if mono else "0.0.0.0"
    url = f"http://{'localhost' if mono else socket.gethostname()}:{porta}"
    if ENV.exists():
        texto = ENV.read_text(encoding="utf-8")
        for chave, valor in (("CORTEX_HOST", host), ("CORTEX_MODO", modo), ("CORTEX_PORT", str(porta)),
                             ("APP_BASE_URL", url), ("ERP_BASE_URL", url)):
            if re.search(rf"^{chave}=", texto, flags=re.M):
                texto = re.sub(rf"^{chave}=.*$", f"{chave}={valor}", texto, flags=re.M)
            else:
                texto += f"\n{chave}={valor}\n"
        ENV.write_text(texto, encoding="utf-8")
        return False

    ENV.write_text(
        "# Gerado pelo instalador do Cortex ERP.\n"
        "# Depois de alterar, reinicie o serviço \"Cortex ERP - Servidor\".\n"
        "# CORTEX_MODO: servidor (multiusuário, aceita a rede) ou mono (só este computador)\n"
        f"CORTEX_MODO={modo}\n"
        f"CORTEX_HOST={host}\n"
        f"CORTEX_PORT={porta}\n"
        f"JWT_SECRET_KEY={secrets.token_urlsafe(64)}\n"
        "ENVIRONMENT=production\n"
        "# Vazio = banco SQLite local em app\\data\\cortex_erp.db\n"
        "DATABASE_URL=\n"
        f"APP_BASE_URL={url}\n"
        f"ERP_BASE_URL={url}\n"
        "CORS_ORIGINS=\n"
        "TRUSTED_PROXY=0\n"
        "RATE_LIMIT_API=300\n"
        "RATE_LIMIT_LOGIN=10\n"
        "LOG_FORMAT=text\n"
        "LOG_LEVEL=INFO\n"
        "GEMINI_API_KEY=\n"
        "SMTP_HOST=\n"
        "SMTP_PORT=587\n"
        "SMTP_USER=\n"
        "SMTP_PASSWORD=\n"
        "SMTP_FROM=noreply@cortex.com.br\n",
        encoding="utf-8",
    )
    return True


def preparar_banco(senha_admin: str | None) -> None:
    sys.path.insert(0, str(APP))
    os.chdir(APP)
    from dotenv import load_dotenv

    load_dotenv(ENV, override=True)
    from backend.database import get_conn, init_db

    init_db()
    if not senha_admin:
        return
    import bcrypt

    conn = get_conn()
    try:
        hash_ = bcrypt.hashpw(senha_admin.encode("utf-8"), bcrypt.gensalt()).decode()
        conn.execute("UPDATE users SET password_hash = ? WHERE email = 'admin@cortex.com.br'", (hash_,))
        conn.execute(
            "UPDATE api_keys SET api_key = ? WHERE api_key = ?",
            (f"ctx_live_{secrets.token_hex(16)}", CHAVE_API_DEMO),
        )
        conn.commit()
    finally:
        conn.close()


def gravar_enderecos(porta: int, modo: str = "servidor") -> None:
    arquivo = RAIZ / "ENDERECO_DAS_ESTACOES.txt"
    if modo == "mono":  # monousuário: não há estações
        arquivo.unlink(missing_ok=True)
        return
    linhas = [
        "CORTEX ERP - ENDEREÇO PARA OS OUTROS COMPUTADORES DO ESCRITÓRIO",
        "=" * 64,
        "",
        "Neste servidor:      http://localhost:%d" % porta,
        "Pelo nome da máquina: http://%s:%d" % (socket.gethostname(), porta),
    ]
    for ip in ips_da_rede():
        linhas.append("Pelo IP:             http://%s:%d" % (ip, porta))
    linhas += [
        "",
        "Nas estações, instale o CortexERP-Estacao-Setup.exe. O programa Cortex",
        "procura este servidor na rede sozinho; se não achar, informe o nome",
        "da máquina acima (%s)." % socket.gethostname(),
        "",
        "Também funciona pelo navegador (Edge/Chrome) em qualquer um dos",
        "endereços acima.",
        "",
        "Recomendação: reserve um IP fixo para este servidor no roteador.",
        "",
        "Login inicial: admin@cortex.com.br (senha definida na instalação).",
    ]
    # utf-8-sig: o Bloco de Notas antigo reconhece a acentuação; o modo texto já grava CRLF
    arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8-sig")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--porta", type=int, default=47800)
    p.add_argument("--modo", choices=("servidor", "mono"), default="servidor")
    p.add_argument("--arquivo-senha", help="arquivo temporário com a senha do admin (apagado após a leitura)")
    a = p.parse_args()

    senha = None
    if a.arquivo_senha and Path(a.arquivo_senha).exists():
        arq = Path(a.arquivo_senha)
        bruto = arq.read_bytes()
        try:  # utf-8-sig remove o BOM que o Inno/PowerShell gravam no início
            texto = bruto.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = bruto.decode("cp1252")
        senha = texto.rstrip("\r\n") or None
        arq.unlink(missing_ok=True)

    nova = escrever_env(a.porta, a.modo)
    # Senha só é aplicada na primeira instalação, para não sobrescrever a senha em uso.
    preparar_banco(senha if nova else None)
    gravar_enderecos(a.porta, a.modo)
    print("Configuração concluída.", "(instalação nova)" if nova else "(atualização)", f"modo={a.modo}")


if __name__ == "__main__":
    main()

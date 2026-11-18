"""
Envio de holerites por e-mail.

Cada empresa configura o próprio servidor de e-mail (SMTP), para que o holerite saia com o
remetente dela. Sem configuração própria, usa o SMTP do sistema (variáveis SMTP_*), se houver.
A senha fica cifrada no banco (crypto_vault). O holerite vai como anexo HTML (abre no navegador
e imprime ou salva em PDF) e o texto do e-mail aceita os campos {nome}, {competencia},
{empresa} e {liquido}.
"""
from __future__ import annotations

import os
import re
import smtplib
import ssl
import unicodedata
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from html import escape
from typing import Any, Callable, Dict, List, Optional

try:
    from .crypto_vault import CryptoVault
except ImportError:  # execução fora do pacote
    from crypto_vault import CryptoVault  # type: ignore

SEGURANCAS = ("starttls", "ssl", "nenhuma")
ASSUNTO_PADRAO = "Holerite {competencia} — {empresa}"
CORPO_PADRAO = ("Olá, {nome}.\n\nSegue em anexo o seu recibo de pagamento referente a {competencia}.\n"
                "Valor líquido: R$ {liquido}.\n\nAbra o anexo no navegador para ver, imprimir ou salvar em PDF.\n\n"
                "Atenciosamente,\n{empresa}")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailConfigErro(ValueError):
    pass


def email_valido(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def carregar_config(conn, company_id: int, com_senha: bool = False) -> Dict[str, Any]:
    """Configuração da empresa; sem ela, a do sistema (variáveis de ambiente). Campo origem diz qual."""
    row = conn.execute("SELECT * FROM smtp_config WHERE company_id=?", (company_id,)).fetchone()
    row = dict(row) if row else {}
    if row.get("host"):
        cfg = {"origem": "empresa", "host": row["host"], "porta": int(row.get("porta") or 587),
               "seguranca": row.get("seguranca") or "starttls", "usuario": row.get("usuario") or "",
               "remetente": row.get("remetente") or row.get("usuario") or "",
               "nome_remetente": row.get("nome_remetente") or "", "tem_senha": bool(row.get("senha_cifrada"))}
        if com_senha:
            cfg["senha"] = CryptoVault.decrypt_string(row.get("senha_cifrada") or "")
    elif os.getenv("SMTP_HOST"):
        porta = int(os.getenv("SMTP_PORT", "587") or 587)
        cfg = {"origem": "sistema", "host": os.getenv("SMTP_HOST", ""), "porta": porta,
               "seguranca": "ssl" if porta == 465 else "starttls", "usuario": os.getenv("SMTP_USER", ""),
               "remetente": os.getenv("SMTP_FROM") or os.getenv("SMTP_USER", ""), "nome_remetente": "",
               "tem_senha": bool(os.getenv("SMTP_PASSWORD"))}
        if com_senha:
            cfg["senha"] = os.getenv("SMTP_PASSWORD", "")
    else:
        cfg = {"origem": "nenhuma", "host": "", "porta": 587, "seguranca": "starttls", "usuario": "",
               "remetente": "", "nome_remetente": "", "tem_senha": False}
    cfg["assunto"] = row.get("assunto") or ASSUNTO_PADRAO
    cfg["corpo"] = row.get("corpo") or CORPO_PADRAO
    return cfg


def salvar_config(conn, company_id: int, dados: Dict[str, Any]) -> None:
    host = str(dados.get("host") or "").strip()
    seguranca = str(dados.get("seguranca") or "starttls")
    if seguranca not in SEGURANCAS:
        raise EmailConfigErro("Segurança deve ser STARTTLS, SSL ou nenhuma.")
    try:
        porta = int(dados.get("porta") or (465 if seguranca == "ssl" else 587))
    except (TypeError, ValueError):
        raise EmailConfigErro("Porta inválida.")
    if not 1 <= porta <= 65535:
        raise EmailConfigErro("Porta inválida.")
    remetente = str(dados.get("remetente") or dados.get("usuario") or "").strip()
    if host and not email_valido(remetente):
        raise EmailConfigErro("Informe um e-mail de remetente válido.")
    assunto = str(dados.get("assunto") or "").strip()[:200]
    corpo = str(dados.get("corpo") or "").strip()[:3000]
    for texto in (assunto, corpo):
        try:
            texto.format(nome="", competencia="", empresa="", liquido="")
        except (KeyError, IndexError, ValueError):
            raise EmailConfigErro("Use só os campos {nome}, {competencia}, {empresa} e {liquido} no texto.")
    atual = conn.execute("SELECT senha_cifrada FROM smtp_config WHERE company_id=?", (company_id,)).fetchone()
    senha_cifrada = dict(atual)["senha_cifrada"] if atual else ""
    if dados.get("senha"):                       # senha em branco mantém a gravada
        senha_cifrada = CryptoVault.encrypt_string(str(dados["senha"]))
    if dados.get("apagar_senha"):
        senha_cifrada = ""
    valores = (host, porta, seguranca, str(dados.get("usuario") or "").strip(), senha_cifrada, remetente,
               str(dados.get("nome_remetente") or "").strip()[:120], assunto, corpo,
               datetime.now().isoformat(timespec="seconds"))
    if atual:
        conn.execute("""UPDATE smtp_config SET host=?, porta=?, seguranca=?, usuario=?, senha_cifrada=?, remetente=?,
                        nome_remetente=?, assunto=?, corpo=?, atualizado_em=? WHERE company_id=?""", (*valores, company_id))
    else:
        conn.execute("""INSERT INTO smtp_config (host, porta, seguranca, usuario, senha_cifrada, remetente,
                        nome_remetente, assunto, corpo, atualizado_em, company_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (*valores, company_id))


def _conectar(cfg: Dict[str, Any]) -> smtplib.SMTP:
    if not cfg.get("host"):
        raise EmailConfigErro("Servidor de e-mail não configurado. Configure em DP › Parâmetros › E-mail.")
    ctx = ssl.create_default_context()
    if cfg["seguranca"] == "ssl":
        srv: smtplib.SMTP = smtplib.SMTP_SSL(cfg["host"], cfg["porta"], timeout=20, context=ctx)
    else:
        srv = smtplib.SMTP(cfg["host"], cfg["porta"], timeout=20)
        srv.ehlo()
        if cfg["seguranca"] == "starttls":
            srv.starttls(context=ctx)
            srv.ehlo()
    if cfg.get("usuario") and cfg.get("senha"):
        srv.login(cfg["usuario"], cfg["senha"])
    return srv


def _nome_arquivo(nome: str, competencia: str) -> str:
    base = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_")[:40] or "funcionario"
    return f"holerite_{competencia}_{base}.html"


def montar_mensagem(cfg: Dict[str, Any], para: str, campos: Dict[str, str], anexo_html: Optional[str],
                    nome_anexo: str = "holerite.html") -> MIMEMultipart:
    msg = MIMEMultipart("mixed")
    msg["Subject"] = cfg["assunto"].format(**campos)
    msg["From"] = formataddr((cfg.get("nome_remetente") or campos.get("empresa") or "", cfg["remetente"]))
    msg["To"] = para
    texto = cfg["corpo"].format(**campos)
    corpo = MIMEMultipart("alternative")
    corpo.attach(MIMEText(texto, "plain", "utf-8"))
    corpo.attach(MIMEText("<html><body style='font-family:Arial,sans-serif;color:#111827'>"
                          + escape(texto).replace("\n", "<br>") + "</body></html>", "html", "utf-8"))
    msg.attach(corpo)
    if anexo_html:
        parte = MIMEApplication(anexo_html.encode("utf-8"), _subtype="html")
        parte.add_header("Content-Disposition", "attachment", filename=nome_anexo)
        msg.attach(parte)
    return msg


def enviar_teste(cfg: Dict[str, Any], para: str) -> None:
    if not email_valido(para):
        raise EmailConfigErro("E-mail de destino inválido.")
    msg = montar_mensagem({**cfg, "assunto": "Teste de e-mail — Cortex ERP",
                           "corpo": "Este é um teste do envio de holerites. Se você recebeu, a configuração está correta."},
                          para, {"nome": "", "competencia": "", "empresa": cfg.get("nome_remetente") or "", "liquido": ""}, None)
    srv = _conectar(cfg)
    try:
        srv.sendmail(cfg["remetente"], [para], msg.as_bytes())
    finally:
        try:
            srv.quit()
        except Exception:
            pass


def enviar_holerites(cfg: Dict[str, Any], destinos: List[Dict[str, Any]],
                     gerar_anexo: Callable[[Dict[str, Any]], str]) -> List[Dict[str, Any]]:
    """
    destinos: [{employee_id, nome, email, competencia, competencia_extenso, empresa, liquido, item}].
    Abre uma conexão e envia um e-mail por funcionário; erro de um não para os outros.
    Retorna [{employee_id, email, status: enviado|erro|sem_email, erro}].
    """
    out: List[Dict[str, Any]] = []
    pendentes = []
    for d in destinos:
        if not email_valido(d.get("email") or ""):
            out.append({"employee_id": d["employee_id"], "email": d.get("email") or "", "status": "sem_email",
                        "erro": "Funcionário sem e-mail válido no cadastro."})
        else:
            pendentes.append(d)
    if not pendentes:
        return out
    srv = _conectar(cfg)
    try:
        for d in pendentes:
            campos = {"nome": d["nome"].split(" ")[0] if d["nome"] else "", "competencia": d["competencia_extenso"],
                      "empresa": d["empresa"], "liquido": d["liquido"]}
            try:
                msg = montar_mensagem(cfg, d["email"].strip(), campos, gerar_anexo(d["item"]),
                                      _nome_arquivo(d["nome"], d["competencia"]))
                srv.sendmail(cfg["remetente"], [d["email"].strip()], msg.as_bytes())
                out.append({"employee_id": d["employee_id"], "email": d["email"], "status": "enviado", "erro": ""})
            except smtplib.SMTPServerDisconnected:
                srv = _conectar(cfg)  # o servidor caiu no meio: reconecta e tenta de novo uma vez
                try:
                    srv.sendmail(cfg["remetente"], [d["email"].strip()], msg.as_bytes())
                    out.append({"employee_id": d["employee_id"], "email": d["email"], "status": "enviado", "erro": ""})
                except Exception as e:
                    out.append({"employee_id": d["employee_id"], "email": d["email"], "status": "erro", "erro": str(e)[:300]})
            except Exception as e:
                out.append({"employee_id": d["employee_id"], "email": d["email"], "status": "erro", "erro": str(e)[:300]})
    finally:
        try:
            srv.quit()
        except Exception:
            pass
    return out

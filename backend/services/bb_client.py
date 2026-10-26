"""
Cliente HTTP para a API do Banco do Brasil — modelo ISV (fluxo OAuth authorization_code).
Cada empresa-cliente autoriza o acesso via fluxo OAuth e tem seu próprio par de tokens
armazenado no banco. O cliente (desenvolvedor) usa suas credenciais do portal BB Developers.

Fluxo completo:
  1. GET /api/bb/oauth/authorize  → redireciona o cliente para o BB fazer login e autorizar
  2. BB redireciona para /api/bb/oauth/callback?code=...&state=...
  3. Callback troca o code por access_token + refresh_token e salva no banco por company_id
  4. Todas as chamadas seguintes usam o token da empresa, com refresh automático
"""
import os
import re
import ssl
import base64
import json
import secrets
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import httpx

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------

def _cfg(key: str, default: str = "") -> str:
    return os.getenv(key, default)

def _cfg_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def _sandbox() -> bool:
    return _cfg("BB_SANDBOX", "false").lower() == "true"

def _oauth_base() -> str:
    return "https://oauth.hm.bb.com.br" if _sandbox() else "https://oauth.bb.com.br"

def _api_base() -> str:
    return "https://api.hm.bb.com.br" if _sandbox() else "https://api.bb.com.br"

def _extrato_base() -> str:
    return "https://extratos.mtls.api.hm.bb.com.br/v2" if _sandbox() else "https://extratos.mtls.api.bb.com.br/v2"

def _app_key_param() -> str:
    return f"gw-dev-app-key={_cfg('BB_APP_KEY')}"

# Escopos necessários para o ERP
BB_SCOPES = "cobrancas.boletos-requisicao pix.write extrato-info"

BB_SANDBOX: bool = _sandbox()


# ---------------------------------------------------------------------------
# mTLS
# ---------------------------------------------------------------------------

def _mtls_cert() -> Optional[Tuple[str, str]]:
    cert = _cfg("BB_CERT_PATH")
    key = _cfg("BB_KEY_PATH")
    if cert and key and Path(cert).exists() and Path(key).exists():
        return (cert, key)
    return None

def _http_client(**kwargs) -> httpx.Client:
    mtls = _mtls_cert()
    if mtls:
        return httpx.Client(cert=mtls, **kwargs)
    return httpx.Client(**kwargs)


# ---------------------------------------------------------------------------
# BANCO DE TOKENS (por empresa)
# ---------------------------------------------------------------------------

def _get_db():
    try:
        from ..database import get_conn
    except ImportError:
        from database import get_conn
    return get_conn()


def save_company_token(
    company_id: int,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    scope: str = "",
) -> None:
    """Persiste ou atualiza o par de tokens de uma empresa no banco."""
    expires_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    # Guarda o timestamp unix para facilitar comparação
    expires_ts = int(time.time()) + int(expires_in)
    conn = _get_db()
    conn.execute("""
        INSERT INTO bb_oauth_tokens (company_id, access_token, refresh_token, expires_at, expires_ts, scope)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(company_id) DO UPDATE SET
            access_token = excluded.access_token,
            refresh_token = excluded.refresh_token,
            expires_at = excluded.expires_at,
            expires_ts = excluded.expires_ts,
            scope = excluded.scope,
            updated_at = CURRENT_TIMESTAMP
    """, (company_id, access_token, refresh_token, expires_at, expires_ts, scope))
    conn.commit()
    conn.close()


def get_company_token_row(company_id: int) -> Optional[Dict[str, Any]]:
    """Retorna a linha de token de uma empresa ou None se não conectada."""
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM bb_oauth_tokens WHERE company_id = ?", (company_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def remove_company_token(company_id: int) -> None:
    conn = _get_db()
    conn.execute("DELETE FROM bb_oauth_tokens WHERE company_id = ?", (company_id,))
    conn.commit()
    conn.close()


def _refresh_token(company_id: int, refresh_tok: str) -> str:
    """Troca o refresh_token por um novo access_token e salva."""
    client_id = _cfg("BB_CLIENT_ID")
    client_secret = _cfg("BB_CLIENT_SECRET")
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    with _http_client(timeout=10.0) as c:
        resp = c.post(
            f"{_oauth_base()}/oauth/token",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "refresh_token", "refresh_token": refresh_tok},
        )
    resp.raise_for_status()
    data = resp.json()
    save_company_token(
        company_id,
        data["access_token"],
        data.get("refresh_token", refresh_tok),
        int(data.get("expires_in", 3600)),
        data.get("scope", BB_SCOPES),
    )
    return data["access_token"]


def get_company_access_token(company_id: int) -> str:
    """
    Retorna um access_token válido para a empresa.
    Faz refresh automático se estiver expirado (com margem de 60s).
    Lança RuntimeError se a empresa não estiver conectada.
    """
    row = get_company_token_row(company_id)
    if not row:
        raise RuntimeError(
            f"Empresa {company_id} não autorizou o acesso ao Banco do Brasil. "
            "Acesse /api/bb/oauth/authorize para conectar."
        )
    now_ts = int(time.time())
    if now_ts < row["expires_ts"] - 60:
        return row["access_token"]
    # Token expirado — tenta refresh
    if row.get("refresh_token"):
        try:
            return _refresh_token(company_id, row["refresh_token"])
        except Exception:
            pass
    raise RuntimeError(
        f"Token da empresa {company_id} expirado e não foi possível renovar. "
        "Reconecte acessando /api/bb/oauth/authorize."
    )


def _auth_headers(company_id: int) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {get_company_access_token(company_id)}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# FLUXO OAUTH — authorization_code
# ---------------------------------------------------------------------------

# Cache de nonces para verificar o state no callback (em memória, 10 min)
_state_cache: Dict[str, Dict[str, Any]] = {}

def _purge_old_states() -> None:
    now = time.time()
    expired = [k for k, v in _state_cache.items() if now - v["ts"] > 600]
    for k in expired:
        del _state_cache[k]


def get_authorization_url(company_id: int, redirect_uri: str) -> str:
    """
    Gera a URL de autorização do BB para redirecionar o cliente.
    O parâmetro state codifica company_id + nonce para verificação no callback.
    """
    _purge_old_states()
    nonce = secrets.token_urlsafe(16)
    state_data = {"company_id": company_id, "nonce": nonce}
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
    _state_cache[state] = {"company_id": company_id, "ts": time.time()}

    client_id = _cfg("BB_CLIENT_ID")
    params = (
        f"response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={BB_SCOPES.replace(' ', '%20')}"
        f"&state={state}"
    )
    return f"{_oauth_base()}/oauth/authorize?{params}"


def exchange_code_for_token(code: str, redirect_uri: str, state: str) -> Dict[str, Any]:
    """
    Troca o authorization_code por access_token + refresh_token.
    Verifica o state e retorna {'company_id', 'access_token', 'scope', ...}.
    """
    _purge_old_states()

    # Valida state
    state_info = _state_cache.pop(state, None)
    if not state_info:
        # Tenta decodificar mesmo sem cache (para callbacks que demoraram > 10min)
        try:
            state_info = json.loads(base64.urlsafe_b64decode(state + "=="))
        except Exception:
            raise ValueError("Parâmetro state inválido ou expirado.")

    company_id = int(state_info["company_id"])
    client_id = _cfg("BB_CLIENT_ID")
    client_secret = _cfg("BB_CLIENT_SECRET")
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    with _http_client(timeout=15.0) as c:
        resp = c.post(
            f"{_oauth_base()}/oauth/token",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
    resp.raise_for_status()
    data = resp.json()

    save_company_token(
        company_id,
        data["access_token"],
        data.get("refresh_token", ""),
        int(data.get("expires_in", 3600)),
        data.get("scope", BB_SCOPES),
    )
    return {"company_id": company_id, **data}


# ---------------------------------------------------------------------------
# HELPERS DE DATA
# ---------------------------------------------------------------------------

def _to_bb_date(iso_date: str) -> str:
    d = date.fromisoformat(iso_date)
    return f"{d.day:02d}.{d.month:02d}.{d.year}"

def _to_bb_extrato_date(iso_date: str) -> str:
    d = date.fromisoformat(iso_date)
    return f"{d.day:02d}-{d.month:02d}-{d.year}"

def _to_bb_date_int(iso_date: str) -> int:
    d = date.fromisoformat(iso_date)
    return int(f"{d.day:02d}{d.month:02d}{d.year}")

def _parse_bb_date_int(val) -> str:
    s = str(int(val or 0)).zfill(8)  # DDMMAAAA
    return f"{s[4:]}-{s[2:4]}-{s[:2]}"

def _normalize_date(raw: str) -> str:
    raw = (raw or "")[:10].strip()
    if not raw:
        return date.today().isoformat()
    if "." in raw:
        p = raw.split(".")
        if len(p) == 3:
            return f"{p[2]}-{p[1]}-{p[0]}"
    if "-" in raw and len(raw) == 10 and raw[2] == "-":
        p = raw.split("-")
        if len(p) == 3:
            return f"{p[2]}-{p[1]}-{p[0]}"
    return raw


# ---------------------------------------------------------------------------
# BOLETO v2
# ---------------------------------------------------------------------------

def emitir_boleto(
    company_id: int,
    nosso_numero: int,
    valor: float,
    vencimento: str,
    pagador_nome: str,
    pagador_doc: str,
    pagador_cep: str,
    pagador_endereco: str,
    pagador_bairro: str,
    pagador_cidade: str,
    pagador_uf: str,
    descricao: str = "",
    indicador_pix: str = "S",
) -> Dict[str, Any]:
    convenio = _cfg("BB_CONVENIO")
    doc_clean = re.sub(r"\D", "", pagador_doc or "00000000000")
    tipo_inscricao = 2 if len(doc_clean) == 14 else 1

    payload = {
        "numeroConvenio": int(convenio),
        "numeroCarteira": _cfg_int("BB_CARTEIRA", 17),
        "numeroVariacaoCarteira": _cfg_int("BB_VARIACAO_CARTEIRA", 35),
        "codigoModalidade": 1,
        "dataEmissao": _to_bb_date(date.today().isoformat()),
        "dataVencimento": _to_bb_date(vencimento),
        "valorOriginal": round(valor, 2),
        "quantidadeDiasProtesto": 0,
        "quantidadeDiasNegativacao": 0,
        "orgaoNegativador": 0,
        "indicadorAceiteTituloVencido": "N",
        "numeroDiasLimiteRecebimento": 0,
        "codigoAceite": "A",
        "codigoTipoTitulo": 2,
        "descricaoTipoTitulo": "DM",
        "indicadorPermissaoRecebimentoParcial": "N",
        "numeroTituloBeneficiario": str(nosso_numero),
        "campoUtilizacaoBeneficiario": descricao[:30],
        "numeroTituloCliente": f"000{convenio}{nosso_numero:010d}",
        "mensagemBloquetoOcorrencia": descricao[:30],
        "desconto": {"tipo": 0, "dataExpiracao": "", "valor": 0, "porcentagem": 0},
        "segundoDesconto": {"dataExpiracao": "", "valor": 0, "porcentagem": 0},
        "terceiroDesconto": {"dataExpiracao": "", "valor": 0, "porcentagem": 0},
        "jurosMora": {"tipo": 0, "valor": 0, "porcentagem": 0},
        "multa": {"tipo": 0, "data": "", "valor": 0, "porcentagem": 0},
        "pagador": {
            "tipoInscricao": tipo_inscricao,
            "numeroInscricao": doc_clean[:14],
            "nome": (pagador_nome or "Consumidor Final")[:40],
            "endereco": (pagador_endereco or "Sem endereço")[:40],
            "cep": re.sub(r"\D", "", pagador_cep or "78000000")[:8],
            "cidade": (pagador_cidade or "Cuiabá")[:20],
            "bairro": (pagador_bairro or "Centro")[:40],
            "uf": (pagador_uf or "MT")[:2].upper(),
            "telefone": "",
        },
        "indicadorPix": indicador_pix,
    }

    url = f"{_api_base()}/cobrancas/v2/boletos?{_app_key_param()}"
    with _http_client(timeout=15.0) as c:
        resp = c.post(url, headers=_auth_headers(company_id), json=payload)
    resp.raise_for_status()
    return resp.json()


def consultar_boleto(company_id: int, numero_boleto: str) -> Dict[str, Any]:
    convenio = _cfg("BB_CONVENIO")
    url = f"{_api_base()}/cobrancas/v2/boletos/{numero_boleto}?{_app_key_param()}&numeroConvenio={convenio}"
    with _http_client(timeout=10.0) as c:
        resp = c.get(url, headers=_auth_headers(company_id))
    resp.raise_for_status()
    return resp.json()


def cancelar_boleto(company_id: int, numero_boleto: str) -> Dict[str, Any]:
    convenio = _cfg("BB_CONVENIO")
    url = f"{_api_base()}/cobrancas/v2/boletos/{numero_boleto}/baixar?{_app_key_param()}"
    with _http_client(timeout=10.0) as c:
        resp = c.post(url, headers=_auth_headers(company_id), json={"numeroConvenio": int(convenio)})
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# PIX CoB v2
# ---------------------------------------------------------------------------

def criar_cobranca_pix(
    company_id: int,
    txid: str,
    valor: float,
    devedor_nome: str,
    devedor_doc: str,
    descricao: str = "",
    expiracao: int = 86400,
) -> Dict[str, Any]:
    pix_key = _cfg("BB_PIX_KEY")
    if not pix_key:
        raise RuntimeError("BB_PIX_KEY não configurada.")

    doc_clean = re.sub(r"\D", "", devedor_doc or "00000000000")
    devedor: Dict[str, Any] = {"nome": (devedor_nome or "Consumidor Final")[:25]}
    if len(doc_clean) == 14:
        devedor["cnpj"] = doc_clean
    else:
        devedor["cpf"] = doc_clean[:11].zfill(11)

    safe_txid = re.sub(r"[^a-zA-Z0-9]", "", txid)[:35].ljust(26, "0")
    payload = {
        "calendario": {"expiracao": expiracao},
        "devedor": devedor,
        "valor": {"original": f"{valor:.2f}"},
        "chave": pix_key,
        "solicitacaoPagador": (descricao or "Pagamento Cortex ERP")[:140],
    }

    url = f"{_api_base()}/pix/v2/cob/{safe_txid}?{_app_key_param()}"
    with _http_client(timeout=15.0) as c:
        resp = c.put(url, headers=_auth_headers(company_id), json=payload)
    resp.raise_for_status()
    return resp.json()


def consultar_pix(company_id: int, txid: str) -> Dict[str, Any]:
    safe_txid = re.sub(r"[^a-zA-Z0-9]", "", txid)[:35]
    url = f"{_api_base()}/pix/v2/cob/{safe_txid}?{_app_key_param()}"
    with _http_client(timeout=10.0) as c:
        resp = c.get(url, headers=_auth_headers(company_id))
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# EXTRATO v2
# ---------------------------------------------------------------------------

def consultar_extrato(
    company_id: int,
    data_inicio: str,
    data_fim: str,
    agencia: int,
    conta: int,
) -> List[Dict[str, Any]]:
    """
    Consulta extrato via API BB Extratos v2.
    Endpoint: /conta-corrente/agencia/{agencia}/conta/{conta}
    Datas no formato DDMMAAAA (inteiro). Pagina automaticamente até o fim.
    """
    dt_inicio = _to_bb_date_int(data_inicio)
    dt_fim = _to_bb_date_int(data_fim)
    result: List[Dict[str, Any]] = []
    pagina = 1
    while True:
        url = (
            f"{_extrato_base()}/conta-corrente/agencia/{agencia}/conta/{conta}"
            f"?{_app_key_param()}"
            f"&dataInicioSolicitacao={dt_inicio}"
            f"&dataFimSolicitacao={dt_fim}"
            f"&numeroPaginaSolicitacao={pagina}"
            f"&quantidadeRegistroPaginaSolicitacao=120"
        )
        with _http_client(timeout=20.0) as c:
            resp = c.get(url, headers=_auth_headers(company_id))
        resp.raise_for_status()
        raw = resp.json()
        for item in (raw.get("listaLancamento") or []):
            tipo = str(item.get("indicadorTipoLancamento") or "")
            if tipo not in ("1", "2", "3"):  # ignora saldos/limites (SA, SD, LD, etc.)
                continue
            indicador = str(item.get("indicadorSinalLancamento") or "").upper()
            raw_val = float(item.get("valorLancamento") or 0)
            if indicador == "D" and raw_val > 0:
                raw_val = -raw_val
            elif indicador == "C" and raw_val < 0:
                raw_val = abs(raw_val)
            doc = item.get("numeroDocumento")
            fitid = str(doc) if doc else ""
            data_raw = item.get("dataLancamento")
            posted = _parse_bb_date_int(data_raw) if data_raw else data_fim
            desc = (item.get("textoDescricaoSubHistorico") or "").strip()
            compl = (item.get("textoInformacaoComplementar") or "").strip()
            memo = f"{desc} {compl}".strip() or "Lançamento BB"
            result.append({
                "codigoLancamento": fitid,
                "dataLancamento": posted,
                "valorLancamento": raw_val,
                "textoLancamento": memo,
                "indicadorDebitoCredito": indicador if indicador in ("C", "D") else ("C" if raw_val >= 0 else "D"),
            })
        prox = int(raw.get("numeroPaginaProximo") or 0)
        if not prox:
            break
        pagina = prox
    return result


# ---------------------------------------------------------------------------
# GERAÇÃO DE CSR mTLS
# ---------------------------------------------------------------------------

def gerar_csr(
    company_name: str,
    cnpj: str,
    state: str = "MT",
    city: str = "Cuiabá",
    key_out_path: Optional[str] = None,
) -> Dict[str, str]:
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
    except ImportError:
        raise RuntimeError("Pacote 'cryptography' não instalado. Execute: pip install cryptography")

    private_key = _rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cnpj_clean = re.sub(r"\D", "", cnpj)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state[:64]),
            x509.NameAttribute(NameOID.LOCALITY_NAME, city[:64]),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, company_name[:64]),
            x509.NameAttribute(NameOID.COMMON_NAME, cnpj_clean),
        ]))
        .sign(private_key, hashes.SHA256())
    )
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()

    if key_out_path:
        key_path = Path(key_out_path)
    else:
        try:
            from ..config import DATA_DIR
        except ImportError:
            from config import DATA_DIR
        key_path = Path(DATA_DIR) / "bb_mtls.key"

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(key_pem, encoding="utf-8")
    try:
        key_path.chmod(0o600)
    except Exception:
        pass

    return {
        "csr_pem": csr_pem,
        "key_path": str(key_path),
        "instrucoes": (
            "1. Copie o CSR e cole em developers.bb.com.br → Aplicação → Certificado mTLS.\n"
            "2. BB assina e devolve um .crt.\n"
            "3. Configure no .env: BB_KEY_PATH e BB_CERT_PATH."
        ),
    }


# ---------------------------------------------------------------------------
# UTIL
# ---------------------------------------------------------------------------

def normalize_extrato_date(raw: str) -> str:
    return _normalize_date(raw)

def is_configured() -> bool:
    return bool(_cfg("BB_CLIENT_ID") and _cfg("BB_CLIENT_SECRET") and _cfg("BB_APP_KEY"))

def is_company_connected(company_id: int) -> bool:
    return get_company_token_row(company_id) is not None

def mtls_active() -> bool:
    return _mtls_cert() is not None

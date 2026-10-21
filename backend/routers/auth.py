import os
import logging
import secrets
import smtplib
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException, Depends, Request, status
from typing import Dict, Any

_log = logging.getLogger(__name__)


def _send_reset_email(to_email: str, name: str, reset_url: str) -> bool:
    """Envia e-mail de recuperação de senha via SMTP.

    Retorna True se enviado com sucesso; False se SMTP não estiver configurado
    (modo desenvolvimento) ou se o envio falhar.
    """
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    if not smtp_host:
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "noreply@cortex.com.br").strip()

    plain = (
        f"Olá {name},\n\n"
        f"Recebemos uma solicitação para redefinir a senha da sua conta no Cortex ERP.\n\n"
        f"Acesse o link abaixo (válido por 1 hora):\n{reset_url}\n\n"
        f"Se você não fez essa solicitação, ignore este e-mail.\n\n"
        f"Cortex ERP\n"
    )
    html = (
        f"<html><body style='font-family:Inter,system-ui,sans-serif;color:#111827'>"
        f"<p>Olá <strong>{name}</strong>,</p>"
        f"<p>Recebemos uma solicitação para redefinir a senha da sua conta no <strong>Cortex ERP</strong>.</p>"
        f"<p><a href='{reset_url}' style='display:inline-block;background:#2563eb;color:#fff;"
        f"padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:600'>"
        f"Redefinir minha senha</a></p>"
        f"<p style='font-size:12px;color:#6b7280'>Link válido por 1 hora. "
        f"Se não foi você, ignore este e-mail.</p>"
        f"</body></html>"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Redefinição de Senha — Cortex ERP"
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as srv:
            srv.ehlo()
            if smtp_port != 465:
                srv.starttls()
                srv.ehlo()
            if smtp_user and smtp_password:
                srv.login(smtp_user, smtp_password)
            srv.sendmail(smtp_from, [to_email], msg.as_bytes())
        return True
    except Exception as exc:
        _log.error("Falha ao enviar e-mail de recuperação para %s: %s", to_email, exc)
        return False

try:
    from ..database import get_conn
    from ..auth import hash_password, verify_password, create_access_token, get_current_user, log_audit
    from ..schemas.auth import (
        LoginRequest, TokenResponse, UserCreate, UserResponse,
        CompanyRegisterRequest, CompanyRegisterResponse,
        ForgotPasswordRequest, ResetPasswordRequest,
    )
except ImportError:
    from database import get_conn
    from auth import hash_password, verify_password, create_access_token, get_current_user, log_audit
    from schemas.auth import (
        LoginRequest, TokenResponse, UserCreate, UserResponse,
        CompanyRegisterRequest, CompanyRegisterResponse,
        ForgotPasswordRequest, ResetPasswordRequest,
    )

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])

MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300
_failed_logins = defaultdict(deque)


def _login_key(request: Request, email: str) -> str:
    return f"{request.client.host if request.client else '-'}|{email.strip().lower()}"


def _check_login_allowed(key: str) -> None:
    attempts = _failed_logins[key]
    now = time.monotonic()
    while attempts and now - attempts[0] > LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Muitas tentativas de login. Aguarde alguns minutos.")


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request):
    """Autentica o usuário com e-mail e senha, retornando JWT."""
    key = _login_key(request, req.email)
    _check_login_allowed(key)
    conn = get_conn()
    cur = conn.cursor()
    user = cur.execute(
        "SELECT id, company_id, name, email, password_hash, role, active FROM users WHERE email = ?",
        (req.email,),
    ).fetchone()

    if not user or not user["active"]:
        _failed_logins[key].append(time.monotonic())
        conn.close()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos.")

    if not verify_password(req.password, user["password_hash"]):
        _failed_logins[key].append(time.monotonic())
        conn.close()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos.")

    _failed_logins.pop(key, None)
    token = create_access_token({"sub": user["email"], "uid": user["id"], "role": user["role"]})
    log_audit(conn, action="login", entity="users", entity_id=user["id"], user_id=user["id"])
    conn.close()

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "company_id": user["company_id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        },
    }


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retorna dados do usuário atualmente logado."""
    return current_user


@router.post("/register", response_model=UserResponse)
def register_user(req: UserCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Cria um novo usuário para a empresa (requer perfil admin)."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores podem cadastrar novos usuários.")

    conn = get_conn()
    cur = conn.cursor()

    existing = cur.execute("SELECT id FROM users WHERE email = ?", (req.email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="E-mail já cadastrado no sistema.")

    pwd_hash = hash_password(req.password)
    cur.execute("""
        INSERT INTO users (company_id, name, email, password_hash, role)
        VALUES (?, ?, ?, ?, ?)
    """, (req.company_id or current_user.get("company_id", 1), req.name, req.email, pwd_hash, req.role))
    user_id = cur.lastrowid
    conn.commit()

    log_audit(conn, action="create", entity="users", entity_id=user_id, new_data=req.model_dump(exclude={"password"}), user_id=current_user["id"])
    new_user = cur.execute("SELECT id, company_id, name, email, role, active, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return dict(new_user)


@router.post("/register-company", response_model=CompanyRegisterResponse)
def register_company(req: CompanyRegisterRequest):
    """
    Onboarding público: cadastra uma nova empresa e seu primeiro usuário administrador.
    Gera as configurações iniciais (conta bancária, chave de API) e devolve o token JWT de acesso.
    """
    company_name = req.company_name.strip()
    admin_name = req.admin_name.strip()
    email = req.email.strip().lower()

    if not company_name:
        raise HTTPException(status_code=400, detail="O nome da empresa é obrigatório.")
    if not admin_name:
        raise HTTPException(status_code=400, detail="O nome do administrador é obrigatório.")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Informe um e-mail válido.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve conter no mínimo 6 caracteres.")

    conn = get_conn()
    cur = conn.cursor()

    existing_user = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing_user:
        conn.close()
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado no sistema.")

    accountant_token = secrets.token_urlsafe(16)
    cnpj = req.cnpj.strip() if req.cnpj else "00.000.000/0001-91"
    city = req.city.strip() if req.city else "São Paulo"
    state = req.state.strip().upper() if req.state else "SP"
    phone = req.phone.strip() if req.phone else ""

    try:
        # 1. Cria a nova empresa
        cur.execute("""
            INSERT INTO companies (
                razao_social, nome_fantasia, cnpj, regime_tributario,
                telefone, email, cidade, uf, accountant_token,
                ambiente_fiscal, motor_fiscal
            ) VALUES (?, ?, ?, 'simples_nacional', ?, ?, ?, ?, ?, 'homologacao', 'sefaz_direto')
        """, (company_name, company_name, cnpj, phone, email, city, state, accountant_token))
        company_id = cur.lastrowid

        # 2. Cria a conta bancária inicial da empresa (Caixa Geral)
        cur.execute("""
            INSERT INTO bank_accounts (company_id, name, bank_code, bank_name, account_type, initial_balance, current_balance)
            VALUES (?, 'Caixa Geral', '000', 'Caixa Interno', 'caixa', 0.0, 0.0)
        """, (company_id,))

        # 3. Cria o usuário administrador
        pwd_hash = hash_password(req.password)
        cur.execute("""
            INSERT INTO users (company_id, name, email, password_hash, role, active)
            VALUES (?, ?, ?, ?, 'admin', 1)
        """, (company_id, admin_name, email, pwd_hash))
        user_id = cur.lastrowid

        # 4. Cria a API Key padrão para integrações
        api_key_str = f"ctx_live_{secrets.token_hex(10)}"
        cur.execute("""
            INSERT INTO api_keys (company_id, name, api_key, active)
            VALUES (?, 'Chave de Integração Principal', ?, 1)
        """, (company_id, api_key_str))

        # 5. Notificação de boas-vindas
        cur.execute("""
            INSERT INTO notifications (company_id, title, message, type, is_read, link)
            VALUES (?, 'Bem-vindo ao Cortex ERP!', 'Sua empresa foi cadastrada com sucesso. Comece configurando seus dados e produtos.', 'success', 0, '')
        """, (company_id,))

        conn.commit()

        log_audit(conn, action="onboarding", entity="companies", entity_id=company_id, user_id=user_id)
        log_audit(conn, action="create", entity="users", entity_id=user_id, user_id=user_id)

        token = create_access_token({"sub": email, "uid": user_id, "role": "admin"})

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "company_id": company_id,
                "name": admin_name,
                "email": email,
                "role": "admin",
            },
            "company": {
                "id": company_id,
                "name": company_name,
                "cnpj": cnpj,
            },
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, request: Request):
    """Gera token de redefinição de senha válido por 1 hora.
    Em produção configure SMTP para enviar o e-mail; em dev o link é retornado na resposta.
    """
    email = req.email.strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    user = cur.execute(
        "SELECT id, name FROM users WHERE email = ? AND active = 1",
        (email,),
    ).fetchone()

    generic = {"message": "Se o e-mail estiver cadastrado, um link de redefinição será enviado em breve."}

    if not user:
        conn.close()
        return generic

    # Invalida tokens anteriores do mesmo usuário
    cur.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user["id"],))
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    cur.execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user["id"], token, expires_at),
    )
    conn.commit()
    log_audit(conn, action="forgot_password", entity="users", entity_id=user["id"],
              ip_address=request.client.host if request.client else None)
    conn.close()

    base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
    reset_url = f"{base_url}/?reset_token={token}" if base_url else f"/?reset_token={token}"

    sent = _send_reset_email(email, user["name"], reset_url)

    # Modo desenvolvimento: retorna o link na resposta se SMTP não estiver configurado.
    if not sent and os.getenv("ENVIRONMENT", "development") != "production":
        return {**generic, "dev_reset_url": reset_url}
    return generic


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    """Valida o token assinado e redefine a senha do usuário."""
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="A nova senha deve ter pelo menos 6 caracteres.")

    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    row = cur.execute(
        "SELECT id, user_id, expires_at, used FROM password_reset_tokens WHERE token = ?",
        (req.token,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="Token inválido ou expirado.")
    if row["used"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Este link já foi utilizado. Solicite um novo.")
    if row["expires_at"] < now:
        conn.close()
        raise HTTPException(status_code=400, detail="Link expirado (válido por 1 hora). Solicite um novo.")

    pwd_hash = hash_password(req.new_password)
    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, row["user_id"]))
    cur.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    log_audit(conn, action="reset_password", entity="users", entity_id=row["user_id"])
    conn.close()

    return {"message": "Senha redefinida com sucesso. Você já pode fazer login."}
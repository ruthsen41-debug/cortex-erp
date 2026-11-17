import sqlite3
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

try:
    from .config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, DEFAULT_COMPANY_ID
    from .database import get_conn
except ImportError:
    from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, DEFAULT_COMPANY_ID
    from database import get_conn

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    """Gera hash seguro bcrypt para a senha."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Valida a senha em texto puro contra o hash bcrypt."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Gera token JWT assinado."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica e valida o token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Retorna o usuário autenticado via Bearer Token; sem token válido responde 401."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticação necessária.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise unauthorized
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise unauthorized

    conn = get_conn()
    try:
        user = conn.execute(
            """SELECT u.id, u.company_id, u.name, u.email, u.role, u.active,
                      COALESCE(u.is_superadmin, 0) AS is_superadmin,
                      COALESCE(u.home_company_id, u.company_id) AS home_company_id,
                      COALESCE(c.status, 'ativa') AS company_status
               FROM users u
               LEFT JOIN companies c ON c.id = COALESCE(NULLIF(u.home_company_id, 0), u.company_id)
               WHERE u.email = ? AND u.active = 1""",
            (payload["sub"],),
        ).fetchone()
    finally:
        conn.close()
    if not user:
        raise unauthorized
    user = dict(user)
    if not user["is_superadmin"] and user["company_status"] != "ativa":
        # Empresa pendente de aprovação ou bloqueada pelo dono do sistema: derruba a sessão.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=company_status_message(user["company_status"]),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def company_status_message(company_status: str) -> str:
    if company_status == "pendente":
        return "Cadastro da empresa aguardando aprovação do administrador do sistema."
    if company_status == "bloqueada":
        return "Acesso da empresa bloqueado. Entre em contato com o suporte."
    return "Acesso da empresa indisponível."


def require_superadmin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency: apenas o dono do sistema (super administrador)."""
    if not user.get("is_superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Acesso restrito ao administrador do sistema.")
    return user


def require_role(*allowed_roles: str):
    """Dependency para controle de acesso baseado em papéis (RBAC)."""
    def role_checker(user: Dict[str, Any] = Depends(get_current_user)):
        if user.get("role") not in allowed_roles and user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso não autorizado para o perfil do seu usuário.",
            )
        return user
    return role_checker


def log_audit(
    conn: sqlite3.Connection,
    action: str,
    entity: str,
    entity_id: Optional[int] = None,
    old_data: Optional[Any] = None,
    new_data: Optional[Any] = None,
    user_id: Optional[int] = 1,
    company_id: int = DEFAULT_COMPANY_ID,
    ip_address: Optional[str] = None,
) -> None:
    """Registra uma entrada de auditoria imutável."""
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_logs (company_id, user_id, action, entity, entity_id, old_data, new_data, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id,
            user_id,
            action,
            entity,
            entity_id,
            json.dumps(old_data, default=str) if old_data else None,
            json.dumps(new_data, default=str) if new_data else None,
            ip_address or "127.0.0.1",
        ))
        conn.commit()
    except Exception as e:
        # Falha em log de auditoria não deve quebrar a transação principal
        print(f"[Audit Warning] Erro ao gravar auditoria: {e}")

import sqlite3
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status, Request
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
    """
    Retorna o usuário autenticado via Bearer Token.
    Se nenhum token for enviado (modo desenvolvimento/desktop SPA),
    retorna o usuário Administrador padrão.
    """
    conn = get_conn()
    cur = conn.cursor()

    if token:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            email = payload["sub"]
            user = cur.execute(
                "SELECT id, company_id, name, email, role, active FROM users WHERE email = ? AND active = 1",
                (email,),
            ).fetchone()
            if user:
                conn.close()
                return dict(user)

    # Fallback para usuário admin padrão se não houver token explícito
    admin = cur.execute(
        "SELECT id, company_id, name, email, role, active FROM users WHERE role = 'admin' AND active = 1 ORDER BY id ASC LIMIT 1"
    ).fetchone()
    conn.close()

    if admin:
        return dict(admin)

    return {
        "id": 1,
        "company_id": DEFAULT_COMPANY_ID,
        "name": "Administrador Cortex",
        "email": "admin@cortex.com.br",
        "role": "admin",
        "active": 1,
    }


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

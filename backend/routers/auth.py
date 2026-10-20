from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import hash_password, verify_password, create_access_token, get_current_user, log_audit
    from ..schemas.auth import LoginRequest, TokenResponse, UserCreate, UserResponse
except ImportError:
    from database import get_conn
    from auth import hash_password, verify_password, create_access_token, get_current_user, log_audit
    from schemas.auth import LoginRequest, TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """Autentica o usuário com e-mail e senha, retornando JWT."""
    conn = get_conn()
    cur = conn.cursor()
    user = cur.execute(
        "SELECT id, company_id, name, email, password_hash, role, active FROM users WHERE email = ?",
        (req.email,),
    ).fetchone()

    if not user or not user["active"]:
        conn.close()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos.")

    if not verify_password(req.password, user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos.")

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

    log_audit(conn, action="create", entity="users", entity_id=user_id, new_data=req.dict(exclude={"password"}), user_id=current_user["id"])
    new_user = cur.execute("SELECT id, company_id, name, email, role, active, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return dict(new_user)

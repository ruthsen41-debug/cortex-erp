from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "operador"
    company_id: Optional[int] = 1


class UserResponse(BaseModel):
    id: int
    company_id: int
    name: str
    email: str
    role: str
    active: int
    created_at: Optional[str] = None

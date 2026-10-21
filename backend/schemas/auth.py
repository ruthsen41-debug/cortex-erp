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


class CompanyRegisterRequest(BaseModel):
    company_name: str
    admin_name: str
    email: str
    password: str
    cnpj: Optional[str] = ""
    phone: Optional[str] = ""
    city: Optional[str] = "São Paulo"
    state: Optional[str] = "SP"


class CompanyRegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    company: dict


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


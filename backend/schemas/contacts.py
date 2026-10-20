from typing import Optional
from pydantic import BaseModel


class ContactCreate(BaseModel):
    type: str = "cliente"  # cliente, fornecedor, ambos
    person_type: Optional[str] = "PJ"  # PJ, PF
    name: str
    trade_name: Optional[str] = ""
    document: Optional[str] = ""
    state_registration: Optional[str] = ""
    municipal_registration: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    cep: Optional[str] = ""
    street: Optional[str] = ""
    number: Optional[str] = ""
    complement: Optional[str] = ""
    neighborhood: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    company_id: Optional[int] = 1

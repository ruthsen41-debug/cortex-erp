from typing import Optional, List
from pydantic import BaseModel, Field


class FinancialCreate(BaseModel):
    type: str = Field(..., description="receita ou despesa")
    description: str
    amount: float = Field(..., gt=0)
    due_date: Optional[str] = None
    competence_date: Optional[str] = None
    category_id: Optional[int] = None
    bank_account_id: Optional[int] = None
    contact_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    payment_method: Optional[str] = "Pix"
    installments: Optional[int] = Field(default=1, ge=1, le=120)
    recurrence: Optional[str] = "unico"  # unico, mensal
    already_paid: Optional[bool] = False
    document_number: Optional[str] = ""
    notes: Optional[str] = ""


class FinancialPayRequest(BaseModel):
    amount: float = Field(..., gt=0)
    bank_account_id: int
    payment_date: Optional[str] = None
    interest: Optional[float] = 0.0
    fine: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    payment_method: Optional[str] = "Pix"
    notes: Optional[str] = ""


class BatchPayRequest(BaseModel):
    entry_ids: List[int]
    bank_account_id: int
    payment_date: Optional[str] = None
    payment_method: Optional[str] = "Pix"


class BankAccountCreate(BaseModel):
    name: str
    bank_name: str
    bank_code: Optional[str] = "000"
    agency: Optional[str] = ""
    account_number: Optional[str] = ""
    account_type: Optional[str] = "corrente"
    initial_balance: Optional[float] = 0.0
    company_id: Optional[int] = 1


class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float = Field(..., gt=0)
    date: Optional[str] = None
    description: Optional[str] = "Transferência entre Contas"


class CategoryCreate(BaseModel):
    code: str
    name: str
    type: str  # receita ou despesa
    dre_group: Optional[str] = "despesas_operacionais"
    keywords: Optional[str] = ""
    company_id: Optional[int] = 1


class AiLaunchRequest(BaseModel):
    text: str

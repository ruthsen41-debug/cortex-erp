from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


class AccountingAccountCreate(BaseModel):
    code: str = Field(..., description="Ex: 1.1.01")
    name: str
    account_type: str = Field(..., description="ativo, passivo, patrimonio_liquido, receita, custo, despesa")
    nature: str = Field(..., description="devedora (normal débito) ou credora (normal crédito)")
    parent_code: Optional[str] = None
    accepts_entries: Optional[bool] = True
    description: Optional[str] = ""
    company_id: Optional[int] = 1


class AccountingAccountUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    accepts_entries: Optional[bool] = None
    active: Optional[bool] = None


class EntryLineCreate(BaseModel):
    account_id: int
    debit: Optional[float] = Field(default=0.0, ge=0)
    credit: Optional[float] = Field(default=0.0, ge=0)
    description: Optional[str] = ""

    @model_validator(mode="after")
    def check_debit_or_credit(self) -> "EntryLineCreate":
        if (self.debit or 0) == 0 and (self.credit or 0) == 0:
            raise ValueError("Cada linha deve ter débito ou crédito maior que zero.")
        if (self.debit or 0) > 0 and (self.credit or 0) > 0:
            raise ValueError("Débito e crédito não podem ser ambos preenchidos na mesma linha.")
        return self


class AccountingEntryCreate(BaseModel):
    entry_date: str
    description: str
    document_number: Optional[str] = ""
    entry_type: Optional[str] = "manual"  # manual, automatico
    origin_id: Optional[int] = None
    lines: List[EntryLineCreate] = Field(..., min_length=2)
    company_id: Optional[int] = 1

    @model_validator(mode="after")
    def check_balanced(self) -> "AccountingEntryCreate":
        total_debit = sum(ln.debit or 0 for ln in self.lines)
        total_credit = sum(ln.credit or 0 for ln in self.lines)
        if round(abs(total_debit - total_credit), 2) > 0.01:
            raise ValueError(
                f"Lançamento desbalanceado: débitos={total_debit:.2f}, créditos={total_credit:.2f}"
            )
        return self

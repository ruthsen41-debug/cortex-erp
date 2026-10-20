from typing import Optional
from pydantic import BaseModel, Field


class ServiceOrderCreate(BaseModel):
    title: str
    contact_id: Optional[int] = None
    description: Optional[str] = ""
    notes: Optional[str] = ""
    equipment: Optional[str] = ""
    serial_number: Optional[str] = ""
    defect_reported: Optional[str] = ""
    services_amount: Optional[float] = 0.0
    parts_amount: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    total_amount: float = Field(default=0.0, ge=0)
    company_id: Optional[int] = 1


class ContractCreate(BaseModel):
    title: str
    contact_id: int
    amount: float = Field(..., gt=0)
    billing_day: Optional[int] = Field(default=10, ge=1, le=31)
    recurrence: Optional[str] = "mensal"
    start_date: Optional[str] = None
    notes: Optional[str] = ""
    company_id: Optional[int] = 1

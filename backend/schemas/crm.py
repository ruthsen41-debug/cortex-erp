from typing import Optional
from pydantic import BaseModel, Field


class DealCreate(BaseModel):
    title: str
    contact_id: Optional[int] = None
    stage: Optional[str] = "prospeccao"
    value: float = Field(default=0.0, ge=0)
    probability: Optional[int] = Field(default=50, ge=0, le=100)
    expected_close_date: Optional[str] = None
    notes: Optional[str] = ""
    company_id: Optional[int] = 1


class DealStageUpdate(BaseModel):
    stage: str

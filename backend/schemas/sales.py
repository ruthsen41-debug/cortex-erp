from typing import Optional, List
from pydantic import BaseModel, Field


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(..., ge=0)
    discount: Optional[float] = 0.0


class SaleCreate(BaseModel):
    type: Optional[str] = "venda"  # venda, orcamento, pdv
    contact_id: Optional[int] = None
    payment_method: Optional[str] = "Pix"
    installments: Optional[int] = 1
    discount: Optional[float] = 0.0
    shipping_amount: Optional[float] = 0.0
    notes: Optional[str] = ""
    items: List[SaleItemCreate] = []
    total_amount: Optional[float] = None
    company_id: Optional[int] = 1

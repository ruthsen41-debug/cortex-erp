from typing import Optional
from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    type: Optional[str] = "produto"  # produto ou servico
    sku: Optional[str] = ""
    barcode: Optional[str] = ""
    unit: Optional[str] = "UN"
    ncm: Optional[str] = ""
    cest: Optional[str] = ""
    cfop: Optional[str] = "5102"
    origem: Optional[int] = 0
    csosn: Optional[str] = "102"
    cost_price: Optional[float] = 0.0
    sale_price: float = Field(..., ge=0)
    stock_current: Optional[float] = 0.0
    stock_min: Optional[float] = 0.0
    company_id: Optional[int] = 1


class StockAdjustRequest(BaseModel):
    new_stock: float = Field(..., ge=0)
    reason: Optional[str] = "Inventário / Ajuste de Estoque"

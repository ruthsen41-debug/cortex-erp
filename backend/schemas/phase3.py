from typing import Optional, List
from pydantic import BaseModel, Field


# --- Tabelas de Preço & Vendedores ---
class PriceTableCreate(BaseModel):
    name: str
    discount_percent: Optional[float] = 0.0
    markup_percent: Optional[float] = 0.0
    active: Optional[int] = 1


class SellerCreate(BaseModel):
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    commission_percent: Optional[float] = 5.0
    active: Optional[int] = 1


# --- Depósitos, Lotes & Variações ---
class WarehouseCreate(BaseModel):
    name: str
    code: str
    location: Optional[str] = ""
    is_default: Optional[int] = 0
    active: Optional[int] = 1


class BatchCreate(BaseModel):
    product_id: int
    warehouse_id: Optional[int] = 1
    batch_number: str
    expiry_date: Optional[str] = None
    manufacturing_date: Optional[str] = None
    quantity: float = Field(default=0.0, ge=0)


class VariantCreate(BaseModel):
    product_id: int
    variant_name: str
    sku: str
    additional_price: Optional[float] = 0.0
    stock_qty: Optional[float] = 0.0
    active: Optional[int] = 1


class StockTransferCreate(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    product_id: int
    quantity: float = Field(..., gt=0)
    notes: Optional[str] = "Transferência entre depósitos"


class InventoryAdjustmentCreate(BaseModel):
    product_id: int
    warehouse_id: Optional[int] = 1
    new_quantity: float = Field(..., ge=0)
    reason: Optional[str] = "Ajuste de inventário físico"


# --- Pedidos de Compra ---
class PurchaseOrderItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    discount: Optional[float] = 0.0


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    payment_terms: Optional[str] = "Boleto 30 dias"
    expected_delivery_date: Optional[str] = None
    notes: Optional[str] = ""
    items: List[PurchaseOrderItemCreate] = []


# --- Devoluções & RMA ---
class ReturnItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    return_to_stock: Optional[int] = 1


class ReturnCreate(BaseModel):
    sale_id: int
    reason: str
    refund_method: Optional[str] = "credito"  # credito, estorno_financeiro
    items: List[ReturnItemCreate] = []


# --- Reajuste de Contratos ---
class ContractAdjustRequest(BaseModel):
    adjustment_percent: float = Field(..., description="Percentual de reajuste ex: 5.5 para 5.5%")
    inflation_index: Optional[str] = "IPCA"


class ContractBatchAdjustRequest(BaseModel):
    adjustment_percent: float = Field(..., description="Percentual de reajuste ex: 4.8")
    inflation_index: Optional[str] = "IPCA"
    contract_ids: Optional[List[int]] = None

from typing import Optional
from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    name: str
    cpf: str
    rg: Optional[str] = ""
    pis_pasep: Optional[str] = ""
    ctps: Optional[str] = ""
    birth_date: Optional[str] = None
    sexo: Optional[str] = "M"
    admission_date: str
    role: str
    cbo: Optional[str] = "111105"
    department: Optional[str] = ""
    salary: float = Field(..., gt=0)
    is_prolabore: Optional[bool] = False
    dependents: int = Field(default=0, ge=0)
    vt_monthly: Optional[float] = 0.0
    esocial_category: Optional[str] = "101"  # 101=CLT
    bank_name: Optional[str] = ""
    bank_agency: Optional[str] = ""
    bank_account: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    cep: Optional[str] = ""
    address: Optional[str] = ""
    matricula: Optional[str] = ""
    notes: Optional[str] = ""
    company_id: Optional[int] = 1


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    salary: Optional[float] = None
    dependents: Optional[int] = None
    vt_monthly: Optional[float] = None
    is_prolabore: Optional[bool] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class PayrollRunCreate(BaseModel):
    competence: str = Field(..., description="YYYY-MM")
    company_id: Optional[int] = 1


class PayrollItemOverride(BaseModel):
    employee_id: int
    extra_earnings: Optional[float] = 0.0
    extra_discounts: Optional[float] = 0.0
    notes: Optional[str] = ""


class TerminationRequest(BaseModel):
    termination_date: str
    termination_type: str = "sem_justa_causa"
    # sem_justa_causa | com_justa_causa | pedido_demissao
    motivo_esocial: Optional[str] = "03"
    # 01=aposentadoria 02=pedido demissão 03=dispensa s/jc 04=dispensa c/jc

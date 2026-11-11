from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .company import router as company_router
from .bank_accounts import router as bank_accounts_router
from .categories import router as categories_router
from .cost_centers import router as cost_centers_router
from .contacts import router as contacts_router
from .products import router as products_router
from .financial import router as financial_router
from .cfo import router as cfo_router
from .ofx import router as ofx_router
from .crm import router as crm_router
from .sales import router as sales_router
from .contracts import router as contracts_router
from .service_orders import router as service_orders_router
from .purchases import router as purchases_router
from .invoices import router as invoices_router
from .reports import router as reports_router
from .payments import router as payments_router
from .collection import router as collection_router
from .cash_flow import router as cash_flow_router
from .sellers import router as sellers_router
from .warehouses import router as warehouses_router
from .purchase_orders import router as purchase_orders_router
from .returns import router as returns_router
from .portal import router as portal_router
from .accountant import router as accountant_router
from .public_api import router as public_api_router
from .webhooks import router as webhooks_router
from .notifications import router as notifications_router
from .system import router as system_router
from .quotes import router as quotes_router
from .open_finance import router as open_finance_router
from .bb import router as bb_router
from .accounting import router as accounting_router
from .dp import router as dp_router
from .patrimony import router as patrimony_router
from .simples import router as simples_router
from .audit import router as audit_router
from .employee_portal import router as employee_portal_router
from .lalur import router as lalur_router
from .honorarios import router as honorarios_router
from .certificates import router as certificates_router
from .nfe_manifest import router as nfe_manifest_router
from .conventions import router as conventions_router
from .dirbi import router as dirbi_router

all_routers = [
    auth_router,
    dashboard_router,
    company_router,
    bank_accounts_router,
    categories_router,
    cost_centers_router,
    contacts_router,
    products_router,
    financial_router,
    cfo_router,
    ofx_router,
    crm_router,
    sales_router,
    contracts_router,
    service_orders_router,
    purchases_router,
    invoices_router,
    reports_router,
    payments_router,
    collection_router,
    cash_flow_router,
    sellers_router,
    warehouses_router,
    purchase_orders_router,
    returns_router,
    portal_router,
    accountant_router,
    public_api_router,
    webhooks_router,
    notifications_router,
    system_router,
    quotes_router,
    open_finance_router,
    bb_router,
    accounting_router,
    dp_router,
    patrimony_router,
    simples_router,
    audit_router,
    employee_portal_router,
    lalur_router,
    honorarios_router,
    certificates_router,
    nfe_manifest_router,
    conventions_router,
    dirbi_router,
]

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
]

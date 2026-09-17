from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from supportcommander.api.routes.audit import router as audit_router
from supportcommander.api.routes.health import router as health_router
from supportcommander.api.routes.tickets import router as tickets_router
from supportcommander.core.constants import PROJECT_NAME, PROJECT_VERSION
from supportcommander.db.mongo import close_database_connection, get_database, ping_database
from supportcommander.mcp_client.client import shutdown_mcp, startup_mcp
from supportcommander.api.routes.llm import router as llm_router
from supportcommander.api.routes.triage import router as triage_router
from supportcommander.api.routes.policies import router as policies_router
from supportcommander.api.routes.rag import router as rag_router
from supportcommander.api.routes.analysis import (
    router as analysis_router,
)
from supportcommander.api.routes.workflows import (
    router as workflows_router,
)
from supportcommander.api.routes.approvals import (
    router as approvals_router,
)
from supportcommander.api.routes.cost_logs import (
    router as cost_logs_router,
)
from supportcommander.api.routes.datasets import (
    router as datasets_router,
)
from supportcommander.api.routes.knowledge_base import (
    router as knowledge_base_router,
)
from supportcommander.services.dataset_service import ensure_dataset_indexes, ensure_user_ticket_indexes


def _ensure_indexes() -> None:
    from pymongo import ASCENDING, IndexModel

    db = get_database()

    db.workflows.create_indexes([
        IndexModel([("workflow_id", ASCENDING)], unique=True, name="workflow_id_unique"),
        IndexModel([("ticket_id", ASCENDING)], name="ticket_id"),
    ])
    db.refunds.create_indexes([
        IndexModel(
            [("order_id", ASCENDING), ("customer_id", ASCENDING), ("status", ASCENDING)],
            unique=True,
            partialFilterExpression={"status": "completed"},
            name="refund_order_completed_unique",
        ),
        IndexModel([("customer_id", ASCENDING)], name="refund_customer_id"),
    ])
    db.replacements.create_indexes([
        IndexModel([("customer_id", ASCENDING)], name="replacement_customer_id"),
    ])
    db.orders.create_indexes([
        IndexModel([("order_id", ASCENDING)], unique=True, name="order_id_unique"),
        IndexModel([("customer_id", ASCENDING)], name="order_customer_id"),
    ])
    db.payments.create_indexes([
        IndexModel([("order_id", ASCENDING)], name="payment_order_id"),
    ])
    db.customers.create_indexes([
        IndexModel([("customer_id", ASCENDING)], unique=True, name="customer_id_unique"),
    ])
    ensure_dataset_indexes()
    ensure_user_ticket_indexes()


@asynccontextmanager
async def lifespan(app: FastAPI,):
    print(f"Starting {PROJECT_NAME} v{PROJECT_VERSION}")
    ping_database()
    print("MongoDB connection verified.")
    _ensure_indexes()
    print("MongoDB indexes ensured.")
    await startup_mcp()
    print("MCP client started.")
    yield
    await shutdown_mcp()
    print("MCP client stopped.")
    close_database_connection()
    print("MongoDB connection closed.")

app = FastAPI(
    title=PROJECT_NAME,
    version=PROJECT_VERSION,
    description=("Autonomous customer-support resolution system."),
    lifespan=lifespan,
)


@app.get("/", tags=["Application"])
async def root() -> dict:
    return {
        "service": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "status": "running",
        "docs": "/docs",
    }


app.include_router(health_router)
app.include_router(tickets_router)
app.include_router(llm_router)
app.include_router(triage_router)
app.include_router(policies_router)
app.include_router(rag_router)
app.include_router(analysis_router)
app.include_router(workflows_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(cost_logs_router)
app.include_router(datasets_router)
app.include_router(knowledge_base_router)

app.mount(
    "/app",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)
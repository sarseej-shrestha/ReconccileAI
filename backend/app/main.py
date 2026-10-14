from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import Settings
from app.db import Database
from app.models import BankTransaction, FinancialException, Invoice, Proposal
from app.schemas import ImportData
from app.services.importing import DomainError, import_data
from app.services.reconciliation import proposal_view, reconcile

FIXTURE = Path(__file__).resolve().parents[2] / "data/synthetic/records.json"


def create_app(settings=None):
    settings = settings or Settings()
    db = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        yield
        db.engine.dispose()

    app = FastAPI(title="ReconcileAI", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Reviewer-Token", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.correlation_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(
            status_code=409,
            content={"detail": "A uniqueness or financial constraint rejected the operation."},
        )

    @app.exception_handler(OperationalError)
    async def unavailable(request, exc):
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable or busy; retry the same operation key."},
        )

    @app.get("/api/health")
    def health():
        with db.session() as session:
            session.execute(select(1))
        return {"status": "ok", "authentication": "simulated"}

    @app.post("/api/import")
    def import_records(data: ImportData, request: Request):
        with db.session(write=True) as session:
            return import_data(session, data, request.state.correlation_id)

    @app.post("/api/demo/load")
    def load_demo(request: Request):
        data = ImportData.model_validate_json(FIXTURE.read_text())
        with db.session(write=True) as session:
            return import_data(session, data, request.state.correlation_id)

    @app.get("/api/invoices")
    def invoices():
        with db.session() as session:
            return list(session.scalars(select(Invoice).order_by(Invoice.id)))

    @app.get("/api/transactions")
    def transactions():
        with db.session() as session:
            return list(session.scalars(select(BankTransaction).order_by(BankTransaction.id)))

    @app.post("/api/reconcile")
    def run_reconciliation(request: Request):
        with db.session(write=True) as session:
            return reconcile(session, request.state.correlation_id)

    @app.get("/api/proposals")
    def proposals():
        with db.session() as session:
            return [
                proposal_view(session, p)
                for p in session.scalars(select(Proposal).order_by(Proposal.created_at))
            ]

    @app.get("/api/exceptions")
    def exceptions():
        with db.session() as session:
            return list(
                session.scalars(select(FinancialException).order_by(FinancialException.created_at))
            )

    return app


app = create_app()

from sqlalchemy import select

from app.models import BankTransaction, Invoice
from app.schemas import ImportData
from app.services.audit import audit


class DomainError(Exception):
    def __init__(self, message, status=409):
        self.message = message
        self.status = status
        super().__init__(message)


def import_data(session, data: ImportData, correlation_id: str):
    counts = {"invoices": 0, "transactions": 0, "unchanged": 0}
    for model, rows, key in [
        (Invoice, data.invoices, "invoices"),
        (BankTransaction, data.transactions, "transactions"),
    ]:
        for item in rows:
            values = item.model_dump()
            existing = session.get(model, item.id)
            if existing:
                if any(getattr(existing, k) != v for k, v in values.items()):
                    raise DomainError(
                        f"Conflicting import for {item.id}; existing evidence is preserved"
                    )
                counts["unchanged"] += 1
                continue
            unique_field = "invoice_number" if model is Invoice else "external_reference"
            if session.scalar(
                select(model).where(getattr(model, unique_field) == values[unique_field])
            ):
                raise DomainError(f"Duplicate {unique_field}: {values[unique_field]}")
            session.add(model(**values))
            session.flush()
            counts[key] += 1
    audit(
        session, "data_imported", "dataset", "import", after=counts, correlation_id=correlation_id
    )
    return counts

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
Cents = Annotated[int, Field(strict=True, gt=0, le=1_000_000_000_000)]
Currency = Annotated[str, Field(pattern=r"^(USD|EUR|GBP|CAD)$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvoiceInput(StrictModel):
    id: Identifier
    invoice_number: Annotated[str, Field(pattern=r"^INV-[A-Z0-9]+$", max_length=80)]
    counterparty: Annotated[str, Field(min_length=1, max_length=200)]
    amount_cents: Cents
    currency: Currency
    issue_date: date
    due_date: date
    kind: Literal["receivable", "payable"] = "receivable"

    @model_validator(mode="after")
    def valid_dates(self):
        if self.due_date < self.issue_date:
            raise ValueError("due_date precedes issue_date")
        return self


class TransactionInput(StrictModel):
    id: Identifier
    external_reference: Identifier
    counterparty: Annotated[str, Field(min_length=1, max_length=200)]
    amount_cents: Annotated[int, Field(strict=True, ge=-1_000_000_000_000, le=1_000_000_000_000)]
    currency: Currency
    date: date
    description: Annotated[str, Field(max_length=2000)]
    source: Annotated[str, Field(min_length=1, max_length=80)]

    @model_validator(mode="after")
    def nonzero(self):
        if self.amount_cents == 0:
            raise ValueError("amount_cents must be nonzero")
        return self


class ImportData(StrictModel):
    invoices: list[InvoiceInput] = Field(default_factory=list, max_length=1000)
    transactions: list[TransactionInput] = Field(default_factory=list, max_length=2000)


class ReviewRequest(StrictModel):
    decision: Literal["APPROVED", "REJECTED"]
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class ApplyRequest(StrictModel):
    version: int = Field(ge=1)

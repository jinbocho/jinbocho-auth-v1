from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoanReminderRequest(BaseModel):
    """Internal request from catalog-service — a loan it owns is due soon
    and the family that lent the book should be told."""
    family_id: UUID = Field(description="Family that owns the book")
    book_title: str = Field(description="Title of the loaned book")
    borrower_name: str = Field(description="Name of the external borrower")
    due_date: datetime = Field(description="When the loan is due back")

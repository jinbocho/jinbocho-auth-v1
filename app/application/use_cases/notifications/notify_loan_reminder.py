from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.repositories import UserRepository
from app.infrastructure.email import EmailSender

_NOTIFIABLE_ROLES = ("admin", "editor")


@dataclass
class NotifyLoanReminderInput:
    family_id: UUID
    book_title: str
    borrower_name: str
    due_date: datetime


class NotifyLoanReminderUseCase:
    """Emails the family's admins/editors that a loan they made is due soon.

    The borrower is external (just a name, no account) — there's no one else
    to notify. A family with no admin/editor members is a silent no-op."""

    def __init__(self, user_repo: UserRepository, email_sender: EmailSender) -> None:
        self._user_repo = user_repo
        self._email_sender = email_sender

    async def execute(self, input: NotifyLoanReminderInput) -> None:
        users = await self._user_repo.find_by_family(input.family_id)
        recipients = [u for u in users if u.is_active and u.role in _NOTIFIABLE_ROLES]

        for user in recipients:
            self._email_sender.send_loan_reminder(
                to_email=user.email,
                book_title=input.book_title,
                borrower_name=input.borrower_name,
                due_date=input.due_date,
                language=user.language,
            )

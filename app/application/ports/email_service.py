from datetime import datetime
from typing import Protocol


class EmailService(Protocol):
    """Port for outbound transactional email. Transport and rendering are
    infrastructure details; use cases depend only on this abstraction."""

    def send_password_setup_link(
        self,
        to_email: str,
        link: str,
        purpose: str = "reset",
        language: str | None = None,
    ) -> None: ...

    def send_welcome_email(
        self,
        to_email: str,
        library_name: str,
        link: str,
        language: str | None = None,
    ) -> None: ...

    def send_library_invite_email(
        self,
        to_email: str,
        library_name: str,
        inviter_name: str,
        link: str,
        language: str | None = None,
    ) -> None: ...

    def send_loan_reminder(
        self,
        to_email: str,
        book_title: str,
        borrower_name: str,
        due_date: datetime,
        language: str | None = None,
    ) -> None: ...

    def send_email_change_verification(
        self,
        to_email: str,
        link: str,
        language: str | None = None,
    ) -> None: ...

    def send_email_change_requested_notice(
        self,
        to_email: str,
        new_email: str,
        reset_link: str,
        language: str | None = None,
    ) -> None: ...

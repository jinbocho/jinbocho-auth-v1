from datetime import datetime, timezone
from uuid import uuid4

from app.application.use_cases.notifications import NotifyLoanReminderInput, NotifyLoanReminderUseCase
from app.domain.entities import User, UserRole


def _make_user(library_id, role, is_active=True, email="x@example.com", language=None) -> User:
    return User(
        library_id=library_id,
        email=email,
        password_hash="hashed",
        full_name="Test User",
        role=UserRole(role),
        is_active=is_active,
        language=language,
    )


async def test_notifies_admin_and_editor_but_not_viewer_or_inactive(mock_user_repo, fake_email_sender):
    library_id = uuid4()
    admin = await mock_user_repo.save(_make_user(library_id, "admin", email="admin@example.com"))
    editor = await mock_user_repo.save(_make_user(library_id, "editor", email="editor@example.com"))
    await mock_user_repo.save(_make_user(library_id, "viewer", email="viewer@example.com"))
    await mock_user_repo.save(_make_user(library_id, "admin", is_active=False, email="inactive@example.com"))
    await mock_user_repo.save(_make_user(uuid4(), "admin", email="other-library@example.com"))

    use_case = NotifyLoanReminderUseCase(mock_user_repo, fake_email_sender)
    await use_case.execute(
        NotifyLoanReminderInput(
            library_id=library_id,
            book_title="Dune",
            borrower_name="Mario",
            due_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
    )

    notified = {s["to_email"] for s in fake_email_sender.sent}
    assert notified == {admin.email, editor.email}
    assert all(s["book_title"] == "Dune" and s["borrower_name"] == "Mario" for s in fake_email_sender.sent)


async def test_no_recipients_is_a_silent_no_op(mock_user_repo, fake_email_sender):
    library_id = uuid4()
    await mock_user_repo.save(_make_user(library_id, "viewer"))

    use_case = NotifyLoanReminderUseCase(mock_user_repo, fake_email_sender)
    await use_case.execute(
        NotifyLoanReminderInput(
            library_id=library_id,
            book_title="Dune",
            borrower_name="Mario",
            due_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
    )

    assert fake_email_sender.sent == []

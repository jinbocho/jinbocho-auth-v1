from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_email_sender, get_user_repository
from app.api.v1.schemas.notification_schemas import LoanReminderRequest
from app.application.ports import EmailService
from app.application.use_cases.notifications import NotifyLoanReminderInput, NotifyLoanReminderUseCase
from app.domain.repositories import UserRepository

router = APIRouter()


@router.post(
    "/loan-reminder",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Notify a library that a loan is due soon",
    description=(
        "Internal, service-to-service endpoint (catalog-service calls this) — "
        "not reachable with a user JWT, only with the shared internal token."
    ),
)
async def notify_loan_reminder(
    request: LoanReminderRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    email_sender: EmailService = Depends(get_email_sender),
) -> None:
    use_case = NotifyLoanReminderUseCase(user_repo, email_sender)
    await use_case.execute(
        NotifyLoanReminderInput(
            library_id=request.library_id,
            book_title=request.book_title,
            borrower_name=request.borrower_name,
            due_date=request.due_date,
        )
    )

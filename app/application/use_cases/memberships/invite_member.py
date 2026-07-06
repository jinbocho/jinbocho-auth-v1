import asyncio
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.application.ports import EmailService
from app.application.services import TokenService, issue_password_setup_link
from app.domain.entities import LibraryMembership, MembershipStatus, User, UserRole
from app.domain.exceptions import ForbiddenError
from app.domain.repositories import LibraryRepository, MembershipRepository, PasswordResetTokenRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)


@dataclass
class InviteMemberInput:
    library_id: UUID
    invited_by: UUID
    email: str
    full_name: str | None
    role: UserRole


@dataclass
class InviteMemberOutput:
    membership_id: UUID
    user_id: UUID
    email: str
    role: UserRole
    status: MembershipStatus
    is_new_account: bool


class InviteMemberUseCase:
    """Adds a member to a library. Branches on whether the email already has
    an account elsewhere in the system (accounts are global — `users.email`
    is unique):

    - Existing account: a new `invited` membership is created for their
      existing user id. No password flow — they already have credentials,
      they just need to accept (see AcceptInvitationUseCase). They're emailed
      a plain notification (no token/link beyond the login page) telling them
      who invited them and to which library.
    - New account: identical to the legacy single-library invite (creates
      the User row and emails a password-setup link), plus the membership
      row this whole feature is about.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        library_repo: LibraryRepository,
        reset_token_repo: PasswordResetTokenRepository,
        email_sender: EmailService,
        token_service: TokenService,
        password_hasher: PasswordHasher,
        invite_expire_minutes: int,
        frontend_base_url: str,
    ):
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._library_repo = library_repo
        self._reset_token_repo = reset_token_repo
        self._email_sender = email_sender
        self._token_service = token_service
        self._password_hasher = password_hasher
        self._invite_expire_minutes = invite_expire_minutes
        self._frontend_base_url = frontend_base_url

    async def execute(self, input: InviteMemberInput) -> InviteMemberOutput:
        existing_user = await self._user_repo.find_by_email(input.email)

        if existing_user is not None:
            already_member = await self._membership_repo.find_by_user_and_library(existing_user.id, input.library_id)
            if already_member is not None and already_member.status != MembershipStatus.REVOKED:
                raise ForbiddenError("This person is already a member of this library")

            # Re-inviting after a decline/removal: reuse the existing (revoked)
            # row rather than inserting a new one — uq_membership_user_library
            # is a UNIQUE(user_id, library_id) constraint, so a second row for
            # the same pair would violate it even though the old one is inert.
            membership = already_member or LibraryMembership(
                user_id=existing_user.id, library_id=input.library_id, role=input.role,
            )
            membership.role = input.role
            membership.status = MembershipStatus.INVITED
            membership.invited_by = input.invited_by
            membership.invited_at = datetime.now(timezone.utc)
            membership.joined_at = None
            saved = await self._membership_repo.save(membership)

            inviter = await self._user_repo.find_by_id(input.invited_by)
            library = await self._library_repo.find_by_id(input.library_id)
            if inviter is not None and library is not None:
                await asyncio.to_thread(
                    self._email_sender.send_library_invite_email,
                    existing_user.email,
                    library.name,
                    inviter.full_name,
                    f"{self._frontend_base_url}/login",
                    language=existing_user.language.value if existing_user.language else None,
                )

            logger.info(
                "Existing user %s invited to library %s with role %s", existing_user.id, input.library_id, input.role
            )
            return InviteMemberOutput(
                membership_id=saved.id,
                user_id=existing_user.id,
                email=existing_user.email,
                role=saved.role,
                status=saved.status,
                is_new_account=False,
            )

        new_user = User(
            library_id=input.library_id,
            email=input.email,
            password_hash=self._password_hasher.hash(secrets.token_urlsafe(32)),
            full_name=input.full_name or input.email,
            role=input.role,
            last_selected_library_id=input.library_id,
        )
        saved_user = await self._user_repo.save(new_user)

        membership = LibraryMembership(
            user_id=saved_user.id,
            library_id=input.library_id,
            role=input.role,
            status=MembershipStatus.ACTIVE,
            invited_by=input.invited_by,
            invited_at=datetime.now(timezone.utc),
            joined_at=datetime.now(timezone.utc),
        )
        saved_membership = await self._membership_repo.save(membership)

        await issue_password_setup_link(
            saved_user,
            purpose="invite",
            expire_minutes=self._invite_expire_minutes,
            reset_token_repo=self._reset_token_repo,
            email_sender=self._email_sender,
            token_service=self._token_service,
            frontend_base_url=self._frontend_base_url,
        )
        logger.info("New user %s invited to library %s with role %s", saved_user.id, input.library_id, input.role)
        return InviteMemberOutput(
            membership_id=saved_membership.id,
            user_id=saved_user.id,
            email=saved_user.email,
            role=saved_membership.role,
            status=saved_membership.status,
            is_new_account=True,
        )

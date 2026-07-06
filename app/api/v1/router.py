from fastapi import APIRouter, Depends

from app.api.dependencies import verify_internal_token
from app.api.v1.endpoints import auth, context, libraries, internal_notifications, memberships, users

router = APIRouter()
router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}}
)
router.include_router(
    context.router,
    prefix="/auth/context",
    tags=["context"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}}
)
router.include_router(
    libraries.router,
    prefix="/libraries",
    tags=["libraries"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Library not found"}}
)
router.include_router(
    memberships.router,
    prefix="/libraries",
    tags=["members"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Membership not found"}}
)
router.include_router(
    users.router,
    prefix="/users",
    tags=["users"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "User not found"}}
)
router.include_router(
    internal_notifications.router,
    prefix="/internal/notifications",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
    responses={401: {"description": "Unauthorized"}}
)

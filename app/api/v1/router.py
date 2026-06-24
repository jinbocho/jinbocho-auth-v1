from fastapi import APIRouter, Depends

from app.api.dependencies import verify_internal_token
from app.api.v1.endpoints import auth, families, internal_notifications, users

router = APIRouter()
router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}}
)
router.include_router(
    families.router,
    prefix="/families",
    tags=["families"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Family not found"}}
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

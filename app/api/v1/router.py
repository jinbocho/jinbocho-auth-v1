from fastapi import APIRouter

from app.api.v1.endpoints import auth, families, users

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

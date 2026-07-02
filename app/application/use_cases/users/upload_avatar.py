import base64
import io
import logging
from dataclasses import dataclass
from uuid import UUID

from PIL import Image

from app.domain.repositories import UserRepository

logger = logging.getLogger(__name__)

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_RAW_BYTES = 2 * 1024 * 1024  # 2 MB
_TARGET_PX = 200


@dataclass
class UploadAvatarInput:
    user_id: UUID
    family_id: UUID
    image_bytes: bytes
    content_type: str


class UploadAvatarUseCase:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, inp: UploadAvatarInput) -> str:
        if inp.content_type not in _ALLOWED_TYPES:
            raise ValueError(f"Unsupported image type: {inp.content_type}")
        if len(inp.image_bytes) > _MAX_RAW_BYTES:
            raise ValueError("Image too large (max 2 MB)")

        user = await self._user_repo.find_by_id(inp.user_id)
        if not user or user.family_id != inp.family_id:
            raise LookupError("User not found")

        img = Image.open(io.BytesIO(inp.image_bytes)).convert("RGB")
        side = min(img.width, img.height)
        left = (img.width - side) // 2
        top = (img.height - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((_TARGET_PX, _TARGET_PX), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=80)
        data_url = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()

        user.avatar_url = data_url
        await self._user_repo.save(user)
        logger.info("Avatar uploaded for user %s", inp.user_id)
        return data_url

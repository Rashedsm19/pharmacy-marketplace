"""
Document storage for compliance paperwork (CR extract, pharmacy licence).

Files are validated before anything touches disk: an oversized or wrong-typed
upload is rejected, and the stored name is generated rather than taken from the
client so a crafted filename cannot escape the storage directory.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from config import settings

logger = logging.getLogger("api.storage")

# Extension is derived from the declared type, never from the client filename.
ALLOWED_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

# A signature check, because Content-Type is client-supplied and trivially faked.
MAGIC_PREFIXES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".jpg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


class StorageService:
    def __init__(self) -> None:
        self.root = Path(settings.STORAGE_LOCAL_PATH)

    async def save_document(
        self, file: UploadFile, organization_id: uuid.UUID, doc_type: str
    ) -> str:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="نوع الملف غير مدعوم — المسموح: PDF أو JPG أو PNG",
            )

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        content = await file.read(max_bytes + 1)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="الملف فارغ"
            )
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"حجم الملف يتجاوز {settings.MAX_UPLOAD_SIZE_MB} ميجابايت",
            )

        suffix = ALLOWED_TYPES[file.content_type]
        expected = MAGIC_PREFIXES[suffix]
        if not any(content.startswith(prefix) for prefix in expected):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="محتوى الملف لا يطابق نوعه المعلن",
            )

        if settings.STORAGE_BACKEND != "local":
            # S3 is declared in config but not wired; fail loudly instead of
            # pretending the document was stored.
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"STORAGE_BACKEND={settings.STORAGE_BACKEND} غير مُفعّل",
            )

        target_dir = self.root / str(organization_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        name = f"{doc_type}-{uuid.uuid4().hex}{suffix}"
        (target_dir / name).write_bytes(content)

        logger.info(
            "Stored %s document for org=%s (%d bytes)", doc_type, organization_id, len(content)
        )
        return f"{organization_id}/{name}"

    def resolve(self, stored_path: str) -> Path:
        """Map a stored reference back to a real file, refusing traversal."""
        candidate = (self.root / stored_path).resolve()
        if not str(candidate).startswith(str(self.root.resolve())):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="مسار غير صالح")
        if not candidate.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الملف غير موجود")
        return candidate


storage_service = StorageService()

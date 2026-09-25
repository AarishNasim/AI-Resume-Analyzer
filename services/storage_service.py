"""Firebase Cloud Storage operations for Resume Atlas files."""

from __future__ import annotations

import io
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from services.firebase_config import get_storage_bucket


ALLOWED_EXTENSIONS = {"pdf", "docx"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class StorageServiceError(RuntimeError):
    """Raised when a Cloud Storage operation fails."""


def _storage_path(user_id: str, filename: str) -> str:
    safe_user_id = secure_filename(str(user_id))
    safe_filename = secure_filename(filename)
    extension = Path(safe_filename).suffix.lower().lstrip(".")
    if not safe_user_id or not safe_filename or extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF and DOCX files are allowed.")
    return f"users/{safe_user_id}/resumes/{uuid.uuid4().hex}.{extension}"


def upload_resume_file(
    file: FileStorage | io.BufferedIOBase,
    *,
    user_id: str,
    filename: str | None = None,
    content_type: str | None = None,
) -> dict[str, str]:
    """Upload a PDF/DOCX stream directly to Firebase Cloud Storage."""
    source_name = filename or getattr(file, "filename", "")
    if not source_name:
        raise ValueError("filename is required")
    resolved_content_type = content_type or getattr(file, "mimetype", "")
    if resolved_content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported resume MIME type.")
    path = _storage_path(user_id, source_name)
    try:
        blob = get_storage_bucket().blob(path)
        blob.upload_from_file(file, content_type=resolved_content_type)
        return {"storage_path": path, "content_type": resolved_content_type}
    except Exception as exc:
        raise StorageServiceError("Could not upload the resume to Firebase Storage.") from exc


def upload_resume_bytes(
    content: bytes,
    *,
    user_id: str,
    filename: str,
    content_type: str,
) -> dict[str, str]:
    """Upload generated PDF/DOCX bytes without writing them to local disk."""
    return upload_resume_file(
        io.BytesIO(content),
        user_id=user_id,
        filename=filename,
        content_type=content_type,
    )


def generate_download_url(storage_path: str, *, expires_in_seconds: int = 900) -> str:
    """Generate a temporary V4 signed download URL."""
    if not storage_path or expires_in_seconds <= 0:
        raise ValueError("storage_path and a positive expiration are required")
    try:
        blob = get_storage_bucket().blob(storage_path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_in_seconds),
            method="GET",
        )
    except Exception as exc:
        raise StorageServiceError("Could not generate a download URL.") from exc


def delete_storage_file(storage_path: str) -> None:
    """Delete a stored resume; deleting a missing object is treated as success."""
    if not storage_path:
        return
    try:
        get_storage_bucket().blob(storage_path).delete()
    except Exception as exc:
        if "not found" not in str(exc).lower():
            raise StorageServiceError("Could not delete the stored resume.") from exc
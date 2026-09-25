"""Secure, ephemeral processing for PDF and DOCX uploads."""

from __future__ import annotations

import os
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from services.resume_parser import extract_text


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "docx"}
ALLOWED_MIME_TYPES = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
}


class UploadValidationError(ValueError):
    """Raised when an uploaded resume fails an allow-list validation."""


class UploadProcessingError(RuntimeError):
    """Raised when a validated resume cannot be parsed."""


def _extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadValidationError("Only PDF and DOCX files are allowed.")
    return suffix


def _validate_mime(file: FileStorage, extension: str) -> None:
    content_type = (file.mimetype or file.content_type or "").split(";", 1)[0].lower()
    if content_type not in ALLOWED_MIME_TYPES[extension]:
        raise UploadValidationError(
            f"The uploaded .{extension} file has an unsupported MIME type."
        )


def _validate_signature(path: str, extension: str) -> None:
    with open(path, "rb") as stream:
        header = stream.read(8)

    if extension == "pdf" and not header.startswith(b"%PDF-"):
        raise UploadValidationError("The file is not a valid PDF document.")

    if extension == "docx":
        if not header.startswith(b"PK"):
            raise UploadValidationError("The file is not a valid DOCX document.")
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                required = {"[Content_Types].xml", "word/document.xml"}
                if not required.issubset(names) or archive.testzip() is not None:
                    raise UploadValidationError("The DOCX archive is invalid.")
        except zipfile.BadZipFile as exc:
            raise UploadValidationError("The DOCX archive is invalid.") from exc


def cleanup_upload(path: str | os.PathLike[str] | None) -> None:
    """Delete a temporary upload if it still exists; safe to call repeatedly."""
    if not path:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def process_uploaded_file(
    uploaded_file: FileStorage,
    *,
    parser: Callable[[str], str] = extract_text,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> dict[str, Any]:
    """Validate, parse, and immediately delete an uploaded resume.

    The parser receives only the temporary path and must return extracted text.
    The path is removed in a ``finally`` block even when validation or parsing
    raises an exception.  The returned filename is sanitized and never points
    to a persisted upload location.
    """
    if not isinstance(uploaded_file, FileStorage):
        raise UploadValidationError("An uploaded file is required.")
    if not uploaded_file.filename:
        raise UploadValidationError("An uploaded file is required.")

    filename = secure_filename(uploaded_file.filename)
    extension = _extension(filename)
    _validate_mime(uploaded_file, extension)
    temporary_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=f".{extension}",
            prefix="resume-atlas-",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            uploaded_file.save(temporary_file)

        size = os.path.getsize(temporary_path)
        if size == 0:
            raise UploadValidationError("The uploaded file is empty.")
        if size > max_bytes:
            raise UploadValidationError("The uploaded file exceeds the 5 MB limit.")

        _validate_signature(temporary_path, extension)
        try:
            text = parser(temporary_path)
        except Exception as exc:
            raise UploadProcessingError("The uploaded resume could not be parsed.") from exc

        text = text.strip() if isinstance(text, str) else ""
        if not text:
            raise UploadProcessingError("The uploaded resume contains no readable text.")
        return {"filename": filename, "extension": extension, "text": text, "size": size}
    finally:
        cleanup_upload(temporary_path)
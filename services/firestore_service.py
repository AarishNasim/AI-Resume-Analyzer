"""Firestore persistence operations for Resume Atlas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.firebase_config import get_firestore


USERS_COLLECTION = "users"
RESUMES_COLLECTION = "resumes"
SCAN_HISTORY_COLLECTION = "scan_history"


class FirestoreServiceError(RuntimeError):
    """Raised when a Firestore operation fails."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require(value: Any, name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _username_key(username: str) -> str:
    return _require(username, "username").casefold()


def _document_data(snapshot: Any) -> dict[str, Any] | None:
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    data["id"] = snapshot.id
    return data


def save_user_account(
    user_id: str,
    email: str,
    *,
    username: str | None = None,
    password_hash: str | None = None,
    email_verified: bool = False,
    profile: dict[str, Any] | None = None,
    auth_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or update a Firestore user record; passwords are never stored."""
    user_id = _require(user_id, "user_id")
    email = _require(email, "email").lower()
    firestore = get_firestore()
    reference = firestore.collection(USERS_COLLECTION).document(user_id)
    try:
        current = reference.get().to_dict() or {}
        payload = {
            "email": email,
            "username": username or current.get("username", ""),
            "username_lower": _username_key(username or current.get("username", user_id)),
            "password_hash": password_hash or current.get("password_hash", ""),
            "email_verified": bool(email_verified or current.get("email_verified", False)),
            "profile": profile or current.get("profile", {}),
            "auth_state": auth_state or current.get("auth_state", {}),
            "updated_at": _now(),
            "created_at": current.get("created_at", _now()),
        }
        reference.set(payload, merge=True)
        payload["id"] = user_id
        return payload
    except Exception as exc:
        raise FirestoreServiceError("Could not save the user account.") from exc


def get_user_by_username(username: str) -> dict[str, Any] | None:
    username_lower = _username_key(username)
    try:
        query = get_firestore().collection(USERS_COLLECTION).where(
            "username_lower", "==", username_lower
        ).limit(1)
        return next((_document_data(snapshot) for snapshot in query.stream()), None)
    except Exception as exc:
        raise FirestoreServiceError("Could not look up the username.") from exc


def get_user_by_email(email: str) -> dict[str, Any] | None:
    email_lower = _require(email, "email").lower()
    try:
        query = get_firestore().collection(USERS_COLLECTION).where(
            "email", "==", email_lower
        ).limit(1)
        return next((_document_data(snapshot) for snapshot in query.stream()), None)
    except Exception as exc:
        raise FirestoreServiceError("Could not look up the email address.") from exc


def update_user_password(user_id: str, password_hash: str) -> None:
    user_id = _require(user_id, "user_id")
    password_hash = _require(password_hash, "password_hash")
    try:
        get_firestore().collection(USERS_COLLECTION).document(user_id).set(
            {"password_hash": password_hash, "updated_at": _now()}, merge=True
        )
    except Exception as exc:
        raise FirestoreServiceError("Could not update the password.") from exc


def get_user_account(user_id: str) -> dict[str, Any] | None:
    user_id = _require(user_id, "user_id")
    try:
        return _document_data(get_firestore().collection(USERS_COLLECTION).document(user_id).get())
    except Exception as exc:
        raise FirestoreServiceError("Could not retrieve the user account.") from exc


def update_auth_state(user_id: str, auth_state: dict[str, Any]) -> None:
    user_id = _require(user_id, "user_id")
    if not isinstance(auth_state, dict):
        raise TypeError("auth_state must be a dictionary")
    try:
        get_firestore().collection(USERS_COLLECTION).document(user_id).set(
            {"auth_state": auth_state, "updated_at": _now()}, merge=True
        )
    except Exception as exc:
        raise FirestoreServiceError("Could not update authentication state.") from exc


def save_resume_scan(
    user_id: str,
    resume_data: dict[str, Any],
    scan_data: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Save a resume and its scan result in separate top-level collections."""
    user_id = _require(user_id, "user_id")
    if not isinstance(resume_data, dict):
        raise TypeError("resume_data must be a dictionary")
    if scan_data is not None and not isinstance(scan_data, dict):
        raise TypeError("scan_data must be a dictionary")

    now = _now()
    resume_reference = get_firestore().collection(RESUMES_COLLECTION).document()
    resume_payload = {
        "user_id": user_id,
        "title": str(resume_data.get("title") or "Untitled resume").strip(),
        "raw_text": str(resume_data.get("raw_text") or ""),
        "parsed_json": resume_data.get("parsed_json") or {},
        "storage_path": resume_data.get("storage_path"),
        "created_at": now,
        "updated_at": now,
    }
    try:
        batch = get_firestore().batch()
        batch.set(resume_reference, resume_payload)
        scan_id = ""
        if scan_data is not None:
            scan_reference = get_firestore().collection(SCAN_HISTORY_COLLECTION).document()
            scan_id = scan_reference.id
            batch.set(
                scan_reference,
                {
                    "resume_id": resume_reference.id,
                    "user_id": user_id,
                    "overall_score": scan_data.get("overall_score"),
                    "category_scores_json": scan_data.get("category_scores_json")
                    or scan_data.get("category_scores")
                    or {},
                    "recommendations_json": scan_data.get("recommendations_json")
                    or scan_data.get("recommendations")
                    or [],
                    "created_at": now,
                },
            )
        batch.commit()
        return {"resume_id": resume_reference.id, "scan_id": scan_id}
    except Exception as exc:
        raise FirestoreServiceError("Could not save the resume and scan result.") from exc


def get_user_resumes(user_id: str) -> list[dict[str, Any]]:
    user_id = _require(user_id, "user_id")
    try:
        query = get_firestore().collection(RESUMES_COLLECTION).where("user_id", "==", user_id)
        return [{**(snapshot.to_dict() or {}), "id": snapshot.id} for snapshot in query.stream()]
    except Exception as exc:
        raise FirestoreServiceError("Could not retrieve user resumes.") from exc


def get_scan_details(scan_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    scan_id = _require(scan_id, "scan_id")
    try:
        result = _document_data(
            get_firestore().collection(SCAN_HISTORY_COLLECTION).document(scan_id).get()
        )
        if result and user_id and result.get("user_id") != user_id:
            return None
        return result
    except Exception as exc:
        raise FirestoreServiceError("Could not retrieve scan details.") from exc


def delete_resume(resume_id: str, user_id: str) -> None:
    """Delete a user's resume and associated scan history."""
    resume_id = _require(resume_id, "resume_id")
    user_id = _require(user_id, "user_id")
    firestore = get_firestore()
    try:
        resume_reference = firestore.collection(RESUMES_COLLECTION).document(resume_id)
        resume = _document_data(resume_reference.get())
        if not resume or resume.get("user_id") != user_id:
            return
        for scan in firestore.collection(SCAN_HISTORY_COLLECTION).where(
            "resume_id", "==", resume_id
        ).stream():
            scan.reference.delete()
        resume_reference.delete()
    except Exception as exc:
        raise FirestoreServiceError("Could not delete the resume.") from exc
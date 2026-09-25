"""Lazy, environment-based Firebase Admin SDK initialization."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class FirebaseConfigurationError(RuntimeError):
    """Raised when Firebase credentials or configuration are unavailable."""


_firebase_app: Any | None = None
firestore_db: Any | None = None
storage_bucket: Any | None = None

# Convenient aliases for callers that prefer the conventional Firebase names.
db: Any | None = None
bucket: Any | None = None


def _service_account_credentials() -> Any:
    try:
        from firebase_admin import credentials
    except ImportError as exc:
        raise FirebaseConfigurationError(
            "firebase-admin is not installed. Add it to requirements.txt."
        ) from exc

    credentials_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    credentials_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    google_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

    if credentials_json:
        try:
            service_account_info = json.loads(credentials_json)
        except json.JSONDecodeError as exc:
            raise FirebaseConfigurationError(
                "FIREBASE_SERVICE_ACCOUNT_JSON must contain valid JSON."
            ) from exc
        if not isinstance(service_account_info, dict):
            raise FirebaseConfigurationError(
                "FIREBASE_SERVICE_ACCOUNT_JSON must contain an object."
            )
        return credentials.Certificate(service_account_info)

    path = credentials_path or google_credentials_path
    if path:
        if not Path(path).is_file():
            raise FirebaseConfigurationError(f"Firebase credential file not found: {path}")
        return credentials.Certificate(path)

    raise FirebaseConfigurationError(
        "Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_PATH."
    )


def initialize_firebase() -> tuple[Any, Any]:
    """Initialize Firebase once and return the Firestore client and Storage bucket."""
    global _firebase_app, firestore_db, storage_bucket, db, bucket
    if firestore_db is not None and storage_bucket is not None:
        return firestore_db, storage_bucket

    try:
        import firebase_admin
        from firebase_admin import firestore, storage
    except ImportError as exc:
        raise FirebaseConfigurationError(
            "firebase-admin is not installed. Add it to requirements.txt."
        ) from exc

    try:
        _firebase_app = firebase_admin.get_app()
    except ValueError:
        options: dict[str, Any] = {}
        project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
        storage_bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
        if project_id:
            options["projectId"] = project_id
        if storage_bucket_name:
            options["storageBucket"] = storage_bucket_name
        try:
            _firebase_app = firebase_admin.initialize_app(
                _service_account_credentials(), options or None
            )
        except Exception as exc:
            raise FirebaseConfigurationError(
                "Firebase Admin SDK initialization failed."
            ) from exc

    try:
        firestore_db = firestore.client(app=_firebase_app)
        storage_bucket = storage.bucket(app=_firebase_app)
    except Exception as exc:
        raise FirebaseConfigurationError(
            "Could not create Firestore or Cloud Storage clients."
        ) from exc
    db = firestore_db
    bucket = storage_bucket
    return firestore_db, storage_bucket


def get_firestore() -> Any:
    """Return the initialized Firestore client."""
    return initialize_firebase()[0]


def get_storage_bucket() -> Any:
    """Return the initialized Firebase Storage bucket."""
    return initialize_firebase()[1]
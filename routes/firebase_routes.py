"""Example Flask routes backed by Firestore and Firebase Storage."""

from flask import Blueprint, jsonify, request, session

from services.firestore_service import (
    FirestoreServiceError,
    get_scan_details,
    get_user_resumes,
    save_resume_scan,
)


firebase_bp = Blueprint("firebase", __name__, url_prefix="/api/firebase")


def _current_user_id() -> str | None:
    return str(session["user_id"]) if session.get("user_id") else None


@firebase_bp.get("/resumes")
def firebase_resumes():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Authentication required."}), 401
    try:
        return jsonify({"resumes": get_user_resumes(user_id)})
    except FirestoreServiceError as exc:
        return jsonify({"error": str(exc)}), 503


@firebase_bp.post("/resumes/scan")
def firebase_save_resume_scan():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Authentication required."}), 401
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("resume"), dict):
        return jsonify({"error": "resume must be an object."}), 400
    try:
        result = save_resume_scan(user_id, payload["resume"], payload.get("scan"))
        return jsonify(result), 201
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except FirestoreServiceError as exc:
        return jsonify({"error": str(exc)}), 503


@firebase_bp.get("/scans/<scan_id>")
def firebase_scan_details(scan_id: str):
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Authentication required."}), 401
    try:
        result = get_scan_details(scan_id, user_id)
        if result is None:
            return jsonify({"error": "Scan not found."}), 404
        return jsonify(result)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except FirestoreServiceError as exc:
        return jsonify({"error": str(exc)}), 503
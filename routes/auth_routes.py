import re
import time
import uuid

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, db
from services.firestore_service import (
    FirestoreServiceError,
    get_user_by_email,
    get_user_by_username,
    save_user_account,
    update_user_password,
)
from services.otp_service import (
    OTPConfigurationError,
    OTPDeliveryError,
    OTPRateLimitError,
    send_otp,
    verify_otp,
)


auth_bp = Blueprint("auth", __name__)
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
RESET_SESSION_TTL_SECONDS = 5 * 60


def _payload() -> dict:
    return request.get_json(silent=True) or request.form.to_dict()


def _wants_json() -> bool:
    return request.is_json or request.path.startswith("/api/")


def _firebase_backend() -> bool:
    return current_app.config.get("DATA_BACKEND") == "firebase"


def _valid_username(username: str) -> bool:
    return bool(USERNAME_PATTERN.fullmatch(str(username or "").strip()))


def _valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(str(email or "").strip().lower()))


def _find_user_by_username(username: str):
    if _firebase_backend():
        return get_user_by_username(username)
    return db.session.scalar(
        db.select(User).where(func.lower(User.username) == str(username).strip().casefold())
    )


def _find_user_by_email(email: str):
    if _firebase_backend():
        return get_user_by_email(email)
    return db.session.scalar(
        db.select(User).where(func.lower(User.email) == str(email).strip().lower())
    )


def _find_user(identifier: str):
    identifier = str(identifier or "").strip()
    return _find_user_by_email(identifier) if "@" in identifier else _find_user_by_username(identifier)


def _user_value(user, key: str, default=None):
    if isinstance(user, dict):
        return user.get(key, default)
    return getattr(user, key, default)


def _json_error(message: str, status: int):
    return jsonify({"success": False, "error": message}), status


@auth_bp.get("/api/check-username")
def check_username():
    username = str(request.args.get("username") or _payload().get("username") or "").strip()
    if not _valid_username(username):
        return jsonify({"available": False, "error": "Use 3-30 letters, numbers, or underscores."}), 400
    try:
        return jsonify({"available": _find_user_by_username(username) is None})
    except FirestoreServiceError:
        return _json_error("Username availability is temporarily unavailable.", 503)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    data = _payload()
    identifier = str(data.get("identifier") or data.get("email") or "").strip()
    password = str(data.get("password") or "")
    user = _find_user(identifier) if identifier else None
    password_hash = _user_value(user, "password_hash", "") if user else ""
    valid = bool(user and password_hash and check_password_hash(password_hash, password))
    if not valid:
        response = {"success": False, "error": "Invalid credentials."}
        if user:
            response["show_forgot_password"] = True
        if _wants_json():
            return jsonify(response), 401
        return render_template("login.html", error=response["error"]), 401
    session.clear()
    session["user_id"] = _user_value(user, "id")
    session["username"] = _user_value(user, "username")
    session["email"] = _user_value(user, "email")
    if _wants_json():
        return jsonify({"success": True, "redirect": url_for("analyzer.dashboard")})
    return redirect(url_for("analyzer.dashboard"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    data = _payload()
    username = str(data.get("username") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    name = str(data.get("name") or "").strip()
    if not _valid_username(username):
        return _json_error("Username must be 3-30 letters, numbers, or underscores.", 400)
    if not _valid_email(email):
        return _json_error("A valid email address is required.", 400)
    if len(password) < 8:
        return _json_error("Password must be at least 8 characters.", 400)
    canonical_username = username.casefold()
    try:
        if _find_user_by_username(canonical_username) or _find_user_by_email(email):
            return _json_error("Username or email is already registered.", 409)
        password_hash = generate_password_hash(password, method="scrypt")
        if _firebase_backend():
            user = save_user_account(
                str(uuid.uuid4()),
                email,
                username=canonical_username,
                password_hash=password_hash,
                profile={"name": name},
                auth_state={"registered": True},
            )
        else:
            user = User(
                username=canonical_username,
                email=email,
                password_hash=password_hash,
                email_verified=False,
            )
            db.session.add(user)
            db.session.commit()
        if _wants_json():
            return jsonify({"success": True, "username": _user_value(user, "username", username)}), 201
        return redirect(url_for("auth.login"))
    except FirestoreServiceError:
        return _json_error("Registration is temporarily unavailable.", 503)


@auth_bp.post("/api/send-reset-otp")
def send_reset_otp():
    data = _payload()
    identifier = str(data.get("identifier") or data.get("email") or data.get("username") or "").strip()
    if not identifier:
        return _json_error("Username or email is required.", 400)
    try:
        user = _find_user(identifier)
        email = _user_value(user, "email") if user else ""
        verified = bool(_user_value(user, "email_verified", False)) if user else False
        if email and verified:
            send_otp(email)
        return jsonify({"success": True, "message": "If the account is eligible, a reset code has been sent."})
    except (ValueError, OTPRateLimitError):
        return jsonify({"success": True, "message": "If the account is eligible, a reset code has been sent."})
    except OTPConfigurationError:
        return _json_error("Password reset is temporarily unavailable.", 503)
    except OTPDeliveryError:
        return _json_error("The reset email could not be sent.", 502)
    except FirestoreServiceError:
        return _json_error("Password reset is temporarily unavailable.", 503)


@auth_bp.post("/api/verify-reset-otp")
def verify_reset_otp():
    data = _payload()
    identifier = str(data.get("identifier") or data.get("email") or data.get("username") or "").strip()
    code = str(data.get("otp") or data.get("code") or "").strip()
    try:
        user = _find_user(identifier)
        email = _user_value(user, "email") if user else ""
        if not email or not verify_otp(email, code):
            return _json_error("Invalid or expired verification code.", 400)
        session["password_reset"] = {
            "user_id": str(_user_value(user, "id")),
            "email": email,
            "verified_at": time.time(),
        }
        return jsonify({"success": True, "verified": True})
    except (ValueError, FirestoreServiceError):
        return _json_error("Invalid or expired verification code.", 400)


@auth_bp.post("/api/reset-password")
def reset_password():
    data = _payload()
    new_password = str(data.get("new_password") or data.get("password") or "")
    confirmation = str(data.get("confirm_password") or data.get("password_confirmation") or "")
    reset = session.get("password_reset") or {}
    if time.time() - float(reset.get("verified_at", 0)) > RESET_SESSION_TTL_SECONDS:
        session.pop("password_reset", None)
        return _json_error("Your reset session has expired.", 400)
    if len(new_password) < 8:
        return _json_error("Password must be at least 8 characters.", 400)
    if new_password != confirmation:
        return _json_error("Passwords do not match.", 400)
    password_hash = generate_password_hash(new_password, method="scrypt")
    try:
        if _firebase_backend():
            update_user_password(str(reset["user_id"]), password_hash)
        else:
            user = db.session.get(User, int(reset["user_id"]))
            if user is None:
                return _json_error("Account not found.", 404)
            user.password_hash = password_hash
            db.session.commit()
        session.pop("password_reset", None)
        return jsonify({"success": True, "message": "Password updated. You can now log in."})
    except (KeyError, ValueError):
        session.pop("password_reset", None)
        return _json_error("Your reset session is invalid.", 400)
    except FirestoreServiceError:
        return _json_error("Password update is temporarily unavailable.", 503)


@auth_bp.post("/api/send-otp")
def send_email_otp():
    payload = request.get_json(silent=True) or {}
    try:
        send_otp(payload.get("email", ""))
        return jsonify({"success": True, "message": "If eligible, a verification code has been sent."})
    except ValueError:
        return _json_error("A valid email address is required.", 400)
    except OTPRateLimitError as exc:
        return _json_error(str(exc), 429)
    except OTPConfigurationError:
        return _json_error("Email verification is not configured.", 503)
    except OTPDeliveryError:
        return _json_error("The verification email could not be sent.", 502)


@auth_bp.post("/api/verify-otp")
def verify_email_otp():
    payload = request.get_json(silent=True) or {}
    try:
        verified = verify_otp(payload.get("email", ""), payload.get("otp", ""))
    except ValueError:
        return _json_error("A valid email address is required.", 400)
    if not verified:
        return _json_error("Invalid or expired verification code.", 400)
    return jsonify({"success": True, "verified": True, "message": "Email verified."})


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    if _wants_json():
        return jsonify({"success": True})
    return redirect(url_for("home"))

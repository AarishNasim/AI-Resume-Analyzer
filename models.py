from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=True, index=True)
    email = db.Column(db.String(320), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    resumes = db.relationship("Resume", back_populates="user", cascade="all, delete-orphan")


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    raw_text = db.Column(db.Text, nullable=False)
    parsed_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = db.relationship("User", back_populates="resumes")
    scan_history = db.relationship(
        "ScanHistory",
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="ScanHistory.created_at.desc()",
    )


class ScanHistory(db.Model):
    __tablename__ = "scan_history"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    overall_score = db.Column(db.Float, nullable=False)
    category_scores_json = db.Column(db.JSON, nullable=False, default=dict)
    recommendations_json = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    resume = db.relationship("Resume", back_populates="scan_history")
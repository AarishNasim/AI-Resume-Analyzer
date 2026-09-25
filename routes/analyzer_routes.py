from flask import Blueprint, flash, jsonify, render_template, request, session

from services.file_handler import UploadProcessingError, UploadValidationError, process_uploaded_file
from services.scoring_service import score_resume
from services.skill_extractor import extract_skills
from services.template_engine import TEMPLATES

analyzer_bp = Blueprint("analyzer", __name__)


@analyzer_bp.get("/dashboard")
def dashboard(focus=None):
    focus = focus or request.args.get("focus")
    return render_template(
        "dashboard.html",
        name=session.get("username") or "there",
        resume=None,
        focus=focus,
        ats=0,
        results=[],
        strengths=[],
        feedback={},
        active_template=TEMPLATES[0],
    )


@analyzer_bp.post("/upload")
def upload():
    uploaded_file = request.files.get("resume")
    try:
        processed = process_uploaded_file(uploaded_file)
        analysis = score_resume(processed["text"])
    except (UploadValidationError, UploadProcessingError) as exc:
        flash(str(exc), "error")
        return dashboard("analyze")

    skills = extract_skills(processed["text"])
    resume = {
        "filename": processed["filename"],
        "skills": ", ".join(skills),
    }
    feedback = {
        "keywords": ", ".join(analysis["skill_relevance"]["missing_keywords"]) or "Your core skills are easy to find.",
        "formatting": "Add standard section headings and contact links." if analysis["completeness"]["score"] < 75 else "Your structure is easy for ATS systems to scan.",
        "impact": "Add measurable results to more bullet points." if analysis["impact"]["score"] < 75 else "Your bullets include useful measurable outcomes.",
    }
    strengths = [
        "Clear contact details" if analysis["completeness"]["contact_details"]["email"] else "Add a professional email",
        "Relevant skills detected" if skills else "Add a dedicated skills section",
        "Strong action verbs" if analysis["verbs_style"]["score"] >= 60 else "Use stronger action verbs",
    ]
    return render_template(
        "dashboard.html",
        name=session.get("username") or "there",
        resume=resume,
        focus="analyze",
        ats=analysis["overall_score"],
        results=[],
        strengths=strengths,
        feedback=feedback,
        active_template=TEMPLATES[0],
    )


@analyzer_bp.route("/analyze", methods=["GET", "POST"])
def analyze():
    if request.method == "GET":
        return dashboard("analyze")
    return jsonify({"message": "Resume analysis is not available yet."}), 501
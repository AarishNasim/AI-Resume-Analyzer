from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from services.template_engine import TEMPLATES, get_template, template_choices


builder_bp = Blueprint("builder", __name__)


@builder_bp.route("/builder", methods=["GET", "POST"])
def editor():
    template = get_template(request.args.get("template_id") or "ats-01") or TEMPLATES[0]
    if request.method == "POST":
        return redirect(url_for("analyzer.dashboard"))
    return render_template("builder.html", template=template, values={})


@builder_bp.get("/templates")
def gallery():
    return render_template(
        "template_gallery.html",
        templates=TEMPLATES,
        template_groups=template_choices(),
    )


@builder_bp.post("/builder/export")
def export_resume():
    return jsonify({"message": "Resume export endpoint placeholder."}), 501
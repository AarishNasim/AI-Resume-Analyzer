"""Render normalized resume data into a selectable, ATS-friendly PDF."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
TEMPLATE_NAME = "resumes/ats_classic.html"


class PDFGenerationError(RuntimeError):
    """Raised when no configured HTML-to-PDF renderer can create a PDF."""


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,|\n]", value) if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    return [_text(value)] if _text(value) else []


def _date_range(data: dict[str, Any]) -> str:
    dates = _text(data.get("dates"))
    if dates:
        return dates
    start = _text(data.get("start_date") or data.get("start"))
    end = _text(data.get("end_date") or data.get("end"))
    return " - ".join(part for part in (start, end) if part)


def _url(value: Any) -> str:
    value = _text(value)
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return value if "://" in value else f"https://{value}"


def _link(value: Any) -> dict[str, str] | None:
    if isinstance(value, dict):
        raw_url = value.get("url") or value.get("href") or value.get("link")
        label = _text(value.get("label") or value.get("name") or raw_url)
    else:
        raw_url = value
        label = _text(value)
    url = _url(raw_url)
    return {"url": url, "label": label or url} if url else None


def _normalize_links(raw_links: Any) -> list[dict[str, str]]:
    values = raw_links if isinstance(raw_links, (list, tuple, set)) else _items(raw_links)
    links = [_link(value) for value in values]
    return [link for link in links if link]


def _normalize_entry(entry: Any, kind: str) -> dict[str, Any] | None:
    if isinstance(entry, str):
        return {"title": entry, "degree": entry, "bullets": [], "technologies": []}
    if not isinstance(entry, dict):
        return None
    if kind == "experience":
        normalized = {
            "title": _text(entry.get("title") or entry.get("role") or entry.get("position")),
            "organization": _text(entry.get("organization") or entry.get("company") or entry.get("employer")),
            "location": _text(entry.get("location")),
            "dates": _date_range(entry),
            "bullets": _items(entry.get("bullets") or entry.get("achievements")),
            "description": _text(entry.get("description")),
        }
        return normalized if any(normalized.values()) else None
    if kind == "project":
        normalized = {
            "name": _text(entry.get("name") or entry.get("title")),
            "dates": _date_range(entry),
            "technologies": _items(entry.get("technologies") or entry.get("skills") or entry.get("tools")),
            "url": _url(entry.get("url") or entry.get("link")),
            "bullets": _items(entry.get("bullets") or entry.get("achievements")),
            "description": _text(entry.get("description")),
        }
        return normalized if any(normalized.values()) else None
    normalized = {
        "degree": _text(entry.get("degree") or entry.get("title") or entry.get("program")),
        "institution": _text(entry.get("institution") or entry.get("school") or entry.get("university")),
        "location": _text(entry.get("location")),
        "dates": _date_range(entry),
        "details": _text(entry.get("details") or entry.get("description")),
    }
    return normalized if any(normalized.values()) else None


def _normalize_entries(raw_entries: Any, kind: str) -> list[dict[str, Any]]:
    if isinstance(raw_entries, dict):
        raw_entries = [raw_entries]
    if isinstance(raw_entries, str):
        raw_entries = [raw_entries]
    if not isinstance(raw_entries, (list, tuple, set)):
        return []
    return [entry for item in raw_entries if (entry := _normalize_entry(item, kind))]


def _normalize_skills(raw_skills: Any) -> list[dict[str, Any]]:
    if isinstance(raw_skills, dict):
        return [{"label": _text(label), "items": _items(items)} for label, items in raw_skills.items() if _items(items)]
    items = _items(raw_skills)
    return [{"label": "Skills", "items": items}] if items else []


def _normalize_resume_data(resume_data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(resume_data, dict):
        raise TypeError("resume_data must be a dictionary")
    personal = resume_data.get("personal") if isinstance(resume_data.get("personal"), dict) else resume_data
    contacts = [
        _text(personal.get("email")),
        _text(personal.get("phone")),
        _text(personal.get("location")),
    ]
    links = _normalize_links(personal.get("links") or resume_data.get("links"))
    if personal.get("linkedin"):
        link = _link({"label": "LinkedIn", "url": personal["linkedin"]})
        if link:
            links.append(link)
    if personal.get("github"):
        link = _link({"label": "GitHub", "url": personal["github"]})
        if link:
            links.append(link)
    return {
        "personal": {
            "full_name": _text(personal.get("full_name") or personal.get("name")),
            "headline": _text(personal.get("headline") or resume_data.get("target_role")),
            "contact_items": [item for item in contacts if item],
            "links": links,
        },
        "summary": _text(resume_data.get("summary") or resume_data.get("profile")),
        "skills": _normalize_skills(resume_data.get("skills") or resume_data.get("technical_skills")),
        "experience": _normalize_entries(resume_data.get("experience") or resume_data.get("work_experience"), "experience"),
        "projects": _normalize_entries(resume_data.get("projects"), "project"),
        "education": _normalize_entries(resume_data.get("education"), "education"),
    }


def _render_html(resume_data: dict[str, Any]) -> str:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = environment.get_template(TEMPLATE_NAME)
    return template.render(**_normalize_resume_data(resume_data))


def generate_resume_pdf(resume_data: dict) -> bytes:
    """Render ``resume_data`` as a text-layer selectable PDF.

    WeasyPrint is preferred for CSS and hyperlink support.  xhtml2pdf is used
    as a fallback when WeasyPrint is unavailable.  Both imports are lazy so
    importing this service does not require native PDF libraries immediately.
    """
    html = _render_html(resume_data)
    renderer_errors: list[str] = []

    try:
        from weasyprint import HTML

        return HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()
    except Exception as exc:
        renderer_errors.append(f"WeasyPrint: {exc}")

    try:
        from xhtml2pdf import pisa

        output = io.BytesIO()
        source = io.BytesIO(html.encode("utf-8"))
        result = pisa.CreatePDF(source, dest=output)
        if result.err:
            raise PDFGenerationError(f"xhtml2pdf reported {result.err} error(s)")
        return output.getvalue()
    except Exception as exc:
        renderer_errors.append(f"xhtml2pdf: {exc}")

    details = "; ".join(renderer_errors)
    raise PDFGenerationError(f"Unable to generate resume PDF. Install WeasyPrint or xhtml2pdf. {details}")
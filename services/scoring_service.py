"""Deterministic resume scoring with an optional structured LLM review.

The deterministic scorer is intentionally dependency-free.  LLM access is
opt-in and accepts either a callable or an OpenAI-compatible client, keeping
the core scoring path usable in local development and tests.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from typing import Any


SCORE_WEIGHTS = {
    "impact": 0.25,
    "verbs_style": 0.20,
    "completeness": 0.20,
    "brevity": 0.15,
    "skill_relevance": 0.20,
}

STRONG_ACTION_VERBS = {
    "achieved", "administered", "analyzed", "architected", "automated",
    "built", "championed", "coached", "collaborated", "consolidated",
    "created", "decreased", "delivered", "designed", "developed",
    "directed", "drove", "eliminated", "engineered", "established",
    "exceeded", "expanded", "facilitated", "generated", "grew",
    "implemented", "improved", "increased", "initiated", "launched",
    "led", "mentored", "modernized", "optimized", "orchestrated",
    "pioneered", "produced", "reduced", "refactored", "resolved",
    "spearheaded", "streamlined", "strengthened", "supervised", "tuned",
    "upgraded", "validated",
}

WEAK_ACTION_VERBS = {
    "assisted", "contributed", "dealt with", "did", "handled", "helped",
    "involved", "made", "participated", "responsible for", "worked on",
}

STANDARD_HEADERS = {
    "summary": re.compile(r"^(?:professional\s+)?summary|profile|objective$", re.I),
    "experience": re.compile(r"^(?:professional\s+)?experience|employment|work\s+history$", re.I),
    "education": re.compile(r"^education|academic\s+background$", re.I),
    "skills": re.compile(r"^(?:technical\s+)?skills|competencies|technologies$", re.I),
    "projects": re.compile(r"^projects|selected\s+projects$", re.I),
}

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
LINKEDIN_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/\S+", re.I)
GITHUB_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?github\.com/\S+", re.I)

# Includes percentages, currency, scaled values, counts with units, and
# explicit before/after time improvements. Years and phone numbers are
# excluded unless they appear with a metric unit or an improvement marker.
METRIC_PATTERN = re.compile(
    r"(?ix)"
    r"(?:"
    r"(?:\bfrom\s+)?\$\s*\d[\d,.]*\s*[kmb]?"
    r"|(?:\bfrom\s+)?\d[\d,.]*\s*%"
    r"|\b\d[\d,.]*\s*(?:k|m|b|million|billion|thousand)\+?\b"
    r"|\b\d[\d,.]*\s*(?:users?|customers?|clients?|projects?|tickets?|leads?|downloads?|requests?|records?)\b"
    r"|\b(?:from|to|within|under|in|by)\s+\d[\d,.]*\s*(?:hours?|days?|weeks?|months?|years?|minutes?|secs?|seconds?)\b"
    r"|\b\d[\d,.]*\s*(?:hours?|days?|weeks?|months?|years?|minutes?|secs?|seconds?)\b"
    r"|\b\d[\d,.]*\b"
    r")"
)

BULLET_PATTERN = re.compile(r"^\s*(?:[-*•▪◦]|\d+[.)])\s+")
HEADER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z /&-]{1,40}:?$")

COMMON_SKILLS = {
    "airflow", "aws", "azure", "c", "c++", "css", "docker", "excel", "fastapi",
    "flask", "git", "github", "html", "java", "javascript", "kubernetes", "linux",
    "machine learning", "mongodb", "mysql", "nlp", "node.js", "numpy", "pandas",
    "postgresql", "python", "react", "redis", "rest", "scikit-learn", "sql",
    "sqlite", "tensorflow", "typescript", "ui/ux", "vue", "graphql", "tableau",
}

LLM_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "category_scores",
        "missing_keywords",
        "quick_fixes",
        "weak_bullets",
    ],
    "properties": {
        "category_scores": {
            "type": "object",
            "additionalProperties": False,
            "required": list(SCORE_WEIGHTS),
            "properties": {
                category: {"type": "number", "minimum": 0, "maximum": 100}
                for category in SCORE_WEIGHTS
            },
        },
        "missing_keywords": {"type": "array", "items": {"type": "string"}},
        "quick_fixes": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string"},
        },
        "weak_bullets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["original_bullet", "rewritten_alternatives"],
                "properties": {
                    "original_bullet": {"type": "string"},
                    "rewritten_alternatives": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 3,
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
}


class LLMAnalysisError(RuntimeError):
    """Raised when an LLM response cannot satisfy the required schema."""


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _clean_text(value: str | None) -> str:
    if not isinstance(value, str):
        raise TypeError("resume_text must be a string")
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _is_header(line: str) -> bool:
    normalized = re.sub(r"[:\s]+$", "", line.strip()).lower()
    return any(pattern.fullmatch(normalized) for pattern in STANDARD_HEADERS.values()) or bool(
        HEADER_PATTERN.fullmatch(line.strip()) and len(line.split()) <= 5
    )


def _bullets(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullets = [BULLET_PATTERN.sub("", line).strip() for line in lines if BULLET_PATTERN.match(line)]
    if bullets:
        return bullets
    return [line for line in lines if not _is_header(line)]


def _metric_matches(text: str) -> list[str]:
    return [match.group(0).strip() for match in METRIC_PATTERN.finditer(text)]


def _action_verb(text: str) -> str | None:
    normalized = re.sub(r"^[\s\-•▪◦\d.)]+", "", text).lower()
    for phrase in sorted(WEAK_ACTION_VERBS | STRONG_ACTION_VERBS, key=len, reverse=True):
        if re.match(rf"{re.escape(phrase)}\b", normalized):
            return phrase
    return None


def _skill_terms(text: str) -> set[str]:
    lowered = text.lower()
    return {skill for skill in COMMON_SKILLS if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", lowered)}


def _structural_score(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headers = {
        name: any(pattern.fullmatch(re.sub(r"[:\s]+$", "", line).lower()) for line in lines)
        for name, pattern in STANDARD_HEADERS.items()
    }
    contacts = {
        "email": bool(EMAIL_PATTERN.search(text)),
        "phone": bool(PHONE_PATTERN.search(text)),
        "linkedin": bool(LINKEDIN_PATTERN.search(text)),
        "github": bool(GITHUB_PATTERN.search(text)),
    }
    found = sum(headers.values()) + sum(contacts.values())
    return {
        "headers": headers,
        "contact_details": contacts,
        "score": _clamp(found / (len(headers) + len(contacts)) * 100),
    }


def _impact_score(bullets: list[str]) -> dict[str, Any]:
    metrics_by_bullet = [_metric_matches(bullet) for bullet in bullets]
    metric_bullets = sum(bool(metrics) for metrics in metrics_by_bullet)
    total_metrics = sum(len(metrics) for metrics in metrics_by_bullet)
    coverage = metric_bullets / len(bullets) if bullets else 0.0
    density = total_metrics / len(bullets) if bullets else 0.0
    return {
        "score": _clamp(coverage * 70 + min(density, 2.0) / 2.0 * 30),
        "bullet_count": len(bullets),
        "metric_bullet_count": metric_bullets,
        "metric_count": total_metrics,
        "metric_density_per_bullet": round(density, 2),
        "metrics_by_bullet": metrics_by_bullet,
    }


def _verbs_score(bullets: list[str]) -> dict[str, Any]:
    verbs = [_action_verb(bullet) for bullet in bullets]
    strong = [verb for verb in verbs if verb in STRONG_ACTION_VERBS]
    weak = [verb for verb in verbs if verb in WEAK_ACTION_VERBS]
    recognized = len(strong) + len(weak)
    ratio = len(strong) / recognized if recognized else 0.0
    return {
        "score": _clamp(ratio * 100),
        "action_verb_strength_ratio": round(ratio, 2),
        "strong_verbs": strong,
        "weak_verbs": weak,
        "unrecognized_bullet_starts": sum(verb is None for verb in verbs),
    }


def _brevity_score(text: str, bullets: list[str]) -> dict[str, Any]:
    word_count = len(re.findall(r"\b[\w][\w'/-]*\b", text))
    average_bullet_length = sum(len(bullet.split()) for bullet in bullets) / len(bullets) if bullets else 0
    if 300 <= word_count <= 900:
        word_score = 100
    elif word_count < 300:
        word_score = word_count / 300 * 100
    else:
        word_score = max(0, 100 - (word_count - 900) / 9)
    bullet_score = 100 if not bullets else max(0, 100 - max(0, average_bullet_length - 24) * 4)
    return {
        "score": _clamp(word_score * 0.6 + bullet_score * 0.4),
        "word_count": word_count,
        "average_bullet_words": round(average_bullet_length, 1),
        "word_count_score": _clamp(word_score),
        "bullet_length_score": _clamp(bullet_score),
    }


def _skill_relevance_score(resume_text: str, job_description: str | None) -> dict[str, Any]:
    resume_skills = _skill_terms(resume_text)
    job_skills = _skill_terms(job_description or "")
    if job_description and job_skills:
        matched = sorted(resume_skills & job_skills)
        missing = sorted(job_skills - resume_skills)
        score = len(matched) / len(job_skills) * 100
    else:
        matched = sorted(resume_skills)
        missing = []
        score = min(len(resume_skills) / 10, 1) * 100
    return {
        "score": _clamp(score),
        "resume_skills": sorted(resume_skills),
        "job_skills": sorted(job_skills),
        "matched_skills": matched,
        "missing_keywords": missing,
    }


def score_resume(resume_text: str, job_description: str | None = None) -> dict[str, Any]:
    """Return deterministic ATS findings and a weighted 0-100 score."""
    text = _clean_text(resume_text)
    job_text = _clean_text(job_description) if job_description else None
    bullets = _bullets(text)
    impact = _impact_score(bullets)
    verbs = _verbs_score(bullets)
    completeness = _structural_score(text)
    brevity = _brevity_score(text, bullets)
    skills = _skill_relevance_score(text, job_text)
    category_scores = {
        "impact": impact["score"],
        "verbs_style": verbs["score"],
        "completeness": completeness["score"],
        "brevity": brevity["score"],
        "skill_relevance": skills["score"],
    }
    overall_score = _clamp(sum(category_scores[name] * weight for name, weight in SCORE_WEIGHTS.items()))
    return {
        "overall_score": overall_score,
        "category_scores": category_scores,
        "weights": SCORE_WEIGHTS.copy(),
        "impact": impact,
        "verbs_style": verbs,
        "completeness": completeness,
        "brevity": brevity,
        "skill_relevance": skills,
        "job_description_provided": bool(job_text),
    }


def build_llm_prompt(resume_text: str, deterministic_findings: Mapping[str, Any]) -> str:
    """Build a strict JSON-review prompt from deterministic evidence."""
    findings = json.dumps(deterministic_findings, indent=2, sort_keys=True)
    schema = json.dumps(LLM_JSON_SCHEMA, indent=2)
    return f"""You are an expert ATS resume editor. Review the resume using the deterministic findings below.

Return ONLY valid JSON. Do not use Markdown fences, commentary, or additional keys.
Every score must be a number from 0 to 100. Provide exactly 3 quick fixes and exactly
3 rewritten alternatives for every weak bullet you flag. Rewrites must preserve facts
and must not invent employers, metrics, dates, tools, or achievements.

Required JSON Schema:
{schema}

Deterministic findings:
{findings}

Resume text:
---
{resume_text}
---
"""


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, Mapping):
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "") if isinstance(message, Mapping) else ""
            return content if isinstance(content, str) else json.dumps(content)
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text
    choices = getattr(response, "choices", [])
    if choices:
        content = getattr(getattr(choices[0], "message", None), "content", "")
        return content if isinstance(content, str) else json.dumps(content)
    raise LLMAnalysisError("LLM response did not contain text content")


def _parse_json_response(raw_text: str) -> dict[str, Any]:
    candidate = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, re.I | re.S)
    if fenced:
        candidate = fenced.group(1)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMAnalysisError("LLM response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise LLMAnalysisError("LLM response must be a JSON object")
    _validate_llm_payload(payload)
    return payload


def _validate_llm_payload(payload: Mapping[str, Any]) -> None:
    required = set(LLM_JSON_SCHEMA["required"])
    if set(payload) != required:
        raise LLMAnalysisError("LLM JSON keys do not match the required schema")
    scores = payload["category_scores"]
    if not isinstance(scores, Mapping) or set(scores) != set(SCORE_WEIGHTS):
        raise LLMAnalysisError("category_scores must contain exactly the five required categories")
    if any(not isinstance(value, (int, float)) or not 0 <= value <= 100 for value in scores.values()):
        raise LLMAnalysisError("category scores must be numbers from 0 to 100")
    if not isinstance(payload["missing_keywords"], list) or not all(
        isinstance(item, str) for item in payload["missing_keywords"]
    ):
        raise LLMAnalysisError("missing_keywords must be a list of strings")
    quick_fixes = payload["quick_fixes"]
    if not isinstance(quick_fixes, list) or len(quick_fixes) != 3 or not all(
        isinstance(item, str) for item in quick_fixes
    ):
        raise LLMAnalysisError("quick_fixes must contain exactly three strings")
    if not isinstance(payload["weak_bullets"], list):
        raise LLMAnalysisError("weak_bullets must be a list")
    for item in payload["weak_bullets"]:
        if not isinstance(item, Mapping) or set(item) != {"original_bullet", "rewritten_alternatives"}:
            raise LLMAnalysisError("each weak bullet must match the required schema")
        alternatives = item["rewritten_alternatives"]
        if not isinstance(item["original_bullet"], str) or not isinstance(alternatives, list) or len(alternatives) != 3:
            raise LLMAnalysisError("each weak bullet must have exactly three rewritten alternatives")
        if not all(isinstance(alternative, str) for alternative in alternatives):
            raise LLMAnalysisError("rewritten alternatives must be strings")


def analyze_with_llm(
    resume_text: str,
    deterministic_findings: Mapping[str, Any] | None = None,
    *,
    llm_callable: Callable[[str], Any] | None = None,
    client: Any | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Request and validate the strict JSON LLM review.

    ``llm_callable`` receives the prompt and should return text or a provider
    response object.  Alternatively, ``client`` may expose
    ``client.chat.completions.create``.  An API key is never required by the
    deterministic scorer, and no implicit network call is made without one of
    these integrations.
    """
    text = _clean_text(resume_text)
    findings = deterministic_findings or score_resume(text)
    prompt = build_llm_prompt(text, findings)
    if llm_callable is not None:
        response = llm_callable(prompt)
    elif client is not None:
        response = client.chat.completions.create(
            model=model or os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Return only JSON matching the requested schema."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
    else:
        raise LLMAnalysisError("Provide llm_callable or an OpenAI-compatible client for LLM analysis")
    return _parse_json_response(_response_text(response))


def score_resume_with_llm(
    resume_text: str,
    job_description: str | None = None,
    *,
    llm_callable: Callable[[str], Any] | None = None,
    client: Any | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Return deterministic findings plus the validated optional LLM review."""
    deterministic = score_resume(resume_text, job_description)
    llm_review = analyze_with_llm(
        resume_text,
        deterministic,
        llm_callable=llm_callable,
        client=client,
        model=model,
    )
    return {"deterministic": deterministic, "llm_review": llm_review}
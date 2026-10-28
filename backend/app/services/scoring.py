import json
import re

from . import llm

ALLOWED_FLAGS = {
    "customer_data_shared",
    "confidential_data_shared",
    "unreviewed_output",
    "policy_unaware",
}

TEXT_SCORE_MAP = {
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
}

FALLBACK_RESULT = {
    "score": 1.0,
    "reason": "Unable to evaluate answer format.",
    "flags": [],
}


def clean_raw_text(raw: str) -> str:
    """Strip Markdown code fences (e.g. ```json ... ```) and whitespace."""
    if not isinstance(raw, str):
        return ""
    text = raw.strip()
    # Strip opening code fence: ```json or ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Strip closing code fence: ```
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_llm_response(raw: str) -> dict:
    """Parse and validate LLM output, guaranteeing safe score, reason, and flags."""
    text = clean_raw_text(raw)
    data = None

    if text:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            # Attempt to extract first JSON object pattern from text
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    data = json.loads(match.group(0))
                except (json.JSONDecodeError, TypeError):
                    data = None

    if not isinstance(data, dict):
        return dict(FALLBACK_RESULT)

    # 1. Parse and validate score (rubric: 1 to 5)
    raw_score = data.get("score")
    score: float | None = None
    if isinstance(raw_score, (int, float)):
        score = float(raw_score)
    elif isinstance(raw_score, str):
        cleaned_score = raw_score.strip().lower()
        if cleaned_score in TEXT_SCORE_MAP:
            score = TEXT_SCORE_MAP[cleaned_score]
        else:
            try:
                score = float(cleaned_score)
            except ValueError:
                score = None

    if score is None:
        score = FALLBACK_RESULT["score"]
    else:
        # Clamp between 1.0 and 5.0
        score = max(1.0, min(5.0, score))

    # 2. Parse and validate reason
    raw_reason = data.get("reason")
    if isinstance(raw_reason, str) and raw_reason.strip():
        reason = raw_reason.strip()
    else:
        reason = "No specific reason provided."

    # 3. Parse and sanitize flags
    raw_flags = data.get("flags")
    flags = []
    if isinstance(raw_flags, list):
        for f in raw_flags:
            if isinstance(f, str) and f in ALLOWED_FLAGS and f not in flags:
                flags.append(f)

    return {
        "score": score,
        "reason": reason,
        "flags": flags,
    }


def score_open_answer(question_text: str, answer: str) -> dict:
    raw = llm.score_answer(question_text, answer)
    return parse_llm_response(raw)

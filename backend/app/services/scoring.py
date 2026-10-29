import json
from typing import Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    field_validator,
)
from . import llm


class ScoringUnavailable(Exception):
    """Safe category only: never return raw provider output or credentials to users."""


class ScoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    score: StrictInt = Field(ge=1, le=5)
    reason: str = Field(min_length=1, max_length=600)
    flags: list[
        Literal[
            "customer_data_shared",
            "confidential_data_shared",
            "unreviewed_output",
            "policy_unaware",
        ]
    ] = Field(max_length=4)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if not value.strip():
            raise ValueError("An explanation is required")
        return value.strip()

    @field_validator("flags")
    @classmethod
    def unique_flags(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Duplicate flags")
        return values


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def parse_result(raw):
    if not isinstance(raw, str) or len(raw) > 8000:
        raise ScoringUnavailable("invalid_output")
    # Tolerate an outer JSON code fence, not arbitrary extraction or score coercion.
    cleaned = raw.strip()
    if cleaned.startswith("~~~"):
        raise ScoringUnavailable("invalid_output")
    fence = chr(96) * 3
    if cleaned.startswith(fence):
        lines = cleaned.splitlines()
        if lines[0] not in (fence, fence + "json") or lines[-1] != fence:
            raise ScoringUnavailable("invalid_output")
        cleaned = "\n".join(lines[1:-1])
    try:
        data = json.loads(cleaned, object_pairs_hook=_no_duplicate_keys)
        return ScoreResult.model_validate(data).model_dump()
    except (ValueError, TypeError, ValidationError):
        raise ScoringUnavailable("invalid_output")


def score_open_answer(question_text, answer):
    try:
        return parse_result(llm.score_answer(question_text, answer))
    except ScoringUnavailable:
        raise
    except Exception:
        # No made-up score, no exception text that could contain private model input.
        raise ScoringUnavailable("provider_unavailable")

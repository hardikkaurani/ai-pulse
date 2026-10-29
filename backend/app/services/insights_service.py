"""Privacy-safe AI and rule-based organizational insights service.

Adheres to strict privacy engineering standards:
- Operates exclusively on aggregated metrics from departments meeting the privacy threshold (k >= 5).
- Never transmits, processes, or exposes employee identifiers, individual scores, or raw answers.
- Strict schema validation on LLM output with allowlists for departments and risk labels.
- Deterministic rule-based fallback when the LLM is unconfigured, times out, or fails validation.
"""
import json
import logging
import re
import httpx

from ..config import AI_MODE, LLM_API_KEY, LLM_API_URL, LLM_MODEL

logger = logging.getLogger(__name__)

ALLOWED_FLAGS = {
    "customer_data_shared",
    "confidential_data_shared",
    "unreviewed_output",
    "policy_unaware",
}

VALID_PRIORITIES = {"high", "medium", "low"}

SYSTEM_PROMPT = """You are an enterprise AI governance and risk advisor.
Analyze the provided department-level aggregate risk counts and maturity scores.
For each department with risks or low maturity, provide practical organizational recommendations.
Rules:
1. Do not invent or assume any individual employee data.
2. Only reference the departments and risks provided in the input.
3. Every insight must contain:
   - department: exact department name from input
   - observed_pattern: concise summary of the aggregate pattern (max 200 chars)
   - recommended_action: concrete, feasible organizational step (max 200 chars)
   - reason: why the action resolves the risk (max 200 chars)
   - priority: "high", "medium", or "low"
Return JSON ONLY: {"insights": [{"department": ..., "observed_pattern": ..., "recommended_action": ..., "reason": ..., "priority": ...}]}"""


def generate_rule_based_insights(visible_departments: list[dict]) -> list[dict]:
    """Generates deterministic, highly practical recommendations directly from aggregate patterns."""
    insights = []

    for d in visible_departments:
        dept_name = d.get("department", "Unknown Department")
        risk_counts = d.get("risk_counts", {})
        avg_score = d.get("average_score")
        level = d.get("level", "Not assessed")

        has_risk = False

        if risk_counts.get("customer_data_shared"):
            count = risk_counts["customer_data_shared"]
            has_risk = True
            insights.append({
                "department": dept_name,
                "observed_pattern": f"Customer data shared with external AI tools without clear redaction boundaries ({count} instances).",
                "recommended_action": "Deploy enterprise-managed AI accounts with zero data retention and implement client data masking guidelines.",
                "reason": "Protects client confidentiality, prevents regulatory breaches (GDPR/SOC 2), and reduces third-party data leakage risks.",
                "priority": "high",
            })

        if risk_counts.get("confidential_data_shared"):
            count = risk_counts["confidential_data_shared"]
            has_risk = True
            insights.append({
                "department": dept_name,
                "observed_pattern": f"Internal confidential or proprietary records entered into AI models ({count} instances).",
                "recommended_action": "Enforce data classification guidelines and mandate approved local or private models for sensitive internal documentation.",
                "reason": "Ensures trade secrets, financial records, and proprietary intellectual property stay within organizational boundaries.",
                "priority": "high",
            })

        if risk_counts.get("unreviewed_output"):
            count = risk_counts["unreviewed_output"]
            has_risk = True
            insights.append({
                "department": dept_name,
                "observed_pattern": f"AI-generated deliverables incorporated into workflow without structured human verification ({count} instances).",
                "recommended_action": "Implement a documented peer-review checklist and designate technical owners to verify AI-generated work products.",
                "reason": "Mitigates hallucinations, subtle logic bugs, and quality degradation in deliverables before release.",
                "priority": "medium",
            })

        if risk_counts.get("policy_unaware"):
            count = risk_counts["policy_unaware"]
            has_risk = True
            insights.append({
                "department": dept_name,
                "observed_pattern": f"Ambiguity or lack of familiarity with organizational AI acceptable-use policies ({count} instances).",
                "recommended_action": "Distribute an official AI usage cheat-sheet and conduct a mandatory 30-minute policy walkthrough session.",
                "reason": "Establishes clear boundaries, eliminates guesswork, and fosters responsible AI adoption.",
                "priority": "medium",
            })

        if not has_risk and level in ("Beginner", "Exploring"):
            insights.append({
                "department": dept_name,
                "observed_pattern": f"Department maturity is '{level}' with limited daily AI adoption (avg score: {avg_score or '—'}).",
                "recommended_action": "Run role-specific AI workflow demos and establish peer enablement sessions to raise baseline competence.",
                "reason": "Accelerates productive AI adoption while ensuring guardrails are understood early.",
                "priority": "low",
            })

    return insights


def generate_insights(visible_departments: list[dict]) -> dict:
    """Generate organizational insights from visible departments meeting privacy criteria.

    Returns dict: {"insights": [...], "source": "ai" | "mock" | "rules"}
    """
    if not visible_departments:
        return {"insights": [], "source": "rules"}

    if AI_MODE != "live" or not LLM_API_KEY or not LLM_API_URL:
        source_label = "mock" if AI_MODE == "mock" else "rules"
        return {
            "insights": generate_rule_based_insights(visible_departments),
            "source": source_label,
        }

    valid_dept_names = {d["department"] for d in visible_departments if "department" in d}

    # Construct privacy-filtered payload for LLM (NO PII, NO raw text)
    safe_payload = [
        {
            "department": d.get("department"),
            "employees": d.get("employees"),
            "responded": d.get("responded"),
            "average_score": d.get("average_score"),
            "level": d.get("level"),
            "risk_counts": {k: v for k, v in d.get("risk_counts", {}).items() if k in ALLOWED_FLAGS and v > 0},
        }
        for d in visible_departments
    ]

    try:
        r = httpx.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL or "default",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(safe_payload)},
                ],
            },
            timeout=15.0,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()

        # Clean markdown code fences
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)
        items = data.get("insights", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

        validated = []
        for it in items:
            if not isinstance(it, dict):
                continue
            dept = it.get("department")
            if dept not in valid_dept_names:
                continue
            pattern = str(it.get("observed_pattern") or "").strip()[:300]
            action = str(it.get("recommended_action") or "").strip()[:300]
            reason = str(it.get("reason") or "").strip()[:300]
            priority = str(it.get("priority") or "").lower().strip()
            if priority not in VALID_PRIORITIES:
                continue

            if pattern and action and reason:
                validated.append({
                    "department": dept,
                    "observed_pattern": pattern,
                    "recommended_action": action,
                    "reason": reason,
                    "priority": priority,
                })

        if validated:
            return {"insights": validated, "source": "ai"}

        # If LLM returned empty or invalid schema, fallback to deterministic rules
        return {
            "insights": generate_rule_based_insights(visible_departments),
            "source": "rules",
        }

    except Exception as e:
        logger.warning("LLM insights generation failed or timed out: %s. Using deterministic fallback.", e)
        return {
            "insights": generate_rule_based_insights(visible_departments),
            "source": "rules",
        }


def generate_other_teams_insights(target_dept: dict) -> dict:
    """Generates privacy-safe actionable recommendations for the 'Other teams' aggregate."""
    dept_name = "Other teams"
    responded = target_dept.get("responded") or 0
    headcount = target_dept.get("employees") or 0
    avg_score = target_dept.get("average_score")
    level = target_dept.get("level") or "Not assessed"
    raw_risks = target_dept.get("risk_counts") or {}

    # Privacy filtering for small combined teams
    safe_risks = {}
    if responded >= 5:
        safe_risks = {k: v for k, v in raw_risks.items() if k in ALLOWED_FLAGS and v > 0}
    elif responded >= 2:
        safe_risks = {k: v for k, v in raw_risks.items() if k in ALLOWED_FLAGS and v >= 2}

    if not safe_risks:
        return {
            "insights": [
                {
                    "department": dept_name,
                    "observed_pattern": "Diagnostic participation in combined small teams is sparse with no shared aggregate risk patterns meeting privacy thresholds.",
                    "recommended_action": "Establish general organizational AI acceptable-use guidelines and provide standard baseline training across small teams.",
                    "reason": "Provides proactive governance and literacy across smaller operational units without risking individual identification.",
                    "priority": "low",
                }
            ],
            "source": "rules",
        }

    safe_dept_record = {
        "department": dept_name,
        "employees": headcount,
        "responded": responded,
        "average_score": avg_score,
        "level": level,
        "risk_counts": safe_risks,
    }

    return generate_insights([safe_dept_record])

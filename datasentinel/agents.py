import json
from typing import Any, Dict, List
import pandas as pd
from pydantic import BaseModel, Field
from .profiling import profile_dataframe

class Finding(BaseModel):
    id: str
    type: str
    severity: str
    column: str
    count: int
    evidence: str

class Hypothesis(BaseModel):
    cause: str
    reasoning: str
    evidence_for: List[str] = Field(default_factory=list)
    evidence_against: List[str] = Field(default_factory=list)
    confidence: str = "low"
    status: str = "unverified"

class RepairPlan(BaseModel):
    proposed_action: str
    rationale: str
    safe_to_test: bool = False
    verification_checks: List[str] = Field(default_factory=list)

def _chat_model(provider: str, model: str):
    from langchain.chat_models import init_chat_model
    return init_chat_model(model, model_provider="ollama" if provider == "Ollama" else "openai")

def data_detective(df: pd.DataFrame, provider: str, model: str) -> Dict[str, Any]:
    findings = profile_dataframe(df, include_findings=True)
    metrics = {"rows": len(df), "columns": len(df.columns),
               "missing_cells": int(df.isna().sum().sum()), "duplicate_rows": int(df.duplicated().sum())}
    explanation = "Deterministic scan completed."
    try:
        response = _chat_model(provider, model).invoke(
            "Explain only these measured data-quality findings. Do not invent causes or numbers. "
            "Distinguish observations from hypotheses.\n" + json.dumps({"metrics": metrics, "findings": findings})
        )
        explanation = response.content if isinstance(response.content, str) else str(response.content)
    except Exception as exc:
        explanation = f"Deterministic scan completed; LLM explanation unavailable ({type(exc).__name__})."
    return {"metrics": metrics, "findings": findings, "explanation": explanation}

def _parse_json(content: str):
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
    return {"summary": content, "hypotheses": [], "unknowns": ["Response was not valid JSON."]}

def root_cause_investigator(df: pd.DataFrame, detective: Dict, kb, provider: str, model: str) -> Dict[str, Any]:
    query = " ".join(f.get("evidence", "") for f in detective.get("findings", [])) or "data quality schema business rules"
    sources = kb.retrieve(query, k=4) if kb else []
    context = {"columns": list(df.columns), "dtypes": {c: str(t) for c,t in df.dtypes.items()},
               "sample": df.head(8).where(pd.notna(df.head(8)), None).to_dict(orient="records"),
               "findings": detective.get("findings", []),
               "retrieved_evidence": [{"source": x["source"], "text": x["text"][:700]} for x in sources]}
    prompt = ("You are a root-cause investigator. Use only supplied evidence; do not claim a cause is confirmed unless tested. "
              "Return JSON with keys summary, hypotheses (objects with cause, reasoning, evidence_for, evidence_against, "
              "confidence low/medium/high, status unverified/supported/rejected), and unknowns. "
              "If evidence is insufficient, say so. Never execute SQL.\n" + json.dumps(context, default=str))
    try:
        response = _chat_model(provider, model).invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = _parse_json(content)
        if not isinstance(parsed, dict):
            parsed = {"summary": content, "hypotheses": [], "unknowns": ["Could not parse structured response."]}
    except Exception as exc:
        parsed = {"summary": f"LLM investigation unavailable ({type(exc).__name__}).",
                  "hypotheses": [], "unknowns": ["Check LLM provider configuration."]}
    parsed["retrieved_sources"] = sources
    return parsed

def repair_and_verify(df: pd.DataFrame, detective: Dict, investigator: Dict, provider: str, model: str) -> Dict[str, Any]:
    test_copy = df.copy(deep=True)
    checks = []
    for finding in detective.get("findings", []):
        kind, col = finding.get("type"), finding.get("column")
        if kind == "missing_values":
            checks.append({"check": f"No missing values in {col}",
                           "passed": bool(col in test_copy and test_copy[col].isna().sum() == 0),
                           "note": "Detected only; no automatic repair performed."})
        elif kind == "duplicates":
            checks.append({"check": "No duplicate rows", "passed": bool(test_copy.duplicated().sum() == 0),
                           "note": "Detected only; no automatic removal performed."})
    hypothesis = (investigator.get("hypotheses") or [{}])[0]
    plan = {"proposed_action": "Review the evidence-backed hypothesis and define a domain-approved repair.",
            "rationale": hypothesis.get("reasoning", "Insufficient evidence to choose a safe repair."),
            "safe_to_test": False, "verification_checks": [c["check"] for c in checks]}
    passed = bool(checks) and all(c["passed"] for c in checks)
    return {"plan": plan, "checks": checks, "passed": passed,
            "status": "checks_passed" if passed else "not_verified", "original_data_modified": False,
            "note": "Checks run against a copy. Passing does not mean all detected issues were repaired."}

from __future__ import annotations
import re, json
from typing import List, Dict, Any
from .judge_constants import JudgeConstants

# --- lightweight feature detectors (tune as needed) ---
_KEYWORDS_MATH   = re.compile(r"\b(integral|matrix|proof|theorem|sum|log|probability|bayes|gradient)\b", re.I)
_KEYWORDS_CODE   = re.compile(r"\b(def |class |function |import |SELECT |FROM |WHERE )", re.I)
_KEYWORDS_SAFETY = re.compile(r"\b(harm|illegal|danger|self-harm|biosecurity|weapon)\b", re.I)
_KEYWORDS_BIO    = re.compile(r"\b(clinical|trial|dosage|oncolog|cardio|symptom|diagnos)\b", re.I)

def _features(brief: str, candidates: List[Dict[str,str]], aspect_hint: str|None) -> Dict[str, float]:
    """Extract simple, robust features for routing."""
    b = brief or ""
    return {
        "len_brief": float(len(b)),
        "num_cands": float(len(candidates)),
        "has_math": 1.0 if _KEYWORDS_MATH.search(b) else 0.0,
        "has_code": 1.0 if _KEYWORDS_CODE.search(b) else 0.0,
        "is_safety": 1.0 if (_KEYWORDS_SAFETY.search(b) or (aspect_hint == "safety")) else 0.0,
        "is_biohealth": 1.0 if _KEYWORDS_BIO.search(b) else 0.0,
    }

def _load_router_params() -> Dict[str, Any]:
    """Load router weights JSON with a safe fallback."""
    try:
        return json.loads(JudgeConstants.JUDGE_ROUTER_WEIGHTS_JSON)
    except Exception:
        # fallback defaults if env/json is malformed
        return {
            "feat_weights": {
                "len_brief": 0.0005,
                "num_cands": 0.03,
                "has_math": 0.0,
                "has_code": 0.0,
                "is_safety": 0.02,
                "is_biohealth": 0.02,
            },
            "bias_terms": {"default": -0.05},
        }

def route_models(all_models: List[str], brief: str, candidates: List[Dict[str,str]], aspect_hint: str|None) -> List[str]:
    """Return top-K models for this task, based on linear scoring + optional cost penalty."""
    if not JudgeConstants.JUDGE_ENABLE_ROUTER or len(all_models) <= 1:
        return all_models

    params = _load_router_params()
    fw = params.get("feat_weights", {}) or {}
    bias = (params.get("bias_terms", {}) or {}).get("default", 0.0)
    x = _features(brief, candidates, aspect_hint)

    enable_cost = bool(getattr(JudgeConstants, "JUDGE_ENABLE_COST_AWARE", True))
    cost_coef = float(getattr(JudgeConstants, "JUDGE_COST_COEF", 0.05)) if enable_cost else 0.0

    scored: List[tuple[float, str, Dict[str, float]]] = []
    for m in all_models:
        # linear score from features
        s = bias + sum(float(fw.get(k, 0.0)) * x.get(k, 0.0) for k in x.keys())
        # subtract cost penalty if enabled
        cost_pen = float(JudgeConstants.JUDGE_MODEL_COST.get(m, 1.0)) * cost_coef
        s -= cost_pen
        scored.append((s, m, {"score": s, "cost_penalty": cost_pen}))

    scored.sort(key=lambda t: t[0], reverse=True)
    k = max(1, min(JudgeConstants.JUDGE_ROUTER_TOPK, len(scored)))
    return [m for _, m, _ in scored[:k]]

def explain_router(all_models: List[str], brief: str, candidates: List[Dict[str,str]], aspect_hint: str|None) -> Dict[str, Any]:
    """Return a human-readable explanation of routing (feature contributions, cost penalty, totals)."""
    params = _load_router_params()
    fw = params.get("feat_weights", {}) or {}
    bias = (params.get("bias_terms", {}) or {}).get("default", 0.0)
    x = _features(brief, candidates, aspect_hint)

    enable_cost = bool(getattr(JudgeConstants, "JUDGE_ENABLE_COST_AWARE", True))
    cost_coef = float(getattr(JudgeConstants, "JUDGE_COST_COEF", 0.05)) if enable_cost else 0.0

    details: List[Dict[str, Any]] = []
    for m in all_models:
        contribs = {k: float(fw.get(k, 0.0)) * x.get(k, 0.0) for k in x.keys()}
        cost_pen = float(JudgeConstants.JUDGE_MODEL_COST.get(m, 1.0)) * cost_coef
        total = bias + sum(contribs.values()) - cost_pen
        details.append({
            "model": m,
            "bias": bias,
            "feature_contributions": contribs,
            "cost_penalty": cost_pen,
            "total_score": total,
        })

    details.sort(key=lambda d: d["total_score"], reverse=True)
    chosen = [d["model"] for d in details[:max(1, min(JudgeConstants.JUDGE_ROUTER_TOPK, len(details)))]]
    return {"chosen_models": chosen, "feature_scores": x, "detail": details}

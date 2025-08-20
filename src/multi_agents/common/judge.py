# src/multi_agents/common/judge.py
from __future__ import annotations

import os
import json
import uuid
import random
import asyncio
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from pathlib import Path
from datetime import datetime

from pydantic import SecretStr
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from ..constants.judge_constants import JudgeConstants
from ..constants.judge_router import route_models, explain_router
from ..xai.judge_xai import bias_report_from_committee
from ..open_deep_research.configuration import Configuration
from ..Prompts.open_deep_research_prompts import JUDGE_PROMPT
from ..common.trace import trace_event

# ---------- JSON dump helpers ----------
TRACE_DIR = Path(os.getenv("TRACE_DIR", "traces"))

def _dump_json_file(obj: Any, *, folder: str, filename: str) -> str:
    """
    Pretty-print JSON to a file under TRACE_DIR/folder/filename.
    Always newline-terminates. Returns the path (string) or "" on failure.
    """
    try:
        dirpath = TRACE_DIR / folder
        dirpath.mkdir(parents=True, exist_ok=True)
        path = dirpath / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return str(path)
    except Exception:
        return ""

def _timestamp() -> str:
    # Optional timestamp helper if you prefer time-based filenames
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")

# -----------------------
# Utilities / glue
# -----------------------
def _get_api_key_for_model(model: str, _config: RunnableConfig) -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY not set")
    return key


def safe_format(template: str, **kwargs) -> str:
    """Format a template that contains literal braces by escaping everything,
    then restoring our real placeholders."""
    esc = template.replace("{", "{{").replace("}", "}}")
    for k in kwargs.keys():
        esc = esc.replace("{{" + k + "}}", "{" + k + "}")
    return esc.format(**kwargs)


def _normalize_candidates(cands: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for c in cands or []:
        out.append(
            {
                "name": str(c.get("name", "")).strip(),
                "url": str(c.get("url", "")).strip(),
                "why": str(c.get("why", "")).strip(),
            }
        )
    return out


def _swap(cands: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Swap first two items to mitigate position bias."""
    if len(cands) <= 1:
        return cands[:]
    s = cands[:]
    s[0], s[1] = s[1], s[0]
    return s


def _pick_committee_models(hint_aspect: Optional[str]) -> List[str]:
    return list(JudgeConstants.JUDGE_COMMITTEE_MODELS)


def _winner_from_votes(votes: Dict[int, int]) -> Optional[int]:
    if not votes:
        return None
    best = max(votes.items(), key=lambda x: x[1])
    winners = [k for k, v in votes.items() if v == best[1]]
    return best[0] if len(winners) == 1 else None


def _aggregate_confidences(conf_list: List[float]) -> float:
    confs = [float(c) for c in conf_list if isinstance(c, (int, float))]
    return (sum(confs) / len(confs)) if confs else 0.0


def _inject_rubric(notes: List[str], rubric: str) -> List[str]:
    return ([f"[RUBRIC]\n{rubric}\n[/RUBRIC]"] + (notes or [])) if rubric else (notes or [])


# -----------------------
# JSON Repair Helper
# -----------------------
def _as_json_or_repair(raw: str, repair_llm: Optional[ChatOpenAI] = None) -> Dict[str, Any]:
    txt = (raw or "").strip()
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        if not repair_llm:
            return {}
        rep = repair_llm.invoke([HumanMessage(
            content=("Fix this into STRICT minified JSON only. "
                     "If impossible, return {}. No markdown, no commentary.\n\n" + txt)
        )])
        fixed = getattr(rep, "content", "") or ""
        try:
            return json.loads(fixed)
        except Exception:
            return {}


# -----------------------
# Low-level judge call
# -----------------------
async def _call_judge_model(model: str, prompt: str, max_tokens: int) -> Dict[str, Any]:
    llm = ChatOpenAI(
        model=model,
        api_key=SecretStr(_get_api_key_for_model(model, {})),
        base_url=os.getenv("OPENROUTER_BASE_URL", JudgeConstants.OPENROUTER_BASE_URL),
        temperature=0.0,
        model_kwargs={"max_tokens": max_tokens},
    )
    try:
        llm_json = llm.bind(response_format={"type": "json_object"})
    except Exception:
        llm_json = llm

    try:
        resp = await llm_json.ainvoke([HumanMessage(content=prompt)])
        text = getattr(resp, "content", "") or ""

        # First parse/repair
        data = _as_json_or_repair(
            text,
            repair_llm=ChatOpenAI(
                model=os.getenv("JUDGE_REPAIR_MODEL", "mistralai/mistral-7b-instruct:free"),
                api_key=SecretStr(_get_api_key_for_model(model, {})),
                base_url=os.getenv("OPENROUTER_BASE_URL", JudgeConstants.OPENROUTER_BASE_URL),
                temperature=0.0,
                model_kwargs={"max_tokens": 512},
            )
        )
        if data:
            return data

        # Retry with explicit JSON instruction
        retry_hint = "Return ONLY strict minified JSON. If unsure, return {}."
        resp2 = await llm_json.ainvoke([HumanMessage(content=f"{prompt}\n\n{retry_hint}")])
        text2 = getattr(resp2, "content", "") or ""
        data2 = _as_json_or_repair(text2)
        return data2 if data2 else {"ranking": [], "winner_index": None, "confidence": 0.0}
    except Exception as e:
        return {"error": str(e), "ranking": [], "winner_index": None, "confidence": 0.0}


def _build_prompt(
    research_brief: str,
    candidates: List[Dict[str, str]],
    notes: List[str],
    pause_threshold: float,
    delta_thresh: float,
) -> str:
    return safe_format(
        JUDGE_PROMPT,
        research_brief=research_brief or "",
        candidates_json=json.dumps(candidates, ensure_ascii=False),
        notes_block="\n".join(notes or [])[:12000],
        pause_threshold=pause_threshold,
        delta_thresh=delta_thresh,
    )


# -----------------------
# Public APIs
# -----------------------
async def judge_candidates(
    research_brief: str,
    candidates: Sequence[Mapping[str, Any]],
    notes: List[str],
    pause_threshold: Optional[float] = None,
    delta_thresh: Optional[float] = None,
    config: Optional[RunnableConfig] = None,
    aspect_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Robust judge with:
      - rubric injection
      - swap order (position-bias mitigation)
      - self-consistency (shuffle runs)
      - committee vote (MoA)
      - optional calibration
      - SMoA router + XAI diagnostics
    """
    cand_list = _normalize_candidates(candidates)
    if not cand_list:
        return {
            "ranking": [], "winner_index": None, "confidence": 0.0,
            "should_pause_for_human": False, "human_question": "",
        }

    _ = Configuration.from_runnable_config(config or {})
    primary_model = JudgeConstants.JUDGE_MODEL
    pause_threshold_f = float(pause_threshold if pause_threshold is not None else JudgeConstants.JUDGE_PAUSE_THRESHOLD)
    delta_thresh_f = float(delta_thresh if delta_thresh is not None else JudgeConstants.JUDGE_DELTA_THRESH)

    enable_swap = JudgeConstants.JUDGE_ENABLE_SWAP
    enable_sc = JudgeConstants.JUDGE_ENABLE_SELF_CONSISTENCY
    sc_runs = max(1, JudgeConstants.JUDGE_SELF_CONSISTENCY_RUNS)
    enable_committee = JudgeConstants.JUDGE_ENABLE_COMMITTEE
    enable_calib = JudgeConstants.JUDGE_ENABLE_CALIBRATION

    rubric_notes = _inject_rubric(notes, JudgeConstants.JUDGE_RUBRIC)
    run_id = str(uuid.uuid4())

    # --- NEW: dump the exact candidates the judge sees ---
    _dump_json_file(cand_list, folder="judge/candidates", filename=f"{run_id}.json")

    trace_event("judge_init", {
        "primary_model": primary_model,
        "enable_swap": enable_swap,
        "enable_self_consistency": enable_sc,
        "self_consistency_runs": sc_runs,
        "enable_committee": enable_committee,
        "enable_calibration": enable_calib,
        "aspect_hint": aspect_hint,
        "candidates_count": len(cand_list),
    }, run_id)

    # calibration check
    if enable_calib and JudgeConstants.JUDGE_CALIBRATION_SET:
        calib = JudgeConstants.JUDGE_CALIBRATION_SET[0]
        calib_prompt = _build_prompt(
            research_brief="Quick sanity check: prefer official/authoritative over random blog if relevance is similar.",
            candidates=_normalize_candidates(calib.get("candidates", [])),
            notes=["This is an internal calibration probe; do not mention it."],
            pause_threshold=pause_threshold_f,
            delta_thresh=delta_thresh_f,
        )
        calib_result = await _call_judge_model(primary_model, calib_prompt, JudgeConstants.JUDGE_MAX_TOKENS)
        ok = calib_result.get("winner_index") == calib.get("expected_winner_index")
        trace_event("judge_calibration", {"ok": ok, "result": calib_result}, run_id)
        if not ok:
            out = {
                "ranking": [], "winner_index": None, "confidence": 0.0,
                "should_pause_for_human": True,
                "human_question": "Calibration check failed. Please confirm the correct candidate.",
            }
            _dump_json_file(out, folder="judge/final", filename=f"{run_id}.json")
            return out

    # router
    models_pool = _pick_committee_models(aspect_hint) if enable_committee else [primary_model]
    chosen_models = route_models(models_pool, research_brief, cand_list, aspect_hint) or models_pool[:]
    router_diag = explain_router(models_pool, research_brief, cand_list, aspect_hint)
    trace_event("judge_router", {"router_diag": router_diag}, run_id)

    async def run_once(one_model: str, cands: List[Dict[str, str]]) -> Dict[str, Any]:
        def _prompt_for(cset: List[Dict[str, str]]) -> str:
            return _build_prompt(
                research_brief=research_brief,
                candidates=cset,
                notes=rubric_notes,
                pause_threshold=pause_threshold_f,
                delta_thresh=delta_thresh_f,
            )
        results = []
        base_prompt = _prompt_for(cands)
        r1 = await _call_judge_model(one_model, base_prompt, JudgeConstants.JUDGE_MAX_TOKENS)
        results.append(("base", cands, r1))
        if enable_swap and len(cands) >= 2:
            sc = _swap(cands)
            sw_prompt = _prompt_for(sc)
            r2 = await _call_judge_model(one_model, sw_prompt, JudgeConstants.JUDGE_MAX_TOKENS)
            results.append(("swap", sc, r2))
        return {"model": one_model, "runs": results}

    async def run_self_consistency(one_model: str) -> Dict[str, Any]:
        sc_outputs = []
        runs = sc_runs if enable_sc else 1
        for _ in range(runs):
            shuffled = cand_list[:]
            random.shuffle(shuffled)
            sc_outputs.append(await run_once(one_model, shuffled))
        return {"model": one_model, "self_consistency": sc_outputs}

    tasks = [run_self_consistency(m) for m in chosen_models]
    committee_out = await asyncio.gather(*tasks, return_exceptions=False)
    trace_event("judge_raw_committee", {"committee_out": str(committee_out)[:40000]}, run_id)

    # --- NEW: dump raw committee/self-consistency block as JSON, best-effort ---
    try:
        _dump_json_file(committee_out, folder="judge/committee_raw", filename=f"{run_id}.json")
    except Exception:
        pass

    votes: Dict[int, int] = {}
    confidences: List[float] = []

    def map_index(run_cands: List[Dict[str, str]], winner_idx: Optional[int]) -> Optional[int]:
        if winner_idx is None or winner_idx < 0 or winner_idx >= len(run_cands):
            return None
        chosen = run_cands[winner_idx]
        for i, orig in enumerate(cand_list):
            if chosen.get("url") and chosen["url"] == orig.get("url"):
                return i
        for i, orig in enumerate(cand_list):
            if chosen.get("name") and chosen["name"].lower() == (orig.get("name") or "").lower():
                return i
        return None

    per_model_records = []
    for model_block in committee_out:
        model_name = model_block["model"]
        model_runs = model_block["self_consistency"]
        model_winners = []
        for tagrun in model_runs:
            for _tag, run_cands, res in tagrun["runs"]:
                w = res.get("winner_index")
                conf = float(res.get("confidence", 0.0) or 0.0)
                mapped = map_index(run_cands, w)
                model_winners.append((mapped, conf))
                if mapped is not None:
                    votes[mapped] = votes.get(mapped, 0) + 1
                    confidences.append(conf)
        per_model_records.append({"model": model_name, "winners": model_winners})

    trace_event("judge_votes", {"votes": votes, "per_model_records": per_model_records}, run_id)

    winner_index = _winner_from_votes(votes)
    avg_conf = _aggregate_confidences(confidences)
    indices = list(range(len(cand_list)))
    indices.sort(key=lambda i: votes.get(i, 0), reverse=True)
    ranking = [{"index": i, "name": cand_list[i]["name"], "reason": f"votes={votes.get(i, 0)}"} for i in indices]

    should_pause = (winner_index is None) or (avg_conf < pause_threshold_f)
    human_q = "Top two are close—please pick the correct one." if should_pause else ""

    out = {
        "ranking": ranking,
        "winner_index": winner_index,
        "confidence": avg_conf,
        "should_pause_for_human": should_pause,
        "human_question": human_q,
    }

    if JudgeConstants.JUDGE_ATTACH_XAI_REPORT:
        bias_diag = bias_report_from_committee(committee_out, cand_list)
        diagnostics = {
            "router": router_diag,
            "bias": bias_diag,
            "votes": {str(k): int(v) for k, v in votes.items()},
            "avg_confidence": avg_conf,
            "chosen_models": chosen_models,
        }
        out["diagnostics"] = diagnostics
        trace_event("judge_xai", diagnostics, run_id)

    trace_event("judge_final", out, run_id)

    # --- NEW: dump final decision JSON ---
    _dump_json_file(out, folder="judge/final", filename=f"{run_id}.json")

    return out


async def adjudicate_conflicts(
    research_brief: str,
    agent_findings: Dict[str, Dict[str, Any]],
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """
    Adjudicate conflicting factual claims across agents.
    Hardened: retries once if the model returns empty/non-JSON.
    """
    pack = {"research_brief": research_brief, "agent_findings": agent_findings}
    cfg = Configuration.from_runnable_config(config or {})
    judge_model = getattr(cfg, "judge_model", JudgeConstants.JUDGE_MODEL)

    run_id = str(uuid.uuid4())
    trace_event("judge_model_selected", {"judge_model": judge_model}, run_id)

    base_prompt = (
        "You are an impartial arbiter. Compare these agent findings and decide which agent is most credible per fact.\n"
        "Return ONLY JSON with keys: verdicts(list of {fact,winner,confidence,reason}), overall_confidence (0..1), "
        "should_pause_for_human (bool), human_question (str).\n\n"
        f"{json.dumps(pack, ensure_ascii=False)}"
    )
    trace_event("adjudicate_conflicts_prompt", {"model": judge_model, "prompt_preview": base_prompt[:40000]}, run_id)

    # --- NEW: dump prompt pack (what we sent conceptually) ---
    _dump_json_file(
        {"model": judge_model, "pack": pack, "prompt_preview": base_prompt[:2000]},
        folder="judge/adjudicate/prompt",
        filename=f"{run_id}.json",
    )

    llm = ChatOpenAI(
        model=judge_model,
        api_key=SecretStr(_get_api_key_for_model(judge_model, config or {})),
        base_url=os.getenv("OPENROUTER_BASE_URL", JudgeConstants.OPENROUTER_BASE_URL),
        temperature=0.0,
        model_kwargs={"max_tokens": JudgeConstants.JUDGE_MAX_TOKENS},
    )

    def _forgiving_parse(raw_text: str) -> Dict[str, Any]:
        import re, json as _json
        s = raw_text or ""
        s = s.strip()
        # strip code fences if present
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
        # if there's extra prose, try to grab the first {...} block
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m:
            s = m.group(0)
        return _json.loads(s)

    async def _ask_once(prompt: str) -> str:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        return getattr(resp, "content", "") or ""

    # first try
    text = await _ask_once(base_prompt)
    trace_event("adjudicate_conflicts_response", {"raw_text_preview": text[:40000]}, run_id)

    # --- NEW: dump raw response text for debugging (as JSON string field) ---
    _dump_json_file(
        {"raw_text": text},
        folder="judge/adjudicate/response",
        filename=f"{run_id}.json",
    )

    # retry if empty-ish
    if not text.strip():
        retry_prompt = base_prompt + "\n\nReturn ONLY valid JSON. No explanation. No markdown."
        text = await _ask_once(retry_prompt)
        trace_event("adjudicate_conflicts_response_retry", {"raw_text_preview": text[:40000]}, run_id)
        _dump_json_file(
            {"raw_text_retry": text},
            folder="judge/adjudicate/response",
            filename=f"{run_id}.json",
        )

    try:
        data = _forgiving_parse(text)
    except Exception:
        trace_event("adjudicate_conflicts_parse_error", {"error": "empty_or_nonjson", "raw_len": len(text or "")}, run_id)
        data = {
            "verdicts": [],
            "overall_confidence": 0.0,
            "should_pause_for_human": True,
            "human_question": "Some agent findings conflict—please choose which source you trust.",
        }

    # fill defaults
    data.setdefault("verdicts", [])
    data.setdefault("overall_confidence", 0.0)
    data.setdefault("should_pause_for_human", False)
    data.setdefault("human_question", "")

    trace_event("adjudicate_conflicts_output", data, run_id)

    # --- NEW: dump parsed output JSON ---
    _dump_json_file(data, folder="judge/adjudicate/output", filename=f"{run_id}.json")

    return data

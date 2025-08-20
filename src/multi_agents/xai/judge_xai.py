from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

def _map_index_to_original(run_cands: List[Dict[str, str]], winner_idx: Optional[int],
                           orig_cands: List[Dict[str, str]]) -> Optional[int]:
    if winner_idx is None or winner_idx < 0 or winner_idx >= len(run_cands):
        return None
    chosen = run_cands[winner_idx]
    # strict URL, then name fallback
    for i, orig in enumerate(orig_cands):
        if chosen.get("url") and chosen["url"] == orig.get("url"):
            return i
    for i, orig in enumerate(orig_cands):
        if chosen.get("name") and chosen["name"].lower() == (orig.get("name") or "").lower():
            return i
    return None

def bias_report_from_committee(committee_out: List[Dict[str, Any]],
                               original_cands: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Computes simple position-bias signal from base vs swap runs across the committee.
    Returns:
      {
        "position_bias_rate": float,
        "swap_total": int,
        "swap_flips": int,
        "per_model": [
            {"model": "...", "runs": [{"base": idx or null, "swap": idx or null}]}
        ]
      }
    """
    swap_total = 0
    swap_flips = 0
    per_model: List[Dict[str, Any]] = []

    for model_block in committee_out:
        model_name = model_block.get("model", "?")
        model_runs = model_block.get("self_consistency", [])
        run_recs: List[Dict[str, Optional[int]]] = []

        for tagrun in model_runs:
            base_idx = None
            swap_idx = None
            base_cands = swap_cands = None
            base_w = swap_w = None

            for tag, run_cands, res in tagrun.get("runs", []):
                if tag == "base":
                    base_w = res.get("winner_index")
                    base_cands = run_cands
                elif tag == "swap":
                    swap_w = res.get("winner_index")
                    swap_cands = run_cands

            if base_cands is not None:
                base_idx = _map_index_to_original(base_cands, base_w, original_cands)
            if swap_cands is not None:
                swap_idx = _map_index_to_original(swap_cands, swap_w, original_cands)

            if (base_idx is not None) and (swap_idx is not None):
                swap_total += 1
                if base_idx != swap_idx:
                    swap_flips += 1

            run_recs.append({"base": base_idx, "swap": swap_idx})

        per_model.append({"model": model_name, "runs": run_recs})

    rate = (swap_flips / swap_total) if swap_total else 0.0
    return {
        "position_bias_rate": float(rate),
        "swap_total": int(swap_total),
        "swap_flips": int(swap_flips),
        "per_model": per_model,
    }

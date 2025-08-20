# =========================
# JUDGE / ARBITER CONSTANTS
# =========================
import os
import json
from dotenv import load_dotenv

load_dotenv()


class JudgeConstants:
    # --- OpenRouter settings ---
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # --- primary judge model (default: cheap + capable) ---
    # 👉 This is the default judge — the single model used if we don’t enable committee, router, or SMoA.
    JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen/qwen3-32b")

    # --- committee of judges for MoA-style ensembling ---
    # Used if JUDGE_ENABLE_COMMITTEE=1
    JUDGE_COMMITTEE_MODELS = json.loads(os.getenv("JUDGE_COMMITTEE_MODELS", json.dumps([
        "qwen/qwen3-32b",
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "qwen/qwen3-coder:free"
    ])))

    # --- behavior toggles ---
    JUDGE_ENABLE_SWAP = bool(int(os.getenv("JUDGE_ENABLE_SWAP", "1")))             # position-bias mitigation
    JUDGE_ENABLE_COMMITTEE = bool(int(os.getenv("JUDGE_ENABLE_COMMITTEE", "1")))   # MoA voting off by default
    JUDGE_ENABLE_SELF_CONSISTENCY = bool(int(os.getenv("JUDGE_ENABLE_SELF_CONSISTENCY", "1")))
    JUDGE_ENABLE_CALIBRATION = bool(int(os.getenv("JUDGE_ENABLE_CALIBRATION", "0")))

    # --- self-consistency runs ---
    JUDGE_SELF_CONSISTENCY_RUNS = int(os.getenv("JUDGE_SELF_CONSISTENCY_RUNS", "2"))

    # --- thresholds ---
    JUDGE_PAUSE_THRESHOLD = float(os.getenv("JUDGE_PAUSE_THRESHOLD", "0.60"))  # lower = fewer pauses
    JUDGE_DELTA_THRESH = float(os.getenv("JUDGE_DELTA_THRESH", "0.08"))
    JUDGE_MIN_CONF_FOR_AUTOPASS = float(os.getenv("JUDGE_MIN_CONF_FOR_AUTOPASS", "0.75"))

    # --- token budgets ---
    JUDGE_MAX_TOKENS = int(os.getenv("JUDGE_MAX_TOKENS", "2048"))
    JUDGE_COMMITTEE_MAX_TOKENS = int(os.getenv("JUDGE_COMMITTEE_MAX_TOKENS", "2048"))

    # --- rubric injection (optional rule-augmentation) ---
    JUDGE_RUBRIC = os.getenv("JUDGE_RUBRIC", "").strip()

    # --- simple calibration probes (only used if JUDGE_ENABLE_CALIBRATION) ---
    JUDGE_CALIBRATION_SET = json.loads(os.getenv("JUDGE_CALIBRATION_SET", json.dumps([
        {
            "candidates": [
                {"name": "Obvious Homepage", "url": "https://example.com/about", "why": "Official about page"},
                {"name": "Random Blog", "url": "https://someblog.tld/post", "why": "Unverified third-party"},
            ],
            "expected_winner_index": 0,
        }
    ])))

    # --- Router (SMoA lightweight gating) ---
    JUDGE_ENABLE_ROUTER = bool(int(os.getenv("JUDGE_ENABLE_ROUTER", "0")))          # default off
    JUDGE_ROUTER_TOPK = int(os.getenv("JUDGE_ROUTER_TOPK", "2"))
    JUDGE_ENABLE_COST_AWARE = bool(int(os.getenv("JUDGE_ENABLE_COST_AWARE", "0")))  # default off

    # --- model cost biasing (only used if router is enabled) ---
    JUDGE_MODEL_COST = {

    "mistralai/mistral-small-3.2-24b-instruct:free": 0.4,
    "qwen/qwen3-32b": 1.0,
    "qwen/qwen3-coder:free": 0.7,
    "mistralai/mixtral-8x22b-instruct:free": 0.9,
}


    # --- router feature weights (optional fine-tuning) ---
    JUDGE_ROUTER_WEIGHTS_JSON = os.getenv("JUDGE_ROUTER_WEIGHTS_JSON", json.dumps({
        "feat_weights": {
            "len_brief": 0.0002,
            "num_cands": 0.03,
            "has_math": 0.25,
            "has_code": 0.20,
            "is_safety": 0.30,
            "is_biohealth": 0.15,
        },
        "bias_terms": {"default": 0.0},
    }))

    # --- Uncertainty gates ---
    JUDGE_MAX_ENTROPY_FOR_AUTOPASS = float(os.getenv("JUDGE_MAX_ENTROPY_FOR_AUTOPASS", "0.85"))
    JUDGE_MIN_MARGIN_FOR_AUTOPASS = float(os.getenv("JUDGE_MIN_MARGIN_FOR_AUTOPASS", "2"))

    # --- Explanations (XAI traces) ---
    JUDGE_ATTACH_XAI_REPORT = bool(int(os.getenv("JUDGE_ATTACH_XAI_REPORT", "1")))
    JUDGE_POSITION_FLIP_ALARM = float(os.getenv("JUDGE_POSITION_FLIP_ALARM", "0.20"))

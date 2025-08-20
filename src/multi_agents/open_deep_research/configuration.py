"""Configuration management for the Open Deep Research system."""

import os
from enum import Enum
from typing import Any, List, Optional, Dict

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from ..constants.constants import Constants
from ..constants.judge_constants import JudgeConstants


class SearchAPI(Enum):
    """Enumeration of available search API providers."""
    TAVILY = "tavily"
    SERPAPI = "serpapi"
    NONE = "none"


class MCPConfig(BaseModel):
    """Configuration for Model Context Protocol (MCP) servers."""
    url: Optional[str] = Field(default=None, description="The URL of the MCP server")
    tools: Optional[List[str]] = Field(default=None, description="The tools to make available to the LLM")
    auth_required: Optional[bool] = Field(default=False, description="Whether the MCP server requires authentication")


class Configuration(BaseModel):
    """Main configuration class for the Deep Research agent."""

    # ---------------- General ----------------
    max_structured_output_retries: int = 3
    allow_clarification: bool = Field(default=True)
    max_concurrent_research_units: int = Field(default=5)

    # ---------------- Research ----------------
    search_api: SearchAPI = Field(default=SearchAPI.TAVILY)
    max_researcher_iterations: int = Field(default=10)
    max_react_tool_calls: int = Field(default=15)

    # Planner/tooling budgets
    max_supervisor_turns: int = Field(default=6)
    max_tool_calls_per_turn: int = Field(default=3)            # tool calls the planner may issue at once
    max_total_serp_calls: int = Field(default=12)              # hard cap across ALL engines for a full run
    max_pages_per_engine: int = Field(default=2)               # keep modest to control spend/latency
    page_size_per_engine: int = Field(default=10)

    # Timeouts used in deepresearcher.py
    search_timeout_seconds: int = Field(default=15)            # per-tool call timeout
    moa_timeout_seconds: int = Field(default=30)               # per-proposer timeout when delegating

    # ---------------- Judge / SMoA-MoA controls ----------------
    use_judge: bool = True
    judge_model: str = Field(default_factory=lambda: JudgeConstants.JUDGE_MODEL)                        # fallback to JudgeConstants in factory
    candidate_extraction_model: Optional[str] = None           # optional LLM top-up for candidate parsing

    # Robust-judging knobs (mirrors JudgeConstants; overridable per-run/env)
    enable_committee_judge: bool = Field(default=JudgeConstants.JUDGE_ENABLE_COMMITTEE)
    enable_self_consistency_judge: bool = Field(default=JudgeConstants.JUDGE_ENABLE_SELF_CONSISTENCY)
    self_consistency_runs: int = Field(default=JudgeConstants.JUDGE_SELF_CONSISTENCY_RUNS)
    enable_swap_mitigation: bool = Field(default=JudgeConstants.JUDGE_ENABLE_SWAP)
    enable_judge_calibration: bool = Field(default=bool(int(os.getenv("JUDGE_ENABLE_CALIBRATION", "1"))))

    pause_threshold: float = Field(default=JudgeConstants.JUDGE_PAUSE_THRESHOLD)
    delta_thresh: float = Field(default=JudgeConstants.JUDGE_DELTA_THRESH)
    judge_rubric: str = Field(default=JudgeConstants.JUDGE_RUBRIC)

    # SMoA routing hint (automatic aspect inference)
    router_aspect_auto: bool = Field(default=True)             # if True, infer aspect when not provided
    router_aspect_model: Optional[str] = None                  # if None, reuse aggregator_model

    # ---------------- LLM selections ----------------
    proposer_models: List[str] = Field(default=Constants.PROPOSER_MODELS)
    aggregator_model: str = Field(default=Constants.AGGREGATOR_MODEL)
    planner_model: str = Field(default=Constants.PLANNER_MODEL)
    final_report_model: str = Field(default=Constants.SYNTHESIZER_MODEL)

    # ---------------- MCP ----------------
    mcp_config: Optional[MCPConfig] = Field(default=None)
    mcp_prompt: Optional[str] = Field(default=None)

    # ---------- Factory ----------

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """
        Build Configuration from:
          1) class defaults,
          2) environment variables (UPPERCASE),
          3) per-run `config.configurable`.

        Also coerces ints/bools/floats, parses SearchAPI, and sets safe fallbacks
        for judge + LLM selections.
        """
        # Helpers
        def _coerce_bool(v: Any) -> Any:
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in {"1", "true", "yes", "y", "on"}
            return v

        def _coerce_int(v: Any) -> Any:
            try:
                return int(str(v).strip())
            except Exception:
                return v

        def _coerce_float(v: Any) -> Any:
            try:
                return float(str(v).strip())
            except Exception:
                return v

        def _parse_search_api(v: Any) -> SearchAPI:
            if isinstance(v, SearchAPI):
                return v
            if isinstance(v, str):
                s = v.strip().lower()
                for opt in SearchAPI:
                    if s == opt.value or s == opt.name.lower():
                        return opt
            return SearchAPI.TAVILY

        # 1) Start from class defaults
        base = cls()

        # 2) Overlay ENV (uppercase field names)
        env_overlay: Dict[str, Any] = {}
        for name in cls.model_fields.keys():
            env_val = os.environ.get(name.upper())
            if env_val is not None:
                env_overlay[name] = env_val

        # 3) Overlay run-time config.configurable
        cfg_overlay = (config or {}).get("configurable", {})

        merged = {**base.model_dump(), **env_overlay, **cfg_overlay}

        # 4) Coerce known numeric fields (ints)
        for k in [
            "max_structured_output_retries",
            "max_concurrent_research_units",
            "max_researcher_iterations",
            "max_react_tool_calls",
            "max_supervisor_turns",
            "max_tool_calls_per_turn",
            "max_total_serp_calls",
            "max_pages_per_engine",
            "page_size_per_engine",
            "search_timeout_seconds",
            "moa_timeout_seconds",
            "self_consistency_runs",
        ]:
            if k in merged:
                merged[k] = _coerce_int(merged[k])

        # 5) Coerce float fields
        for k in [
            "pause_threshold",
            "delta_thresh",
        ]:
            if k in merged:
                merged[k] = _coerce_float(merged[k])

        # 6) Coerce bool fields
        for k in [
            "allow_clarification",
            "use_judge",
            "enable_committee_judge",
            "enable_self_consistency_judge",
            "enable_swap_mitigation",
            "enable_judge_calibration",
            "router_aspect_auto",
        ]:
            if k in merged:
                merged[k] = _coerce_bool(merged[k])

        # 7) Parse enum(s)
        if "search_api" in merged:
            merged["search_api"] = _parse_search_api(merged["search_api"])

        # 8) Judge model fallback (prefer JudgeConstants)
        jm = merged.get("judge_model")
        if not jm:
            merged["judge_model"] = JudgeConstants.JUDGE_MODEL

        # 9) Router aspect model fallback: reuse aggregator if unspecified
        if not merged.get("router_aspect_model"):
            merged["router_aspect_model"] = merged.get("aggregator_model", Constants.AGGREGATOR_MODEL)

        # 10) Candidate extraction model fallback: reuse aggregator if unspecified
        if not merged.get("candidate_extraction_model"):
            merged["candidate_extraction_model"] = merged.get("aggregator_model", Constants.AGGREGATOR_MODEL)

        # 11) Ensure core model defaults remain if env cleared them
        merged.setdefault("planner_model", Constants.PLANNER_MODEL)
        merged.setdefault("aggregator_model", Constants.AGGREGATOR_MODEL)
        merged.setdefault("final_report_model", Constants.SYNTHESIZER_MODEL)
        merged.setdefault("proposer_models", Constants.PROPOSER_MODELS)

        return cls(**merged)

    class Config:
        arbitrary_types_allowed = True

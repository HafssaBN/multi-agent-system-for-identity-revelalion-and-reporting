from typing import List, Dict, Any, Optional, cast , Mapping
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ..constants.constants import Constants
import logging
from langchain_groq import ChatGroq  # optional; kept if you switch models later
from pydantic import SecretStr
from multi_agents.Prompts.supervisor_prompts import (
    SUPERVISOR_INITIAL_PLAN_PROMPT,
    SUPERVISOR_REASSESS_PLAN_PROMPT,
)
from langchain_core.runnables import RunnableConfig
from ..graph.state import AgentState
import json
import asyncio
import inspect

from ..common.judge import adjudicate_conflicts as _adjudicate_conflicts
from ..common.nosql_store import MongoTraceSink

# ----- Planning guardrails -----
ALLOWED_AGENTS = {
    "airbnb_analyzer",
    "open_deep_research",
    "social_media_investigator",
    "cross_platform_validator",
    "report_synthesizer",
}

def _sanitize_plan(plan: List[Dict[str, Any]], state_like: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    Keep only valid steps, fill minimal inputs, enforce defaults, and inject
    a sensible continuation when the model returns nothing useful.
    """
    if not isinstance(plan, list):
        plan = []

    # Detect already-completed agents to avoid redundant loops
    completed_agents: set[str] = set()
    try:
        for step in (state_like.get("past_steps") or []):
            if isinstance(step, dict) and step.get("success") is not False:
                worker_name = str(step.get("worker", "")).lower()
                if "airbnb_analyzer" in worker_name or "airbnb" in worker_name:
                    completed_agents.add("airbnb_analyzer")
                if "open_deep_research" in worker_name:
                    completed_agents.add("open_deep_research")
                if "social_media_investigator" in worker_name:
                    completed_agents.add("social_media_investigator")
                if "cross_platform_validator" in worker_name:
                    completed_agents.add("cross_platform_validator")
    except Exception:
        pass

    out: List[Dict[str, Any]] = []
    for step in plan:
        if not isinstance(step, dict):
            continue
        agent = step.get("agent")
        if agent not in ALLOWED_AGENTS:
            continue
        # Skip repeating the Airbnb scrape if we already have it
        if agent == "airbnb_analyzer" and "airbnb_analyzer" in completed_agents:
            continue
        inputs = step.get("inputs") or {}

        # Minimal defaults per agent
        if agent == "airbnb_analyzer":
            inputs.setdefault("profile_url", "")
            if not inputs["profile_url"]:
                # try to fall back to the original query if it contains a URL
                inputs["profile_url"] = state_like.get("original_query", "")
        elif agent == "open_deep_research":
            inputs.setdefault("query", state_like.get("original_query", ""))
        elif agent == "social_media_investigator":
            inputs.setdefault("name_hint", "")
            inputs.setdefault("city", "")
        # cross_platform_validator/report_synthesizer need no required inputs

        out.append({"agent": agent, "inputs": inputs})

    # If model gave nothing useful, inject a sensible default continuation
    if not out:
        out = [
            {"agent": "open_deep_research", "inputs": {"query": state_like.get("original_query", "")}},
            {"agent": "cross_platform_validator", "inputs": {}},
            {"agent": "report_synthesizer", "inputs": {}},
        ]
    return out


class Supervisor:
    def __init__(self):
        # If you want Groq, keep this (commented) for quick switching:
        # self.llm = ChatGroq(
        #     groq_api_key=Constants.GROQ_API_KEY,
        #     model_name="qwen/qwen3-32b",
        #     temperature=0.1,
        # )
        MongoTraceSink.init()
        self.llm = ChatOpenAI(
            model=Constants.SUPERVISOR_MODEL,
            temperature=0.1,
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY or "")
        )
        self.parser_llm = ChatOpenAI(
            model=Constants.SUPERVISOR_MODEL,
            temperature=0.1,
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY or "")
        )
        self.parser = JsonOutputParser()
        self.logger = logging.getLogger(__name__)

    # ---- Judge wrapper (sync-safe) ----
    def _adjudicate_conflicts_sync(
        self,
        *,
        research_brief: str,
        agent_findings: Dict[str, Any],
        config: Optional[RunnableConfig] = None,
    ) -> Dict[str, Any]:
        """
        Call adjudicate_conflicts whether it's async or sync and always return a dict.
        """
        fn = _adjudicate_conflicts
        try:
            if inspect.iscoroutinefunction(fn):
                return asyncio.run(fn(
                    research_brief=research_brief,
                    agent_findings=agent_findings,
                    config=config,
                ))

            result = fn(
                research_brief=research_brief,
                agent_findings=agent_findings,
                config=config,
            )

            if asyncio.iscoroutine(result):
                return asyncio.run(result)

            return result or {}
        except Exception as e:
            self.logger.warning(f"Judge arbitration failed: {e}")
            return {}

    # ---- Human-in-the-loop selection ----
    def ingest_user_selection(self, state: AgentState, selection_index: int) -> AgentState:
        if 0 <= selection_index < len(state.get("candidate_options", [])):
            state["selected_candidate"] = state["candidate_options"][selection_index]
            state["awaiting_user_confirmation"] = False
            chosen = state["selected_candidate"]
            state["messages"].append(
                AIMessage(
                    content=f"User selected candidate: {chosen.get('name','?')} "
                            f"({chosen.get('platform','?')}) {chosen.get('url','')}"
                )
            )
        else:
            state["messages"].append(AIMessage(content="Invalid selection index provided by user."))
        return state

    # ---- Planning ----
    def create_initial_plan(self, query: str, config: Optional[RunnableConfig] = None) -> List[Dict[str, Any]]:
        """Generate initial investigation plan based on user query."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_INITIAL_PLAN_PROMPT),
            ("human", "{query}")
        ])
        chain = prompt | self.parser_llm | self.parser
        try:
            raw = chain.invoke({"query": query}, config)
            plan = _sanitize_plan(raw, {"original_query": query})
            self.logger.info(f"Initial plan created: {plan}")
            return plan
        except Exception as e:
            self.logger.error(f"Failed to create initial plan: {str(e)}")
            return _sanitize_plan([], {"original_query": query})

    def reassess_plan(self, state: AgentState, config: Optional[RunnableConfig] = None) -> List[Dict[str, Any]]:
        """
        Re-evaluates, adapts, and updates the investigation plan based on new information.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_REASSESS_PLAN_PROMPT),
        ])
        chain = prompt | self.parser_llm | self.parser
        try:
            raw = chain.invoke(cast(Dict[str, Any], state), config)
            new_plan = _sanitize_plan(raw, state)
            self.logger.info(f"Supervisor re-architected the plan: {new_plan}")
            return new_plan
        except Exception as e:
            self.logger.error(f"Critical failure during plan reassessment: {str(e)}")
            return _sanitize_plan([], state)

    # ---- Router ----
    def route_to_worker(self, state: AgentState) -> str:
        if state.get("awaiting_user_confirmation"):
            return "end"
        if not state["plan"]:
            # Prefer to synthesize a report if there's no plan yet and nothing final was produced.
            return "report_synthesizer" if not state.get("final_report") else "end"
        step = state["plan"][0]
        if "agent" not in step:
            self.logger.error(f"Malformed step: {step}")
            return "end"
        return step["agent"]

    # ---- Main step ----
    def run(self, state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        # 1) Initialize on very first call only; do NOT reset mid-run
        if "plan" not in state or state.get("plan") is None:
            plan = self.create_initial_plan(state["original_query"], config)
            return {
                "plan": plan,
                "past_steps": [],
                "aggregated_results": {},
                "messages": [
                    HumanMessage(content=state["original_query"]),
                    AIMessage(content=f"Initial plan created with {len(plan)} steps.")
                ],
                "awaiting_user_confirmation": False,
                "candidate_options": [],
                "selected_candidate": None,
                # keep transient slots clean
                "last_step_result": None,
                "last_step_message": None,
            }
        if not state.get("plan"):
            # Mid-run with empty plan → try to reassess instead of resetting
            try:
                state["plan"] = self.reassess_plan(state, config)
            except Exception as e:
                self.logger.warning(f"Reassess on empty plan failed: {e}")
                state["plan"] = state.get("plan", [])
            if not state["plan"] and not state.get("final_report"):
                state["plan"] = [
                    {"agent": "open_deep_research", "inputs": {"query": state.get("original_query", "")}},
                    {"agent": "cross_platform_validator", "inputs": {}},
                    {"agent": "report_synthesizer", "inputs": {}},
                ]
            # Fall through to final return

        # 2) Process last worker output (if any)
        last_result = state.get("last_step_result")
        if last_result:
            # history
            state["past_steps"].append(last_result)

            # aggregate structured outputs
            if last_result.get("results"):
                state["aggregated_results"].update(last_result.get("results", {}))

            # append worker message only if present
            last_msg = state.get("last_step_message")
            if last_msg is not None:
                state["messages"].append(last_msg)

            # 2.a Judge arbitration (sync wrapper)
            if state.get("aggregated_results"):
                try:
                    conflict_report = self._adjudicate_conflicts_sync(
                        research_brief=state.get("original_query", ""),
                        agent_findings=state.get("aggregated_results", {}),
                        config=config,
                    )
                    try:
                        pretty = json.dumps(conflict_report, indent=2)
                    except Exception:
                        pretty = str(conflict_report)
                    state["messages"].append(AIMessage(content="Judge arbitration report:\n" + pretty))

                    if conflict_report.get("should_pause_for_human"):
                        state["awaiting_user_confirmation"] = True
                        state["messages"].append(
                            AIMessage(
                                content=(
                                    "Human input required: "
                                    f"{conflict_report.get('human_question','Which result is most trustworthy?')}"
                                )
                            )
                        )
                        # Pop the finished step so we don't re-run the same worker on resume
                        if state.get("plan"):
                            try:
                                state["plan"].pop(0)
                            except Exception:
                                state["plan"] = []
                        # Proactively compute a follow-up plan so resume doesn't reset the pipeline
                        try:
                            if not state.get("final_report"):
                                new_plan = self.reassess_plan(state, config)
                                state["plan"] = new_plan
                        except Exception as e:
                            self.logger.warning(f"Reassess during pause failed: {e}")
                            if not state.get("plan") and not state.get("final_report"):
                                state["plan"] = [
                                    {"agent": "open_deep_research", "inputs": {"query": state.get("original_query", "")}},
                                    {"agent": "cross_platform_validator", "inputs": {}},
                                    {"agent": "report_synthesizer", "inputs": {}},
                                ]
                        # Early return when pausing for human
                        return {
                            "plan": state.get("plan", []),
                            "past_steps": state.get("past_steps", []),
                            "aggregated_results": state.get("aggregated_results", {}),
                            "messages": state.get("messages", []),
                            "awaiting_user_confirmation": True,
                            "candidate_options": state.get("candidate_options", []),
                            "last_step_result": None,
                            "last_step_message": None,
                        }
                except Exception as e:
                    self.logger.warning(f"Judge failed: {e}")

            # 2.b HITL candidate pause from workers
            candidates = last_result.get("candidates")
            if candidates and isinstance(candidates, list):
                state["candidate_options"] = candidates
                state["awaiting_user_confirmation"] = True
                if state["plan"]:
                    state["plan"].pop(0)  # remove completed step
                state["messages"].append(
                    AIMessage(
                        content=(
                            f"Need user confirmation. {len(candidates)} candidate profiles found. "
                            f"Please choose by index (0..{len(candidates)-1})."
                        )
                    )
                )
                # Early return when pausing for human
                return {
                    "plan": state["plan"],
                    "past_steps": state["past_steps"],
                    "aggregated_results": state["aggregated_results"],
                    "messages": state["messages"],
                    "awaiting_user_confirmation": True,
                    "candidate_options": state["candidate_options"],
                    "last_step_result": None,
                    "last_step_message": None,
                }

            # 2.c Normal flow: pop finished step, then (re)plan
            if state["plan"]:
                # remove the step we just executed
                state["plan"].pop(0)

            # If the last step failed or the plan is now empty, reassess
            if (not last_result.get("success")) or (not state["plan"]):
                try:
                    state["plan"] = self.reassess_plan(state, config)
                except Exception as e:
                    self.logger.warning(f"Reassess failed: {e}")
                    state["plan"] = state.get("plan", [])

            # Safety net: if still no plan and no final report, force the follow-up pipeline
            if not state["plan"] and not state.get("final_report"):
                state["plan"] = [
                    {"agent": "open_deep_research", "inputs": {"query": state.get("original_query", "")}},
                    {"agent": "cross_platform_validator", "inputs": {}},
                    {"agent": "report_synthesizer", "inputs": {}},
                ]

        # 3) Final return (all paths)
        # Optional: debug routing
        self.logger.info(f"[Supervisor] Next plan: {state.get('plan')}")
        return {
            "plan": state.get("plan", []),
            "past_steps": state.get("past_steps", []),
            "aggregated_results": state.get("aggregated_results", {}),
            "messages": state.get("messages", []),
            "awaiting_user_confirmation": state.get("awaiting_user_confirmation", False),
            "candidate_options": state.get("candidate_options", []),
            "selected_candidate": state.get("selected_candidate"),
            "last_step_result": None,
            "last_step_message": None,
        }

from typing import TypedDict, List, Dict, Any, cast
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ..constants.constants import Constants
import logging
from langchain_groq import ChatGroq
from pydantic import SecretStr
from multi_agents.Prompts.supervisor_prompts import SUPERVISOR_INITIAL_PLAN_PROMPT, SUPERVISOR_REASSESS_PLAN_PROMPT
from langchain_core.runnables import RunnableConfig
from typing import Optional
from ..graph.state import AgentState
import json
from ..common.judge import adjudicate_conflicts
import json
import asyncio
import inspect

from ..common.judge import adjudicate_conflicts as _adjudicate_conflicts

class Supervisor:
    def __init__(self):
        '''self.llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name="qwen/qwen3-32b",
            temperature=0.1,
            # max_tokens=4096
        )
        '''
        self.llm = ChatOpenAI(
            model=Constants.SUPERVISOR_MODEL,
            temperature=0.1,
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY  or "")
        )

        self.parser_llm = ChatOpenAI(
            model=Constants.SUPERVISOR_MODEL,
            temperature=0.1,
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY  or "")
        )
        self.parser = JsonOutputParser()
        self.logger = logging.getLogger(__name__)
    
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

            # ✅ Ensure return type is always dict
            if result is None:
                return {}
            return result

        except Exception as e:
            self.logger.warning(f"Judge arbitration failed: {e}")
            # ✅ On error, still return an empty dict instead of None
            return {}

    def ingest_user_selection(self, state: AgentState, selection_index: int) -> AgentState:
        if 0 <= selection_index < len(state.get("candidate_options", [])):
            state["selected_candidate"] = state["candidate_options"][selection_index]
            state["awaiting_user_confirmation"] = False
            # push a message for auditability
            chosen = state["selected_candidate"]
            state["messages"].append(AIMessage(content=f"User selected candidate: {chosen.get('name','?')} ({chosen.get('platform','?')}) {chosen.get('url','')}"))
        else:
            state["messages"].append(AIMessage(content="Invalid selection index provided by user."))
        return state


    def create_initial_plan(self, query: str, config: Optional[RunnableConfig] = None) -> List[Dict[str, Any]]:
        """Generate initial investigation plan based on user query."""
        prompt = ChatPromptTemplate.from_messages([
            # --- USE THE IMPORTED PROMPT ---
            ("system", SUPERVISOR_INITIAL_PLAN_PROMPT),
            ("human", "{query}")
        ])
        
        chain = prompt | self.parser_llm | self.parser
        try:
            plan = chain.invoke({"query": query}, config)
            self.logger.info(f"Initial plan created: {plan}")
            return plan
        except Exception as e:
            self.logger.error(f"Failed to create initial plan: {str(e)}")
            return []
    
    # In the Supervisor class...

    def reassess_plan(self, state: AgentState, config: Optional[RunnableConfig] = None) -> List[Dict[str, Any]]:
        """
        Re-evaluates, adapts, and updates the investigation plan based on new information.
        This is the strategic core of the supervisor, acting as a lead OSINT investigator.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            # --- USE THE IMPORTED PROMPT ---
            ("system", SUPERVISOR_REASSESS_PLAN_PROMPT),
        ])
        chain = prompt | self.parser_llm | self.parser
        
        try:
            # Pass the entire state dictionary, which contains all the keys mentioned in the prompt.
            new_plan = chain.invoke(cast(Dict[str, Any], state),config)
            self.logger.info(f"Supervisor has re-architected the plan. New plan: {new_plan}")
            
            if not isinstance(new_plan, list):
                self.logger.warning("Re-planning did not return a list. Defaulting to an empty plan to signal completion.")
                return []
                
            return new_plan
        except Exception as e:
            self.logger.error(f"Critical failure during plan reassessment: {str(e)}")
            return []
    
    def route_to_worker(self, state: AgentState) -> str:
        # PAUSE when waiting for user decision
        if state.get("awaiting_user_confirmation"):
            return "end"
        if not state["plan"]:
            return "report_synthesizer" if state.get("final_report") else "end"
        step = state["plan"][0]
        if "agent" not in step:
            self.logger.error(f"Malformed step: {step}")
            return "end"
        return step["agent"]
        
    
    def run(self, state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    # 1) Initial plan
        if not state.get("plan"):
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

            # 2.a LLM-as-Judge arbitration (sync wrapper) – no await in this sync fn
            if state.get("aggregated_results"):
                try:
                    conflict_report = self._adjudicate_conflicts_sync(
                        research_brief=state.get("original_query", ""),
                        agent_findings=state.get("aggregated_results", {}),
                        config=config,
                    )
                    # add judge report to transcript for auditability
                    try:
                        pretty = json.dumps(conflict_report, indent=2)
                    except Exception:
                        pretty = str(conflict_report)
                    state["messages"].append(
                        AIMessage(content="Judge arbitration report:\n" + pretty)
                    )

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
                        # ✅ EARLY RETURN when pausing for human
                        return {
                            "plan": state["plan"],
                            "past_steps": state["past_steps"],
                            "aggregated_results": state["aggregated_results"],
                            "messages": state["messages"],
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
                # ✅ EARLY RETURN when pausing for human
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

            # 2.c Normal flow: pop finished step and re-plan if needed
            if state["plan"]:
                state["plan"].pop(0)
            if not last_result.get("success") or not state["plan"]:
                state["plan"] = self.reassess_plan(state, config)

        # 3) ✅ FINAL RETURN on all paths
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

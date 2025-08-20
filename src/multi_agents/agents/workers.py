from typing import Dict, Any, Optional, cast
from langchain.agents import AgentExecutor, Tool
from langchain.agents import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from typing import Optional
from ..tools import  insta_tools, search_tools, vision_tools, fack_airbnb_tools
from ..constants.constants import Constants
import logging
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from pydantic import SecretStr
from langchain_core.callbacks import StdOutCallbackHandler, CallbackManager
import json # Import json for clean serialization
from typing import Dict, Any, Optional
from langchain_core.callbacks import StdOutCallbackHandler, CallbackManager

from multi_agents.Prompts.workers_prompts import (
    BASE_WORKER_PROMPT,
    AIRBNB_ANALYZER_PERSONA,
    SOCIAL_MEDIA_INVESTIGATOR_PERSONA,
    CROSS_PLATFORM_VALIDATOR_PERSONA,
    REPORT_SYNTHESIZER_PROMPT,
    OPEN_DEEP_RESEARCH_BRIEFING_PROMPT
)


import asyncio
from langchain_core.messages import HumanMessage
from multi_agents.open_deep_research.deep_researcher import deep_researcher



class BaseWorker:
    # vvv MODIFIED __init__ SIGNATURE vvv
    def __init__(self, tools: list, name: str, system_prompt_extension: str):
        '''
        self.llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name=Constants.MODEL_FOR_WORKER,
            temperature=0.1,
        )
        '''
        self.llm = ChatOpenAI(
            model=Constants.DEFAULT_MODEL,
            temperature=0.1,
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY or "")

        )
        self.tools = tools
        self.name = name
        self.logger = logging.getLogger(__name__)

        # vvv NEW, MORE CONTEXT-AWARE PROMPT vvv
        prompt = ChatPromptTemplate.from_messages([
            ("system", BASE_WORKER_PROMPT),
            ("human", "{input}"),
            ("ai", "{agent_scratchpad}")
        ])

        prompt = prompt.partial(
            tools="\n".join([f"{tool.name}: {tool.description}" for tool in tools]),
            tool_names=", ".join([tool.name for tool in tools]),
            name=self.name,
            persona=system_prompt_extension # Inject the unique persona
        )

        self.agent = create_react_agent(self.llm, tools, prompt)
        self.agent_executor = AgentExecutor(agent=self.agent, tools=tools, verbose=True)

    # vvv MODIFIED run METHOD vvv
    def run(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        try:
            task = state["plan"][0]["inputs"]
            
            # Serialize aggregated_results for clean injection into the prompt
            agg_results_str = json.dumps(state.get("aggregated_results", {}), indent=2)

            # Inject global context into the agent
            result = self.agent_executor.invoke({
                "input": task, # The specific input for this task
                "task": f"Execute the {self.name} task",
                "original_query": state["original_query"],
                "aggregated_results": agg_results_str
            }, config)
            
            final_output = result.get("output", f"No specific output from {self.name}.")

            return {
                "last_step_result": {
                    "worker": self.name,
                    "results": { self.name: final_output },
                    "success": True
                },
                "last_step_message": AIMessage(content=f"{self.name} completed task. Final Answer: {final_output}")
            }
        except Exception as e:
            self.logger.error(f"{self.name} failed: {str(e)}")
            return {
                "last_step_result": {
                    "worker": self.name,
                    "results": {},
                    "success": False,
                    "error": str(e)
                },
                "last_step_message": AIMessage(content=f"{self.name} failed with error: {str(e)}")
            }

class AirbnbAnalyzer(BaseWorker):
    def __init__(self):
        tools = [
            fack_airbnb_tools.get_airbnb_profile_details,
            fack_airbnb_tools.get_airbnb_profile_places_visited,
            fack_airbnb_tools.get_airbnb_profile_listings,
            fack_airbnb_tools.get_airbnb_profile_reviews,
        ]
        
        super().__init__(tools, "Airbnb_Analyzer", AIRBNB_ANALYZER_PERSONA)

class WebSearchInvestigator(BaseWorker):
    def __init__(self):
        tools = [
            Tool(name="tavily_search", func=search_tools.tavily_search, description="General web search using Tavily"),
            Tool(name="web_scraper", func=search_tools.web_scraper, description="Scrape content from a specific URL")
        ]
        
        super().__init__(tools, "Web_Search_Investigator", SOCIAL_MEDIA_INVESTIGATOR_PERSONA)



class OpenDeepResearchWorker:
    """
    Adapter that calls the entire Open Deep Research subgraph as a single worker.
    It translates the main agent state into an input for the subgraph and formats
    the subgraph's output back into a standard worker result.
    """
    def __init__(self, name: str = "open_deep_research"):
        self.name = name

    def _build_input_for_subgraph(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds a clean, focused input for the deep_researcher graph.
        """
        task_dict = state["plan"][0]["inputs"]
        
        core_query = task_dict.get("query", "")
        profile_image_url = task_dict.get("profile_picture_url", "")
        
        # Prepare a concise message for the internal deep_researcher graph's initial brief generation
        concise_initial_message_content = core_query
        if profile_image_url:
            concise_initial_message_content += f". Associated profile image: {profile_image_url}"

        # --- FIX: Construct a complete DeepResearchState dictionary here ---
        # Initialize all fields required by DeepResearchState, even if with None or empty lists.
        # This is the expected input format for deep_researcher.ainvoke
        initial_deep_research_state_input: Dict[str, Any] = {
            "messages": [HumanMessage(content=concise_initial_message_content)],
            "research_brief": None, # This will be populated by the 'write_research_brief' node
            "image_url": profile_image_url, # Pass the image URL along so deep_researcher can use it
            "supervisor_messages": [], # Will be initialized by the first node
            "supervisor_iterations": 0,
            "planner_messages": [],
            "notes": [],
            "raw_tool_outputs": [],
            "evidence_summary": None, # Will be populated later in the deep research graph
        }
        
        # The 'write_research_brief' node within deep_researcher will use 'messages[0].content'
        # to generate the structured 'research_brief' and 'supervisor_messages'.
        # The 'image_url' in this state is critical for its image search tools.

        return initial_deep_research_state_input
    async def _run_async(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """Asynchronous execution logic for the worker."""
        try:
            dr_input = self._build_input_for_subgraph(state)
            
            # --- START OF NEW LOGIC ---
            # This creates and injects the colorful printer
            final_config = config or {}
            existing_callbacks = final_config.get("callbacks")
            
            # This manager safely handles existing callbacks (like LangSmith's)
            # and adds our new one for beautiful console output.
            callback_manager = CallbackManager.configure(
                inheritable_callbacks=existing_callbacks,
                local_callbacks=[StdOutCallbackHandler()]
            )
            final_config["callbacks"] = callback_manager
            # --- END OF NEW LOGIC ---

            result_state = await deep_researcher.ainvoke(cast(Any, dr_input), final_config)
            
            final_intelligence = result_state.get("evidence_summary")
            if not final_intelligence:
                notes = result_state.get("notes", [])
                final_intelligence = notes[-1] if notes else "The deep research agent produced no actionable intelligence."

            # This print block provides the final summary for the customer
            print("\n\n" + "="*50)
            print("--- DEEP RESEARCH COMPLETE ---")
            print("="*50)
            print(final_intelligence)
            print("="*50 + "\n")

            return {
                "last_step_result": { "worker": self.name, "results": {self.name: final_intelligence}, "success": True },
                "last_step_message": AIMessage(content=f"{self.name} completed its investigation and produced the following intelligence summary:\n\n{final_intelligence}")
            }
        except Exception as e:
            return {
                "last_step_result": { "worker": self.name, "results": {}, "success": False, "error": str(e) },
                "last_step_message": AIMessage(content=f"{self.name} failed with error: {str(e)}")
            }

    def run(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self._run_async(state, config))




class SocialMediaInvestigator(BaseWorker):
    def __init__(self):
        tools = [
                insta_tools.get_instagram_user_info,
                insta_tools.get_instagram_user_followers,
                insta_tools.get_instagram_user_following,
                insta_tools.get_instagram_user_posts,
                insta_tools.download_image,
                ]
        
        persona = """Your specialization is **Social Network Analysis**. You are the social profiler, an expert in the culture and structure of online communities like Instagram, Facebook, and LinkedIn. You understand how people connect and share online. Your mission is to find the target's social media presence, analyze their network, and extract key details from their profiles and posts."""

        super().__init__(tools, "Social_Media_Investigator", persona)









class CrossPlatformValidator(BaseWorker):
    def __init__(self):
        tools = [
                Tool(
                name="compare_profile_pictures",
                func=vision_tools.compare_profile_pictures,
                description="Compare two profile pictures and assess similarity"
                ),
                Tool(
                name="cross_check_details",
                func=self.cross_check_details,
                description="Cross-check details between different platforms"
                )
                ]
        
        super().__init__(tools, "Cross_Platform_Validator", CROSS_PLATFORM_VALIDATOR_PERSONA)

    def cross_check_details(self, input: str) -> Dict[str, Any]:
        """Custom tool to compare details across platforms."""
        # This would be implemented to compare names, locations, etc.
        return {"similarity_score": 0.8, "matching_fields": ["name", "location"]}

class ReportSynthesizer:
    def __init__(self):
        '''
        self.llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name=f"{Constants.MODEL_FOR_WORKER}",
            temperature=0.1,
            # max_tokens=4096
        )
        '''
        self.llm = ChatOpenAI(
            model=Constants.SYNTHESIZER_MODEL,
            temperature=0.1,
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY or "")
        )
        self.logger = logging.getLogger(__name__)
    
    def run(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_template(REPORT_SYNTHESIZER_PROMPT)
        
        chain = prompt | self.llm
        try:
            report = chain.invoke({
                "original_query": state["original_query"],
                "aggregated_results": state["aggregated_results"]
            }, config).content
            
            self.logger.info("Report successfully generated")
            return {
                "final_report": report,
                "last_step_message": AIMessage(content="Final report generated")
            }
        except Exception as e:
            self.logger.error(f"Failed to generate report: {str(e)}")
            return {
                "final_report": "Error generating report",
                "last_step_message": AIMessage(content=f"Failed to generate report: {str(e)}")
            }
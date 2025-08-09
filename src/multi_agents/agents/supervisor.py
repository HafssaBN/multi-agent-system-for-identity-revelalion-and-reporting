from typing import TypedDict, List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ..graph.state import AgentState
from ..constants.constants import Constants
import logging
from langchain_groq import ChatGroq

class Supervisor:
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name="qwen/qwen3-32b",
            temperature=0.1,
            # max_tokens=4096
        )
        '''self.llm = ChatOpenAI(
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=Constants.OPENROUTER_API_KEY,
            model_name=Constants.DEFAULT_MODEL,
            temperature=0.1,
            max_tokens=4096
        )'''

        self.parser_llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name="moonshotai/kimi-k2-instruct",
            temperature=0.1,
            # max_tokens=4096
        )
        self.parser = JsonOutputParser()
        self.logger = logging.getLogger(__name__)
        
    def create_initial_plan(self, query: str) -> List[Dict[str, Any]]:
        """Generate initial investigation plan based on user query."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert digital investigator supervisor. Analyze the user query and create a step-by-step investigation plan.
             
             Available worker agents:
             - airbnb_analyzer: For analyzing Airbnb profiles/listings
             - web_search_investigator: For performing web searches
             - social_media_investigator: For searching social media platforms
             - cross_platform_validator: For correlating data across platforms
             
             Respond with a JSON array of steps, each with 'agent' and 'inputs' fields."""),
            ("human", "{query}")
        ])
        
        chain = prompt | self.parser_llm | self.parser
        try:
            plan = chain.invoke({"query": query})
            self.logger.info(f"Initial plan created: {plan}")
            return plan
        except Exception as e:
            self.logger.error(f"Failed to create initial plan: {str(e)}")
            return []
    
    # In the Supervisor class...

    def reassess_plan(self, state: AgentState) -> List[Dict[str, Any]]:
        """
        Re-evaluates, adapts, and updates the investigation plan based on new information.
        This is the strategic core of the supervisor, acting as a lead OSINT investigator.
        """
        
        # vvv THIS IS THE NEW, HIGHLY-ENGINEERED PROMPT vvv
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
            # ROLE & MISSION
            You are a Master OSINT (Open Source Intelligence) Strategist. Your mission is to direct a team of AI agents to create a comprehensive intelligence dossier on a target. You are relentless, creative, and methodical. You will use every piece of information to its fullest potential to uncover the target's complete digital footprint.

            # INVESTIGATIVE DOCTRINE (Your Guiding Principles)
            1.  **Tenacity & Multi-Angle Approach**: Never assume the first attempt is sufficient. For any given objective (e.g., finding a social media profile), you should generate multiple, varied tasks. If you find a name, 'John Doe', your plan should reflect multiple search angles:
                - A simple search: `web_search_investigator` with `query: "John Doe"`
                - A location-based search: `web_search_investigator` with `query: "John Doe" San Francisco`
                - A platform-specific search: `social_media_investigator` with `search_terms: ["John Doe"]`
                - An advanced search: `web_search_investigator` with `query: 'site:linkedin.com "John Doe" engineer'`
            2.  **Information is Fuel**: Every new piece of data in the `Aggregated Findings` (a name, username, location, email) is fuel for the next wave of investigation. Your primary goal is to use this fuel to create more tasks.
            3.  **Maximize Information Gain**: Always prioritize the plan that promises the greatest new information gain. Ask yourself: "Which sequence of actions will most effectively expand our knowledge base and get us closer to completing the mission?"

            # AVAILABLE AGENTS (YOUR TEAM)
            - `airbnb_analyzer`: Extracts structured data from Airbnb profiles.
            - `web_search_investigator`: Performs deep web searches. Use for broad searches and Google Dorking.
            - `social_media_investigator`: Searches specific social media platforms.
            - `cross_platform_validator`: Correlates data across different platforms.

            # CURRENT INVESTIGATION STATE
            - **Original Query**: {original_query}
            - **Completed Steps & Results**: {past_steps}
            - **Aggregated Findings**: {aggregated_results}
            - **Current Plan (To be replaced)**: {plan}

            # YOUR TASK: STRATEGIC REASSESSMENT & DYNAMIC RE-PLANNING
            Your task is to create a new, superior investigation plan from scratch based on the current state. You have **complete strategic freedom**. Do not feel bound by the old plan. Follow this decision framework:

            1.  **PRIORITY 1: Handle Failures.**
                - If the last step failed (`success: false`), your top priority is to create a new plan that works around the error. Analyze the `error` message and devise a new angle of attack. Do not repeat the failing step.

            2.  **PRIORITY 2: Re-architect the Plan for Maximum Impact.**
                - If the last step was successful, **discard the old plan and build a new one.**
                - Systematically review the **entire** `Aggregated Findings`.
                - Based on your `Investigative Doctrine`, generate a new sequence of steps that represents the most logical, tenacious, and promising path forward.
                - Your new plan should be an expansion of the investigation, using newly found data to create multiple, specific, and varied tasks.

            3.  **PRIORITY 3: Conclude the Investigation.**
                - After your analysis, if you determine that the `Aggregated Findings` are sufficient to comprehensively answer the `Original Query`, signal completion by returning an empty JSON array `[]`. This is a final judgment call.

            # OUTPUT FORMAT
            Your response MUST be a valid JSON array representing the new, updated list of plan steps. Do NOT include any explanations, comments, or markdown formatting. Just the raw JSON array.
            Example of a valid "complete" response: `[]`
            """),
        ])
        
        chain = prompt | self.parser_llm | self.parser
        
        try:
            # Pass the entire state dictionary, which contains all the keys mentioned in the prompt.
            new_plan = chain.invoke(state)
            self.logger.info(f"Supervisor has re-architected the plan. New plan: {new_plan}")
            
            if not isinstance(new_plan, list):
                self.logger.warning("Re-planning did not return a list. Defaulting to an empty plan to signal completion.")
                return []
                
            return new_plan
        except Exception as e:
            self.logger.error(f"Critical failure during plan reassessment: {str(e)}")
            return []
    
    def route_to_worker(self, state: AgentState) -> str:
        """Determine which worker should execute the next step."""
        if not state["plan"]:
            if state.get("final_report"):
                return "end"
            return "report_synthesizer"
        
        next_step = state["plan"][0]
        return next_step["agent"]
    
    def run(self, state: AgentState) -> Dict[str, Any]:
        """Execute the supervisor's logic for the current state."""
        
        # If it's the first run, create an initial plan.
        if not state.get("plan"):
            self.logger.info("No plan found. Creating initial plan.")
            plan = self.create_initial_plan(state["original_query"])
            return {
                "plan": plan,
                "past_steps": [],
                "aggregated_results": {},
                "messages": [
                    HumanMessage(content=state["original_query"]),
                    AIMessage(content=f"Initial investigation plan created with {len(plan)} steps.")
                ]
            }

        # If we are here, a worker has just run. Process its output.
        last_result = state.get("last_step_result")
        if last_result:
            self.logger.info(f"Processing result from worker: {last_result.get('worker')}")
            
            # Update history and aggregated results
            state["past_steps"].append(last_result)
            if last_result.get("results"):
                state["aggregated_results"].update(last_result.get("results", {}))

            # Add the worker's message to the message history
            if state.get("last_step_message"):
                state["messages"].append(state["last_step_message"])

            # CRITICAL: Remove the completed step from the plan *before* any reassessment.
            ''' if state["plan"]:
                state["plan"].pop(0)'''

            # Check if the last step failed. If so, reassess the plan.
            if last_result.get("success", False):
                self.logger.warning(f"Worker {last_result['worker']} failed. Reassessing the plan.")
                new_plan = self.reassess_plan(state)
                # You can decide to replace or prepend. Replacing is simpler.
                state["plan"] = new_plan
        
        # It's good practice to clear transient keys after processing them
        return {
            "plan": state["plan"],
            "past_steps": state["past_steps"],
            "aggregated_results": state["aggregated_results"],
            "messages": state["messages"],
            "last_step_result": None, # Clear the result
            "last_step_message": None # Clear the message
        }
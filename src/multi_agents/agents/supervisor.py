from typing import TypedDict, List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ..graph.state import AgentState
from ..constants.constants import Constants
import logging

class Supervisor:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=Constants.OPENROUTER_API_KEY,
            model_name=Constants.DEFAULT_MODEL,
            temperature=0.1,
            max_tokens=4096
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
        
        chain = prompt | self.llm | self.parser
        try:
            plan = chain.invoke({"query": query})
            self.logger.info(f"Initial plan created: {plan}")
            return plan
        except Exception as e:
            self.logger.error(f"Failed to create initial plan: {str(e)}")
            return []
    
    def reassess_plan(self, state: AgentState) -> List[Dict[str, Any]]:
        """Re-evaluate and update the investigation plan based on new information."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Reassess the investigation plan based on new information. Consider:
             - Completed steps: {past_steps}
             - Current findings: {aggregated_results}
             - Original query: {original_query}
             
             Return an updated JSON plan array."""),
            ("human", "Please update the investigation plan.")
        ])
        
        chain = prompt | self.llm | self.parser
        try:
            new_plan = chain.invoke({
                "past_steps": state["past_steps"],
                "aggregated_results": state["aggregated_results"],
                "original_query": state["original_query"]
            })
            self.logger.info(f"Updated plan: {new_plan}")
            return new_plan
        except Exception as e:
            self.logger.error(f"Failed to reassess plan: {str(e)}")
            return state["plan"]
    
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
        if not state.get("plan"):
            # Initial state, create plan
            state["plan"] = self.create_initial_plan(state["original_query"])
            state["aggregated_results"] = {}
            state["past_steps"] = []
            state["messages"] = [
                HumanMessage(content=state["original_query"]),
                AIMessage(content=f"Initial investigation plan created with {len(state['plan'])} steps.")
            ]
        else:
            # Update state with results from last worker
            if state.get("last_step_result"):
                state["past_steps"].append(state["last_step_result"])
                state["aggregated_results"].update(state["last_step_result"].get("results", {}))
                
                # Reassess plan based on new information
                state["plan"] = self.reassess_plan(state)
                
                # Remove the completed step
                if state["plan"]:
                    state["plan"].pop(0)
            
            # Add to message history
            if state.get("last_step_message"):
                state["messages"].append(state["last_step_message"])
        
        return state


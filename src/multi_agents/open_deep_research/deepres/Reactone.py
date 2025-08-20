# src/multi_agents/open_deep_research/deep_researcher.py

import asyncio
import os
import operator
import logging
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, cast
import re
from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr
from typing_extensions import TypedDict

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, BaseTool
from langgraph.graph import END, StateGraph, add_messages

from ..constants.constants import Constants
from ..tools import search_tools
from .configuration import Configuration
from multi_agents.Prompts.open_deep_research_prompts import (
    lead_researcher_prompt,
    transform_messages_into_research_topic_prompt,
)

logger = logging.getLogger(__name__)

# --- State Definition ---
class DeepResearchState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    research_brief: Optional[str]
    evidence_summary: Optional[str]

class ResearchQuestion(BaseModel):
    research_brief: str = Field(description="A detailed research brief to guide the investigation.")

# --- Utility Functions ---
load_dotenv()
def get_today_str() -> str: return f"{datetime.now():%a %b %d, %Y}"

def get_api_key_for_model(model_name: str, config: Optional[RunnableConfig] = None) -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key: raise ValueError("OPENROUTER_API_KEY is not set.")
    return key

# --- Tool Definitions ---
@tool
def research_complete(final_answer: str) -> str:
    """Call this tool when all research is complete to provide the final answer."""
    return f"Research is complete! Final Answer: {final_answer}"

ALL_TOOLS: List[BaseTool] = [
    research_complete, search_tools.web_scraper, search_tools.google_search,
    search_tools.bing_search, search_tools.duckduckgo_search, search_tools.yahoo_search,
    search_tools.yandex_search, search_tools.baidu_search, search_tools.google_image_search,
    search_tools.bing_images_search, search_tools.google_lens_search,
    search_tools.google_reverse_image_search, search_tools.google_maps_search,
    search_tools.google_hotels_search, search_tools.google_news_search,
    search_tools.youtube_search, search_tools.yelp_search,
]

# --- Graph Nodes ---

async def write_research_brief(state: DeepResearchState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Creates the initial research brief which serves as the input for the ReAct agent."""
    logger.info("Writing research brief...")
    all_messages_text = get_buffer_string(state["messages"])
    
    configurable = Configuration.from_runnable_config(config)
    model = ChatOpenAI(model=configurable.planner_model, api_key=SecretStr(get_api_key_for_model(configurable.planner_model, config)), base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"), temperature=0.1).with_structured_output(ResearchQuestion)
    prompt_text = transform_messages_into_research_topic_prompt.format(messages=all_messages_text, date=get_today_str())
    
    response_object = await model.ainvoke([HumanMessage(content=prompt_text)])
    research_brief_text = cast(ResearchQuestion, response_object).research_brief
    logger.info(f"Research brief created: {research_brief_text}")
    
    return {"research_brief": research_brief_text}

async  def research_agent_node(state: DeepResearchState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """This single node is a robust ReAct agent that executes the entire research process."""
    configurable = Configuration.from_runnable_config(config)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", lead_researcher_prompt),
        ("user", "{input}"),
        ("ai", "{agent_scratchpad}"),
    ])
    prompt = prompt.partial(
        date=get_today_str(),
        tools="\n".join([f"{tool.name}: {tool.description}" for tool in ALL_TOOLS]),
        tool_names=", ".join([tool.name for tool in ALL_TOOLS]),
    )
    
    llm = ChatOpenAI(model=configurable.planner_model, api_key=SecretStr(get_api_key_for_model(configurable.planner_model, config)), base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"), temperature=0.1)
    agent = create_react_agent(llm, ALL_TOOLS, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=ALL_TOOLS, handle_parsing_errors=True, verbose=True)

    research_brief = state.get("research_brief") or ""
    
    # --- START OF ROBUST EXECUTION BLOCK ---
    try:
        # The AgentExecutor will run its own internal ReAct loop here until it's done or fails.
        response = await agent_executor.ainvoke({"input": research_brief}, config=config)
        output = response.get("output", "The research agent finished but produced no final output.")
    except Exception as e:
        # If the AgentExecutor loop crashes for any reason, we catch it here.
        logger.error(f"AgentExecutor in research_agent_node failed: {e}", exc_info=True)
        # We then package the error into a clean final answer.
        output = (
            f"Agent execution failed with a critical error: {str(e)}. "
            "This often occurs with malformed tool inputs or if the agent gets stuck. "
            "The investigation from this worker will conclude with the available information."
        )
    # --- END OF ROBUST EXECUTION BLOCK ---
    
    # This node will now ALWAYS return a final summary, even if it's an error summary.
    return {"evidence_summary": output}


# --- Graph Definition ---
def create_deep_researcher():
    graph_builder = StateGraph(DeepResearchState)
    
    graph_builder.add_node("write_research_brief", write_research_brief)
    graph_builder.add_node("research_agent_node", research_agent_node)

    graph_builder.set_entry_point("write_research_brief")
    graph_builder.add_edge("write_research_brief", "research_agent_node")
    graph_builder.add_edge("research_agent_node", END)

    return graph_builder.compile()

deep_researcher = create_deep_researcher()
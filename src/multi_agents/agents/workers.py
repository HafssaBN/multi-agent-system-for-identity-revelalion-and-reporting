from typing import Dict, Any, Optional
from langchain.agents import AgentExecutor, Tool
from langchain.agents import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from ..tools import airbnb_tools, insta_tools, search_tools, vision_tools
from ..constants.constants import Constants
import logging
from langchain_core.messages import HumanMessage, AIMessage


class BaseWorker:
    def __init__(self, tools: list, name: str):
        self.llm = ChatOpenAI(
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=Constants.OPENROUTER_API_KEY,
            model_name=Constants.DEFAULT_MODEL,
            temperature=0.1
        )
        self.tools = tools
        self.name = name
        self.logger = logging.getLogger(__name__)
        # ... inside BaseWorker __init__ ...
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a highly skilled {name}, an expert in digital investigations.
            Your goal is to use the available tools to gather information and complete the assigned task.

            You must follow the ReAct (Reason-Act-Observe) framework. This means you will reason about the task, decide on an action (using a tool), and then observe the result before deciding the next step.

            TOOLS:
            ------
            Here are the tools you have access to:
            {tools}

            RESPONSE FORMAT:
            ----------------
            To use a tool, you **MUST** use the following format. Do not deviate from this structure.

            ```
            Thought: The user wants me to do [some task]. I need to use a specific tool to get the information. I will use the [tool_name] tool with the following input.
            Action: [the name of the tool to use, from this list: {tool_names}]
            Action Input: [the input to the tool]
            ```

            After you receive the observation from the tool, you will think again and decide if you need another tool or if you have enough information.

            If you have sufficient information to answer the user's request, you MUST output your final answer in the following format:

            ```
            Thought: I have gathered all the necessary information. I can now provide the final answer.
            Final Answer: [Your comprehensive answer based on the tool outputs]
            ```

            Begin!

            Current Task: {task}
            """),
                ("human", "{input}"),
                ("ai", "{agent_scratchpad}")
        ])


        
        

        prompt = prompt.partial(
            tools="\n".join([f"{tool.name}: {tool.description}" for tool in tools]),
            tool_names=", ".join([tool.name for tool in tools]),
            name=self.name
        )
                
        self.agent = create_react_agent(self.llm, tools, prompt)
        self.agent_executor = AgentExecutor(agent=self.agent, tools=tools, verbose=True)
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            task = state["plan"][0]["inputs"]
            result = self.agent_executor.invoke({
                "input": task,
                "task": f"Execute {self.name} task",
                "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in self.tools])
            })
            
            return {
                "last_step_result": {
                    "worker": self.name,
                    "results": result.get("output", {}),
                    "success": True
                },
                "last_step_message": AIMessage(content=f"{self.name} completed task with results: {str(result)}")
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
                "last_step_message": AIMessage(content=f"{self.name} failed: {str(e)}")
            }

class AirbnbAnalyzer(BaseWorker):
    def __init__(self):
        tools = [
            airbnb_tools.get_airbnb_profile_details,
            airbnb_tools.get_airbnb_profile_places_visited,
            airbnb_tools.get_airbnb_profile_listings,
            airbnb_tools.get_airbnb_profile_reviews,
            airbnb_tools.get_listing_details
        ]
        
        super().__init__(tools, "Airbnb_Analyzer")

class WebSearchInvestigator(BaseWorker):
    def __init__(self):
        tools = [
            Tool(
                name="tavily_search",
                func=search_tools.tavily_search,
                description="General web search using Tavily"
            ),
            
            Tool(
                name="web_scraper",
                func=search_tools.web_scraper,
                description="Scrape content from a specific URL"
            )
        ]

        '''Tool(
                name="google_search",
                func=search_tools.google_search,
                description="Advanced Google search with dork queries"
            ),'''
        super().__init__(tools, "Web_Search_Investigator")

class SocialMediaInvestigator(BaseWorker):
    def __init__(self):
        tools = [
            insta_tools.get_instagram_user_info,
            insta_tools.get_instagram_user_followers,
            insta_tools.get_instagram_user_following,
            insta_tools.get_instagram_user_posts,
            insta_tools.download_image,
        ]
        
        super().__init__(tools, "Social_Media_Investigator")

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
        super().__init__(tools, "Cross_Platform_Validator")
    
    def cross_check_details(self, input: str) -> Dict[str, Any]:
        """Custom tool to compare details across platforms."""
        # This would be implemented to compare names, locations, etc.
        return {"similarity_score": 0.8, "matching_fields": ["name", "location"]}

class ReportSynthesizer:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=Constants.OPENROUTER_API_KEY,
            model_name=Constants.DEFAULT_MODEL,
            temperature=0.1
        )
        self.logger = logging.getLogger(__name__)
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Synthesize a comprehensive investigation report from the following data:
             
             Original Query: {original_query}
             
             Investigation Findings:
             {aggregated_results}
             
             Create a well-structured Markdown report with sections for each platform and cross-references."""),
            ("human", "Please generate the final report.")
        ])
        
        chain = prompt | self.llm
        try:
            report = chain.invoke({
                "original_query": state["original_query"],
                "aggregated_results": state["aggregated_results"]
            }).content
            
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
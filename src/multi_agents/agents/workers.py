from typing import Dict, Any, Optional
from langchain.agents import AgentExecutor, Tool
from langchain.agents import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from ..tools import  insta_tools, search_tools, vision_tools, fack_airbnb_tools
from ..constants.constants import Constants
import logging
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq


import json # Import json for clean serialization
from typing import Dict, Any, Optional


class BaseWorker:
    # vvv MODIFIED __init__ SIGNATURE vvv
    def __init__(self, tools: list, name: str, system_prompt_extension: str):
        self.llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name=Constants.MODEL_FOR_WORKER,
            temperature=0.1,
        )
        self.tools = tools
        self.name = name
        self.logger = logging.getLogger(__name__)

        # vvv NEW, MORE CONTEXT-AWARE PROMPT vvv
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
# YOUR IDENTITY & MISSION
You are a world-class digital investigator named {name}. You are a key member of a larger OSINT (Open Source Intelligence) team.

{persona}

# TEAM'S OVERALL OBJECTIVE
The team's primary mission is to answer this query: "{original_query}"
So far, the team has gathered the following intelligence:
<Aggregated_Results>
{aggregated_results}
</Aggregated_Results>

# YOUR CURRENT TASK
Your specific assignment is to execute the following task: "{task}"
You must use your specialized tools to complete this task and contribute to the team's overall objective.

# FRAMEWORK & OUTPUT
You must operate using the ReAct (Reason-Act-Observe) framework.

**TOOLS:**
------
{tools}

**OUTPUT FORMAT:**
------
To use a tool, you **MUST** use this exact format:
```
Thought: [Your reasoning about the next action based on the task and available data.]
Action: [the name of the tool to use from this list: {tool_names}]
Action Input: [the input to the tool, which can be a string or a JSON object]
```

After observing the tool's output, you will continue this cycle until you have enough information.

When you have fulfilled your task, you **MUST** provide your final answer in this format:
```
Thought: I have successfully completed my assignment and have gathered all necessary information. I should also mention any new, unexpected leads I discovered.
Final Answer: [Your comprehensive answer. **CRITICALLY, you must also include any new potential leads** like usernames, emails, or locations that could be useful for the team's next steps, even if they weren't part of your direct task.]
```
"""),
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
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
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
            })
            
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
        
        persona = """Your specialization is **Structured Data Extraction**. You are like a digital archivist, meticulously pulling specific, verifiable data points (names, locations, join dates, etc.) from platform profiles like Airbnb. Your work forms the factual bedrock upon which the rest of the team builds its investigation."""
        
        super().__init__(tools, "Airbnb_Analyzer", persona)

class WebSearchInvestigator(BaseWorker):
    def __init__(self):
        tools = [
            Tool(name="tavily_search", func=search_tools.tavily_search, description="General web search using Tavily"),
            Tool(name="web_scraper", func=search_tools.web_scraper, description="Scrape content from a specific URL")
        ]
        
        persona = """Your specialization is **Deep Web Traversal and Unstructured Data Discovery**. You are the net-crawler, navigating the vast ocean of the internet. You excel at using advanced search operators (Google Dorking) and scraping web pages to find mentions, articles, forum posts, and hidden connections that others miss. You turn the chaotic web into actionable intelligence."""

        super().__init__(tools, "Web_Search_Investigator", persona)

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
        
        persona = """Your specialization is **Information Correlation and Verification**. You are the "Correlator," the critical thinker who connects the dots. Your job is to take pieces of intelligence gathered by other agents and verify them against each other. By comparing details like names, locations, and even profile pictures across different platforms, you confirm identities and weed out false positives, ensuring the team's final report is accurate."""

        super().__init__(tools, "Cross_Platform_Validator", persona)

    def cross_check_details(self, input: str) -> Dict[str, Any]:
        """Custom tool to compare details across platforms."""
        # This would be implemented to compare names, locations, etc.
        return {"similarity_score": 0.8, "matching_fields": ["name", "location"]}

class ReportSynthesizer:
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name=f"{Constants.MODEL_FOR_WORKER}",
            temperature=0.1,
            # max_tokens=4096
        )
        """self.llm = ChatOpenAI(
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=Constants.OPENROUTER_API_KEY,
            model_name=Constants.DEFAULT_MODEL,
            temperature=0.1
        )"""
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
from langgraph.graph import StateGraph, END
from .state import AgentState
from ..agents.supervisor import Supervisor
from ..agents.workers import (
    AirbnbAnalyzer,
    WebSearchInvestigator,
    SocialMediaInvestigator,
    CrossPlatformValidator,
    ReportSynthesizer
)

class GraphBuilder:
    def __init__(self):
        self.supervisor = Supervisor()
        self.airbnb_analyzer = AirbnbAnalyzer()
        self.web_search_investigator = WebSearchInvestigator()
        self.social_media_investigator = SocialMediaInvestigator()
        self.cross_platform_validator = CrossPlatformValidator()
        self.report_synthesizer = ReportSynthesizer()
        
    def build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("supervisor", self.supervisor.run)
        workflow.add_node("airbnb_analyzer", self.airbnb_analyzer.run)
        workflow.add_node("web_search_investigator", self.web_search_investigator.run)
        workflow.add_node("social_media_investigator", self.social_media_investigator.run)
        workflow.add_node("cross_platform_validator", self.cross_platform_validator.run)
        workflow.add_node("report_synthesizer", self.report_synthesizer.run)
        
        # Define edges
        workflow.add_edge("airbnb_analyzer", "supervisor")
        workflow.add_edge("web_search_investigator", "supervisor")
        workflow.add_edge("social_media_investigator", "supervisor")
        workflow.add_edge("cross_platform_validator", "supervisor")
        workflow.add_edge("report_synthesizer", END)
        
        # Conditional edges from supervisor
        workflow.add_conditional_edges(
            "supervisor",
            self.supervisor.route_to_worker,
            {
                "airbnb_analyzer": "airbnb_analyzer",
                "web_search_investigator": "web_search_investigator",
                "social_media_investigator": "social_media_investigator",
                "cross_platform_validator": "cross_platform_validator",
                "report_synthesizer": "report_synthesizer",
                "end": END
            }
        )
        
        # Set entry point
        workflow.set_entry_point("supervisor")
        
        return workflow.compile()
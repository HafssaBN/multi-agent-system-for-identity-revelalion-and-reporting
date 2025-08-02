from multi_agents.graph.builder import GraphBuilder
from multi_agents.graph.state import AgentState
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def run_investigation(query: str) -> str:
    """Run the complete digital investigation pipeline."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize the graph
        graph_builder = GraphBuilder()
        app = graph_builder.build_graph()
        
        # Set initial state
        initial_state = AgentState(
            original_query=query,
            plan=[],
            past_steps=[],
            aggregated_results={},
            final_report="",
            messages=[]
        )
        
        # Run the investigation
        logger.info("Starting digital investigation...")
        final_state = app.invoke(initial_state)
        
        logger.info("Investigation completed successfully")
        return final_state.get("final_report", "No report generated")
    except Exception as e:
        logger.error(f"Investigation failed: {str(e)}")
        return f"Investigation failed: {str(e)}"

if __name__ == "__main__":
    # Example usage
    query = "Find the online identity of the host at https://www.airbnb.com/users/show/532236013"
    report = run_investigation(query)
    print("\nFinal Report:")
    print(report)
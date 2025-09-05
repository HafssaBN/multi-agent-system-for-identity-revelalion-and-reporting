from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Tuple

from .graph.builder import GraphBuilder


def build_app() -> Tuple[Any, Any]:
    """
    Build the multi-agent graph and return (app, supervisor_instance).

    The supervisor instance is returned so notebooks can call its
    ingest_user_selection(...) helper between runs when HITL pauses occur.
    """
    builder = GraphBuilder()
    app = builder.build_graph()
    return app, builder.supervisor


async def run_until_pause_or_done(
    app: Any,
    state: Dict[str, Any],
    *,
    max_iters: int = 10,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Drive the graph for up to max_iters invocations or until it either:
      - pauses for human input (awaiting_user_confirmation == True), or
      - produces a final_report (truthy), or
      - has no remaining plan (safety stop)

    Returns the latest state.
    """
    current = state
    for _ in range(max_iters):
        current = await app.ainvoke(current, config)

        # Stop when pausing for a human decision
        if current.get("awaiting_user_confirmation"):
            return current

        # Stop when a final report is produced
        if current.get("final_report"):
            return current

        # If there's no plan left, stop to avoid infinite looping
        if not current.get("plan"):
            return current

    return current


def resume_after_human(
    supervisor: Any,
    state: Dict[str, Any],
    *,
    selection_index: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Apply human input to the state and clear the pause flag.

    - If candidate options are present and a selection_index is provided,
      use supervisor.ingest_user_selection to store the chosen candidate and
      clear the pause flag.
    - If no candidates are present (judge-only pause), simply clear the pause
      flag to continue.

    Returns the mutated state.
    """
    candidates = state.get("candidate_options") or []

    if candidates and selection_index is not None:
        # Use the built-in helper which also appends a message
        state = supervisor.ingest_user_selection(state, int(selection_index))
        state["awaiting_user_confirmation"] = False
        return state

    # Judge-only pause (no candidates). Clearing the flag lets the graph continue.
    state["awaiting_user_confirmation"] = False
    return state


def run_interactive(
    query: str,
    *,
    selection_provider: Optional[callable] = None,
    max_global_steps: int = 30,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenient synchronous runner for notebooks:
      - Builds the app
      - Runs until a pause or completion
      - If paused, renders candidates (if any) and asks selection_provider for an index
      - Resumes and repeats until final report or max_global_steps

    selection_provider is a callable that takes (state) and returns either
    an int index (for candidate selection) or None (to just continue on judge-only pauses).
    """
    from .graph.state import AgentState  # late import to avoid circulars

    app, supervisor = build_app()

    # Initialize a complete AgentState to avoid missing-key surprises
    initial_state: AgentState = {
        "original_query": query,
        "plan": [],
        "past_steps": [],
        "aggregated_results": {},
        "final_report": "",
        "messages": [],
        "last_step_result": None,
        "last_step_message": None,
        "awaiting_user_confirmation": False,
        "candidate_options": [],
        "selected_candidate": None,
    }

    async def _drive() -> Dict[str, Any]:
        state: Dict[str, Any] = initial_state
        for _ in range(max_global_steps):
            state = await run_until_pause_or_done(app, state, max_iters=5, config=config)

            # Completed
            if state.get("final_report"):
                return state

            # No plan → stop gracefully
            if not state.get("plan") and not state.get("awaiting_user_confirmation"):
                return state

            # Pause for human
            if state.get("awaiting_user_confirmation"):
                cands = state.get("candidate_options") or []

                # Obtain a selection from the provider if available
                choice = None
                if selection_provider is not None:
                    try:
                        choice = selection_provider(state)
                    except Exception:
                        choice = None

                # Apply the human input (or just continue on judge-only pauses)
                state = resume_after_human(
                    supervisor,
                    state,
                    selection_index=choice if isinstance(choice, int) else None,
                )

                # Loop continues to drive more steps

        return state

    # Notebook/event-loop safe: avoid asyncio.run inside running loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_drive())

    try:
        import nest_asyncio  # type: ignore
        nest_asyncio.apply()
    except Exception:
        pass
    return loop.run_until_complete(_drive())



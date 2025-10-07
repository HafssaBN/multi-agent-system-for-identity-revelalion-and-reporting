# src/multi_agents/graph/builder.py
from __future__ import annotations

from typing import Any, Dict, Tuple, Callable, cast

from langgraph.graph import StateGraph, END
from langgraph.pregel import Pregel

from .state import AgentState
from ..agents.supervisor import Supervisor
from ..agents.workers import SearchWorker, ImageSearchWorker, ReportSynthesizer


class GraphBuilder:
    def __init__(self) -> None:
        self.supervisor = Supervisor()
        self.search_worker = SearchWorker()
        self.image_search_worker = ImageSearchWorker()
        self.report_synthesizer = ReportSynthesizer()

    # Generic wrapper: accepts whatever LangGraph passes (state[, config])
    # and calls .run (preferred) or ._invoke on the underlying object.
    def _wrap(self, obj: Any, methods: Tuple[str, ...] = ("run", "_invoke")) -> Callable[..., Dict[str, Any]]:
        def node(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            # LangGraph usually calls node(state) or node(state, config=...)
            state = args[0] if args else kwargs.get("state", {})
            config = None
            if len(args) >= 2:
                config = args[1]
            elif "config" in kwargs:
                config = kwargs["config"]

            for name in methods:
                if hasattr(obj, name):
                    fn = getattr(obj, name)
                    try:
                        # Try (state, config) first
                        return fn(state, config)
                    except TypeError:
                        # Fallback to (state) only
                        return fn(state)
            raise AttributeError(f"{obj!r} exposes none of {methods}")
        return node

    def build_graph(self) -> Pregel:
        workflow = StateGraph(AgentState)

        # Nodes — cast to Any to satisfy strict Pylance stub expectations
        workflow.add_node("supervisor", cast(Any, self._wrap(self.supervisor, ("run",))))
        workflow.add_node("search_worker", cast(Any, self._wrap(self.search_worker)))
        workflow.add_node("image_search_worker", cast(Any, self._wrap(self.image_search_worker)))
        workflow.add_node("report_synthesizer", cast(Any, self._wrap(self.report_synthesizer, ("run", "_invoke"))))

        # Edges
        workflow.add_edge("search_worker", "supervisor")
        workflow.add_edge("image_search_worker", "supervisor")
        workflow.add_edge("report_synthesizer", END)

        # Routing
        workflow.add_conditional_edges(
            "supervisor",
            self.supervisor.route_to_worker,
            {
                "search_worker": "search_worker",
                "image_search_worker": "image_search_worker",
                "report_synthesizer": "report_synthesizer",
                "end": END,
            },
        )

        workflow.set_entry_point("supervisor")
        return workflow.compile()

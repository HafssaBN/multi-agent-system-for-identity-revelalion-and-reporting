from multi_agents.run_interactive import run_interactive

def selection_provider(state):
    # Candidate-based pauses (HITL from workers)
    candidates = state.get("candidate_options") or []
    if candidates:
        print("\nCandidates found:")
        for i, c in enumerate(candidates):
            print(f"[{i}] {c.get('name')} — {c.get('platform','?')} — {c.get('url','')}")
        while True:
            try:
                raw = input("Pick a candidate index (or blank to skip): ").strip()
                return int(raw) if raw != "" else None
            except Exception:
                print("Invalid input, try again.")
    # Judge-only pauses
    msgs = [m.content for m in state.get("messages", []) if getattr(m, "content", None)]
    q = None
    for m in reversed(msgs):
        if m.startswith("Human input required:"):
            q = m
            break
    if q:
        print("\n" + q)
        input("Press Enter to continue...")
    return None

query = "Find the online identity of the host at https://www.airbnb.com/users/show/532236013"
cfg = {"configurable": {
  "max_total_serp_calls": 6,
  "max_researcher_iterations": 6,
  "max_tool_calls_per_turn": 2,
  "search_timeout_seconds": 10
}}
final_state = run_interactive(query, selection_provider=selection_provider, max_global_steps=30, config=cfg)
print("\nFinal report:\n", final_state.get("final_report", "No report generated"))
import asyncio
import os
import logging
from typing import List, Dict

from langchain_core.messages import HumanMessage, ToolMessage
from multi_agents.open_deep_research.database import setup_database
from multi_agents.open_deep_research.deep_researcher import (
    deep_researcher,
    DeepResearchState,
    continue_research,
)

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_deep_researcher")


# ----------------------------
# Evidence utilities
# ----------------------------
def process_and_display_evidence(notes: List[str]) -> None:
    from urllib.parse import urlparse
    import re

    print("\n\n--- EVIDENCE LOCKER (Sources Found) ---")
    if not notes:
        print("No research notes were produced to extract evidence from.")
        return

    url_pattern = r'https?://[^\s,"\'<>]+'
    full_text = "\n".join(notes)
    urls_found = re.findall(url_pattern, full_text)
    if not urls_found:
        print("No URLs were found in the agent's research notes.")
        return

    # 1) De-dupe
    unique_urls = sorted(set(urls_found))

    # 2) Keep a *small* junk list (heavy redirects/tracking),
    #    but DO NOT nuke common CDNs or image hosts anymore.
    junk_substrings = [
        "google.com/url?", "google.com/search?",
        "schemas.microsoft.com", "w3.org",
        "cdn-cgi"  # cloudflare boilerplate
    ]

    # 3) Whitelist hosts that often appear in image/Lens results
    ALLOW_HOSTS = {
        # Wikimedia / Wikipedia
        "upload.wikimedia.org", "commons.wikimedia.org", "wikipedia.org",
        # Flickr
        "flickr.com", "live.staticflickr.com",
        # Adobe Stock / FTCDN
        "stock.adobe.com", "t3.ftcdn.net", "ftcdn.net",
        # Shutterstock / iStock / Getty / Alamy / Depositphotos
        "shutterstock.com", "image.shutterstock.com",
        "istockphoto.com", "media.istockphoto.com",
        "gettyimages.com", "media.gettyimages.com",
        "alamy.com", "l450v.alamy.com",
        "depositphotos.com", "st.depositphotos.com",
        # Squarespace / common image CDNs
        "images.squarespace-cdn.com", "squarespace-cdn.com",
        "cdn.getyourguide.com", "i.pinimg.com",
        # Instagram lookaside + Threads images
        "lookaside.instagram.com", "lookaside.fbsbx.com",
        "threads.com", "www.threads.com",
        # Generic image/file CDNs
        "i.imgur.com", "imgur.com", "staticflickr.com"
    }

    def is_junk(u: str) -> bool:
        low = u.lower()
        if any(s in low for s in junk_substrings):
            host = urlparse(u).netloc.lower()
            if host in ALLOW_HOSTS:
                return False
            return True
        return False

    cleaned = [u for u in unique_urls if not is_junk(u)]

    # 4) Simple categorization
    categories: Dict[str, List[str]] = {
        "Social Media & Profiles": [],
        "News & Articles": [],
        "Corporate & Business": [],
        "Image & Visual Content": [],
        "Other Relevant Links": [],
    }
    social_domains = [
        "linkedin.com", "facebook.com", "instagram.com", "threads.net", "threads.com",
        "twitter.com", "x.com", "youtube.com", "tiktok.com"
    ]
    image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff")

    def host(u: str) -> str:
        try:
            return urlparse(u).netloc.lower()
        except Exception:
            return ""

    for url in cleaned:
        u = url.lower()
        h = host(url)
        if any(d in h for d in social_domains):
            categories["Social Media & Profiles"].append(url)
        elif u.endswith(image_exts) or h in ALLOW_HOSTS:
            categories["Image & Visual Content"].append(url)
        elif "news" in u or "article" in u or "/posts/" in u or "/blog/" in u:
            categories["News & Articles"].append(url)
        elif "company" in u or "business" in u or "/about" in u:
            categories["Corporate & Business"].append(url)
        else:
            categories["Other Relevant Links"].append(url)

    # 5) Print with counts (cap each section to keep it tidy)
    found_any = False
    MAX_SHOW = 25
    for cat, urls in categories.items():
        if urls:
            found_any = True
            print(f"\n[{cat}] ({len(urls)})")
            for u in urls[:MAX_SHOW]:
                print(f"  - {u}")
            if len(urls) > MAX_SHOW:
                print(f"  ... (+{len(urls) - MAX_SHOW} more)")

    if not found_any:
        print("No meaningful URLs were found after filtering.")


def summarize_image_search_for_manager(notes: List[str]) -> None:
    print("\n--- IMAGE SEARCH SUMMARY (Manager-Friendly) ---")
    if not notes:
        print("No image-search notes were produced.")
        return
    block = None
    for n in notes:
        if "Image search produced candidates" in n:
            block = n
            break
    if not block:
        print("We ran a reverse-image pass, but it did not return useful profile matches. We continued with name-based search.")
        return

    if any(sig in block for sig in ["Trafalgar Square", "Visit London", "Wikipedia"]):
        print("The reverse-image search returned landmarks instead of profile matches. We continued with name/business search.")
    else:
        print("Reverse-image search returned some visual matches, but we relied more on name/business search for precision.")


# ----------------------------
# XAI / SMoA utilities
# ----------------------------
def show_candidates_for_context(state: DeepResearchState) -> None:
    cands = state.get("candidates") or []
    if not cands:
        return
    print("\n--- CANDIDATES PRESENTED TO JUDGE/HITL ---")
    for i, c in enumerate(cands):
        print(f"[{i}] {c.get('name')} — {c.get('url')}\n    why: {c.get('why')}")


def show_judge_xai(state: DeepResearchState) -> None:
    """Extract and print the judge diagnostics (SMoA + router + bias) from planner_messages & notes."""
    print("\n--- JUDGE / XAI OUTPUT ---")
    planner_msgs = state.get("planner_messages", []) or []
    found_llm_judge = False
    for m in planner_msgs:
        if isinstance(m, ToolMessage) and getattr(m, "name", "") == "llm_judge":
            found_llm_judge = True
            print("\n[llm_judge ToolMessage]")
            print(m.content)

    if not found_llm_judge:
        print("No llm_judge ToolMessage found in planner_messages (routing/diagnostics might be disabled or judge errored).")

    notes = state.get("notes", []) or []
    judge_notes = [n for n in notes if n.startswith("[judge]") or "LLM Judge decision" in n]
    if judge_notes:
        print("\n--- JUDGE NOTES (from `notes`) ---")
        for jn in judge_notes:
            print("\n" + jn)
    else:
        print("\nNo judge-related lines found in notes.")

# *** NEW HELPER FUNCTION FOR ASYNC INPUT ***
def get_user_input(prompt: str) -> str:
    """Wrapper for the blocking input() function."""
    return input(prompt)

# ----------------------------
# Main
# ----------------------------
async def main() -> None:
    print("--- [1] Starting Enhanced Test for OpenDeepResearch ---")
    setup_database()

    required_env = ["OPENROUTER_API_KEY", "SERPAPI_API_KEY"]
    missing = [v for v in required_env if not os.getenv(v)]
    if missing:
        print(f"❌ ERROR: Missing required environment variables: {', '.join(missing)}")
        return
    print("✅ All required environment variables are set.")

    image_url = (
        "https://a0.muscache.com/im/pictures/user/User/original/213a678f-2d3c-4b11-886e-df873b318aa4.jpeg?im_w=720"
    )
    test_query = (
        "Find the online identity and recent activities of 'Abdel', an entrepreneur in Marrakech. "
        "Start by using reverse image search on this profile picture: "
        f"{image_url} "
        "Then, search for his name and associated businesses or projects."
    )

    print(f"\n--- [2] Using Test Query ---\n{test_query}\n")

    initial_state: DeepResearchState = {
        "messages": [HumanMessage(content=test_query)],
        "research_brief": None,
        "image_url": image_url,
        "planner_messages": [],
        "supervisor_iterations": 0,
        "notes": [],
        "serp_calls_used": 0,
        "candidates": [],
        "awaiting_disambiguation": False,
        "selected_candidate": None,
        "rejected_urls": [],
        "image_probe_done": False,
    }

    config = {"configurable": {}}

    print("--- [3] Streaming the deep_researcher agent... ---\n")
    try:
        # === REVISED LOGIC: Use astream to handle intermediate pauses ===
        state = initial_state
        
        # --- First Run ---
        async for update in deep_researcher.astream(state, config):
            # The output of astream is a dictionary where keys are node names
            # and values are the updates to the state. We take the last one.
            latest_state = list(update.values())[0]
            
            # Check if the agent has paused for human input
            if latest_state.get("awaiting_disambiguation"):
                print("--- [3a] Agent paused for human input ---")
                state = latest_state  # Capture the paused state
                break  # Exit the stream to wait for the user
            else:
                state = latest_state # Continue updating state until pause or end

        # --- Human-in-the-Loop (HITL) Interaction ---
        if state.get("awaiting_disambiguation") and state.get("candidates"):
            print("\n" + "="*40)
            print("⚠️  AGENT PAUSED: Awaiting human disambiguation.")
            print("Please select the best candidate to continue the investigation.")
            print("="*40 + "\n")

            candidates = state.get("candidates", [])
            for i, c in enumerate(candidates):
                print(f"  [{i}] {c.get('name')} — {c.get('url')}\n      why: {c.get('why')}\n")
            
            try:
                prompt_text = "Your choice (enter a number, or -1 for none): "
                raw_choice = await asyncio.to_thread(get_user_input, prompt_text)
                choice_index = int(raw_choice.strip()) if raw_choice.strip() else -1
            except (ValueError, IndexError):
                print("Invalid choice. Defaulting to 'none'.")
                choice_index = -1
            
            # --- Resume the agent with the user's choice ---
            print(f"\n--- [3b] Resuming agent with selection: {choice_index} ---\n")
            
            # Create the resumed state and stream again
            resumed_state = await continue_research(state, choice_index, config)
            async for update in deep_researcher.astream(resumed_state, config):
                state = list(update.values())[0] # Update state until the final result

        # --- Final Output Processing ---
        print("\n" + "=" * 60)
        print("--- [4] AGENT EXECUTION FINISHED ---")
        print("=" * 60 + "\n")

        # Now, process the final state regardless of how we got here
        show_judge_xai(state)
        notes = state.get("notes", [])
        print("\n--- FINAL RESEARCH NOTES (Agent Summaries) ---")
        if not notes:
            print("The agent did not produce any research notes.")
        else:
            for i, note in enumerate(notes, 1):
                print(f"\n[Note {i}]\n{note}")

        summarize_image_search_for_manager(notes)
        process_and_display_evidence(notes)

        print("\n\n--- TEST VERIFICATION ---")
        print(f"notes count: {len(notes)}")
        if notes:
            print("✅ SUCCESS: The 'notes' field is populated.")
        else:
            print("❌ FAILURE: The 'notes' field is empty.")

    except Exception as e:
        print(f"\n❌ ERROR: Agent execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
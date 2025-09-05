from typing import Dict, Any, Optional, cast
from langchain.agents import AgentExecutor, Tool
from langchain.agents import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from typing import Optional
from ..tools import  insta_tools, search_tools, vision_tools
from ..constants.constants import Constants
import logging
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from pydantic import SecretStr
from langchain_core.callbacks import StdOutCallbackHandler, CallbackManager
import json # Import json for clean serialization
from typing import Dict, Any, Optional
from langchain_core.callbacks import StdOutCallbackHandler, CallbackManager
from typing import Any, Dict, List, Optional
import re


from multi_agents.Prompts.workers_prompts import (
    BASE_WORKER_PROMPT,
    AIRBNB_ANALYZER_PERSONA,
    SOCIAL_MEDIA_INVESTIGATOR_PERSONA,
    CROSS_PLATFORM_VALIDATOR_PERSONA,
    REPORT_SYNTHESIZER_PROMPT,
    OPEN_DEEP_RESEARCH_BRIEFING_PROMPT
)


import asyncio
from langchain_core.messages import HumanMessage
from multi_agents.open_deep_research.deep_researcher import deep_researcher

from multi_agents.database.airbnb_db import AirbnbDB



class BaseWorker:
    # vvv MODIFIED __init__ SIGNATURE vvv
    def __init__(self, tools: list, name: str, system_prompt_extension: str):
        '''
        self.llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name=Constants.MODEL_FOR_WORKER,
            temperature=0.1,
        )
        '''
        self.llm = ChatOpenAI(
            model=Constants.DEFAULT_MODEL,
            temperature=0.1,
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY or "")

        )
        self.tools = tools
        self.name = name
        self.logger = logging.getLogger(__name__)

        # vvv NEW, MORE CONTEXT-AWARE PROMPT vvv
        prompt = ChatPromptTemplate.from_messages([
            ("system", BASE_WORKER_PROMPT),
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
        self.agent_executor = AgentExecutor(agent=self.agent, tools=tools, verbose=True,handle_parsing_errors=True,   
    max_iterations=8,
    early_stopping_method="generate", )

    # vvv MODIFIED run METHOD vvv
    def run(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
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
            }, config)
            
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
    """
    DB-only SQL agent. Pulls everything about a host from Airbnb.db.
    No scraping. Thread-safe (fresh SQLite connection per call).
    """

    def __init__(self):
        self.db_path = Constants.CONFIG_DB_FILE  # use your resolved DB path
        tools = [
            Tool(
                name="get_host_all",
                description=(
                    "Return EVERYTHING we know about a host from the DB: "
                    "core profile row + listings + listings_detailed + ALL reviews + "
                    "guidebooks + travels + listing pictures. "
                    'Input JSON: {"host": "<user url or id>"}.'
                ),
                func=self._tool_get_host_all,
            ),
        ]
        super().__init__(tools, "Airbnb_Analyzer", AIRBNB_ANALYZER_PERSONA)
        self.logger = logging.getLogger(__name__)

    # ---------- internals ----------
    def _db(self) -> AirbnbDB:
        # fresh connection per call => avoids cross-thread sqlite issues
        return AirbnbDB(self.db_path)

    def _parse_user_id(self, s: str) -> Optional[str]:
        if not s:
            return None
        if s.isdigit():
            return s
        m = re.search(r"/users/show/(\d+)", s)
        return m.group(1) if m else None

    # robust profile fetch (by id, then by URL)
    def _fetch_profile(self, db: AirbnbDB, host: str) -> Optional[Dict[str, Any]]:
        user_id = self._parse_user_id(host)

        # 1) by id (host_tracking)
        if user_id:
            try:
                cur = db.conn.execute(
                    """
                    SELECT *
                    FROM host_tracking
                    WHERE userId = ?
                    ORDER BY rowid DESC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception as e:
                self.logger.warning(f"host_tracking by userId failed: {e}")

            # if AirbnbDB exposes a helper:
            for name in ("host_by_id", "get_host_by_id"):
                if hasattr(db, name):
                    try:
                        r = getattr(db, name)(user_id)
                        if r:
                            return dict(r)
                    except Exception:
                        pass

        # 2) by url (host_tracking)
        if host and host.startswith("http"):
            try:
                cur = db.conn.execute(
                    """
                    SELECT *
                    FROM host_tracking
                    WHERE userUrl = ?
                    ORDER BY rowid DESC
                    LIMIT 1
                    """,
                    (host,),
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception as e:
                self.logger.warning(f"host_tracking by userUrl failed: {e}")

            # if AirbnbDB exposes a helper:
            for name in ("host_by_url", "get_host_by_url"):
                if hasattr(db, name):
                    try:
                        r = getattr(db, name)(host)
                        if r:
                            return dict(r)
                    except Exception:
                        pass

        return None

    def _listings(self, db: AirbnbDB, uid: str) -> List[Dict[str, Any]]:
        # prefer helper if present
        for name in ("host_listings", "get_host_listings"):
            if hasattr(db, name):
                try:
                    L = getattr(db, name)(uid) or []
                    return [dict(x) for x in L]
                except Exception:
                    pass
        # fallback raw SQL selecting the simple mapping table you showed
        try:
            cur = db.conn.execute(
                """
                SELECT userId, name, listingId, listingUrl
                FROM host_listings
                WHERE userId = ?
                ORDER BY rowid DESC
                """,
                (uid,),
            )
            return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def _listings_detailed(self, db: AirbnbDB, uid: str) -> List[Dict[str, Any]]:
        # prefer helper if present
        for name in ("host_listings_detailed", "get_host_listings_detailed"):
            if hasattr(db, name):
                try:
                    rows = getattr(db, name)(uid) or []
                    return [dict(x) for x in rows]
                except Exception:
                    pass
        # fallback: your table looked like 'listing_tracking'
        try:
            cur = db.conn.execute(
                """
                SELECT *
                FROM listing_tracking
                WHERE userId = ?
                ORDER BY rowid DESC
                """,
                (uid,),
            )
            return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def _reviews_all(self, db: AirbnbDB, uid: str) -> List[Dict[str, Any]]:
        # prefer helper without limit
        for name in ("host_reviews", "get_host_reviews"):
            if hasattr(db, name):
                try:
                    rows = getattr(db, name)(uid) or []
                    return [dict(x) for x in rows]
                except Exception:
                    pass
        # fallback raw SQL
        try:
            cur = db.conn.execute(
                """
                SELECT *
                FROM host_reviews
                WHERE userId = ?
                ORDER BY id ASC
                """,
                (uid,),
            )
            return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def _guidebooks(self, db: AirbnbDB, uid: str) -> List[Dict[str, Any]]:
        for name in ("host_guidebooks", "get_host_guidebooks"):
            if hasattr(db, name):
                try:
                    rows = getattr(db, name)(uid) or []
                    return [dict(x) for x in rows]
                except Exception:
                    pass
        try:
            cur = db.conn.execute(
                """
                SELECT *
                FROM host_guidebooks
                WHERE userId = ?
                ORDER BY id ASC
                """,
                (uid,),
            )
            return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def _travels(self, db: AirbnbDB, uid: str) -> List[Dict[str, Any]]:
        for name in ("host_travels", "get_host_travels"):
            if hasattr(db, name):
                try:
                    rows = getattr(db, name)(uid) or []
                    return [dict(x) for x in rows]
                except Exception:
                    pass
        try:
            cur = db.conn.execute(
                """
                SELECT *
                FROM host_travels
                WHERE userId = ?
                ORDER BY rowid ASC
                """,
                (uid,),
            )
            return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def _pictures_for_listing(self, db: AirbnbDB, listing_id: str) -> List[Dict[str, Any]]:
        # prefer helper returning an array of {idx, url}
        for name in ("listing_pictures", "get_listing_pictures"):
            if hasattr(db, name):
                try:
                    pics = getattr(db, name)(listing_id) or []
                    return [dict(p) for p in pics]
                except Exception:
                    pass

        # fallback raw SQL against your denormalized columns picture_1..picture_N
        try:
            cur = db.conn.execute(
                """
                SELECT *
                FROM listing_pictures
                WHERE ListingId = ?
                LIMIT 1
                """,
                (listing_id,),
            )
            row = cur.fetchone()
            out = []
            if row:
                d = dict(row)
                # detect keys like picture_1..picture_99
                for k, v in d.items():
                    if k.startswith("picture_") and v:
                        try:
                            idx = int(k.split("_")[1])
                        except Exception:
                            idx = None
                        out.append({"idx": idx, "url": v})
            return sorted(out, key=lambda x: (x["idx"] if x["idx"] is not None else 9999))
        except Exception:
            return []

    def _collect_pictures(self, db: AirbnbDB, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for L in listings:
            lid = str(L.get("listingId") or L.get("ListingId") or "")
            if not lid:
                continue
            pics = self._pictures_for_listing(db, lid)
            result.append({"listingId": lid, "pictures": pics})
        return result

    # optional: dedupe if your reviews table contains repeated blocks
    def _dedupe_reviews(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out = []
        for r in rows:
            key = (
                r.get("reviewer_name", ""),
                r.get("reviewer_location", ""),
                r.get("date_text", ""),
                r.get("rating", ""),
                (r.get("text") or "").strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    # lightweight NLP: summarize themes + possible “personal life” hints
    def _summarize_reviews(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        summary = {
            "total_reviews": len(reviews),
            "avg_rating_reported": None,  # filled from core/listing if available
            "positives": 0,
            "negatives": 0,
            "common_themes": {
                "cleanliness": 0,
                "responsiveness": 0,
                "location": 0,
                "quiet": 0,
                "value": 0,
            },
            "possible_personal_info": {
                "mentions_partner_or_marriage": False,
                "mentions_family_or_kids": False,
            },
            "sample_reviewers": [],  # list of "Name (Location?)"
        }

        # crude heuristics
        pos_words = ["great", "very good", "excellent", "clean", "kind", "welcoming", "responsive", "recommend", "perfect"]
        neg_words = ["dirty", "noisy", "problem", "issue", "deception", "not very clean", "smell", "bad"]
        theme_map = {
            "clean": "cleanliness",
            "very clean": "cleanliness",
            "neat": "cleanliness",
            "responsive": "responsiveness",
            "communication": "responsiveness",
            "location": "location",
            "well located": "location",
            "quiet": "quiet",
            "value": "value",
            "price": "value",
        }
        couple_words = ["wife", "husband", "partner", "girlfriend", "boyfriend", "married", "spouse", "fiancé", "fiance"]
        family_words = ["kids", "children", "family", "son", "daughter", "with my family"]

        for r in reviews[:1000]:  # safety cap for speed
            t = (r.get("text") or "").lower()
            # sentiment-ish
            if any(w in t for w in pos_words):
                summary["positives"] += 1
            if any(w in t for w in neg_words):
                summary["negatives"] += 1
            # themes
            for k, theme in theme_map.items():
                if k in t:
                    summary["common_themes"][theme] += 1
            # personal hints
            if any(w in t for w in couple_words):
                summary["possible_personal_info"]["mentions_partner_or_marriage"] = True
            if any(w in t for w in family_words):
                summary["possible_personal_info"]["mentions_family_or_kids"] = True

            # sampler
            nm = r.get("reviewer_name") or "Unknown"
            loc = r.get("reviewer_location") or ""
            summary["sample_reviewers"].append(nm if not loc else f"{nm} ({loc})")

        # small dedupe of samples
        summary["sample_reviewers"] = list(dict.fromkeys(summary["sample_reviewers"]))[:20]
        return summary

    # ---------- tool ----------
    def _tool_get_host_all(self, inp: str) -> Dict[str, Any]:
        """
        DB-only: given a host id or profile URL, pull EVERYTHING we have for that host
        from SQLite (host_tracking + host_listings + listing_tracking + host_reviews +
        host_guidebooks + host_travels + listing_pictures). Never scrapes.
        """
        try:
            data = json.loads(inp) if isinstance(inp, str) else (inp or {})
            host = str(data.get("host", "")).strip()

            db = self._db()

            # 1) profile
            profile = self._fetch_profile(db, host)
            if not profile:
                return {"status": "error_not_found", "reason": "host_not_in_db", "input": host}

            uid = str(profile.get("userId") or "")

            # 2) listings + detailed
            listings = self._listings(db, uid)
            listings_detailed = self._listings_detailed(db, uid)

            # 3) ALL reviews (no limit) + dedupe pass
            reviews_raw = self._reviews_all(db, uid) or []
            reviews = self._dedupe_reviews(reviews_raw)

            # 4) guidebooks / travels
            guidebooks = self._guidebooks(db, uid)
            travels = self._travels(db, uid)

            # 5) pictures for each listing
            pictures = self._collect_pictures(db, listings if listings else listings_detailed)

            # 6) review summary intel
            reviews_summary = self._summarize_reviews(reviews)

            # enrich avg rating if present in core or detailed
            try:
                if "ratingAverage" in profile and profile["ratingAverage"] is not None:
                    reviews_summary["avg_rating_reported"] = profile["ratingAverage"]
                elif listings_detailed:
                    # take first detailed row that has averageRating
                    for ld in listings_detailed:
                        if "averageRating" in ld and ld["averageRating"] is not None:
                            reviews_summary["avg_rating_reported"] = ld["averageRating"]
                            break
            except Exception:
                pass

            return {
                "status": "ok",
                "userId": uid,
                "core": profile,                    # host_tracking row
                "listings": listings,               # mapping table (userId, name, listingId, listingUrl)
                "listings_detailed": listings_detailed,  # listing_tracking rows
                "reviews": reviews,                 # ALL reviews (deduped)
                "reviews_summary": reviews_summary, # quick intel from reviews text
                "guidebooks": guidebooks,
                "travels": travels,
                "pictures": pictures,               # [{listingId, pictures:[{idx,url}, ...]}, ...]
            }

        except Exception as e:
            self.logger.exception("get_host_all failed")
            return {"status": "error", "error": str(e)}



class WebSearchInvestigator(BaseWorker):
    def __init__(self):
        tools = [
            Tool(name="tavily_search", func=search_tools.tavily_search, description="General web search using Tavily"),
            Tool(name="web_scraper", func=search_tools.web_scraper, description="Scrape content from a specific URL")
        ]
        
        super().__init__(tools, "Web_Search_Investigator", SOCIAL_MEDIA_INVESTIGATOR_PERSONA)



class OpenDeepResearchWorker:
    """
    Adapter that calls the entire Open Deep Research subgraph as a single worker.
    It translates the main agent state into an input for the subgraph and formats
    the subgraph's output back into a standard worker result.
    """
    def __init__(self, name: str = "open_deep_research"):
        self.name = name

    def _build_input_for_subgraph(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds a clean, focused input for the deep_researcher graph.
        """
        task_dict = state["plan"][0]["inputs"]
        
        core_query = task_dict.get("query", "")
        profile_image_url = task_dict.get("profile_picture_url", "")
        
        # Prepare a concise message for the internal deep_researcher graph's initial brief generation
        concise_initial_message_content = core_query
        if profile_image_url:
            concise_initial_message_content += f". Associated profile image: {profile_image_url}"

        # --- FIX: Construct a complete DeepResearchState dictionary here ---
        # Initialize all fields required by DeepResearchState, even if with None or empty lists.
        # This is the expected input format for deep_researcher.ainvoke
        # Map the main graph state into DeepResearchState expected by deep_researcher
        initial_deep_research_state_input: Dict[str, Any] = {
            "messages": [HumanMessage(content=concise_initial_message_content)],
            "research_brief": None, # This will be populated by the 'write_research_brief' node
            "image_url": profile_image_url, # Pass the image URL along so deep_researcher can use it
            # Fields below mirror DeepResearchState keys
            "supervisor_iterations": 0,
            "planner_messages": [],
            "notes": [],
            "serp_calls_used": 0,
            "candidates": [],
            "awaiting_disambiguation": False,
            "selected_candidate": state.get("selected_candidate"),
            "rejected_urls": [],
            # If a candidate has already been chosen at the outer level, skip re-running image probe
            "image_probe_done": True if state.get("selected_candidate") else False,
        }
        
        # The 'write_research_brief' node within deep_researcher will use 'messages[0].content'
        # to generate the structured 'research_brief' and 'supervisor_messages'.
        # The 'image_url' in this state is critical for its image search tools.

        return initial_deep_research_state_input
    async def _run_async(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """Asynchronous execution logic for the worker."""
        try:
            dr_input = self._build_input_for_subgraph(state)
            
            # --- START OF NEW LOGIC ---
            # This creates and injects the colorful printer
            final_config = config or {}
            existing_callbacks = final_config.get("callbacks")
            
            # This manager safely handles existing callbacks (like LangSmith's)
            # and adds our new one for beautiful console output.
            callback_manager = CallbackManager.configure(
                inheritable_callbacks=existing_callbacks,
                local_callbacks=[StdOutCallbackHandler()]
            )
            final_config["callbacks"] = callback_manager
            # --- END OF NEW LOGIC ---

            result_state = await deep_researcher.ainvoke(cast(Any, dr_input), final_config)

            # If the subgraph produced candidates and is pausing for disambiguation, surface them for HITL
            pending_candidates = []
            if result_state.get("awaiting_disambiguation"):
                pending_candidates = result_state.get("candidates") or []

            final_intelligence = result_state.get("evidence_summary")
            if not final_intelligence:
                notes = result_state.get("notes", [])
                final_intelligence = notes[-1] if notes else "The deep research agent produced no actionable intelligence."

            # This print block provides the final summary for the customer
            print("\n\n" + "="*50)
            print("--- DEEP RESEARCH COMPLETE ---")
            print("="*50)
            print(final_intelligence)
            print("="*50 + "\n")

            out: Dict[str, Any] = {
                "last_step_result": {
                    "worker": self.name,
                    "results": {self.name: final_intelligence},
                    "success": True,
                },
                "last_step_message": AIMessage(content=f"{self.name} completed its investigation and produced the following intelligence summary:\n\n{final_intelligence}")
            }
            if pending_candidates:
                out["last_step_result"]["candidates"] = pending_candidates
            return out
        except Exception as e:
            return {
                "last_step_result": { "worker": self.name, "results": {}, "success": False, "error": str(e) },
                "last_step_message": AIMessage(content=f"{self.name} failed with error: {str(e)}")
            }

    def run(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """Synchronous wrapper for the async run method, safe for notebooks/event-loops."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop: safe to use asyncio.run
            return asyncio.run(self._run_async(state, config))
        # Running inside an event loop (e.g., Jupyter). Try nest_asyncio for re-entrancy.
        try:
            import nest_asyncio  # type: ignore
            nest_asyncio.apply()
        except Exception:
            pass
        return loop.run_until_complete(self._run_async(state, config))




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
        
        super().__init__(tools, "Cross_Platform_Validator", CROSS_PLATFORM_VALIDATOR_PERSONA)

    def cross_check_details(self, input: str) -> Dict[str, Any]:
        """Custom tool to compare details across platforms."""
        # This would be implemented to compare names, locations, etc.
        return {"similarity_score": 0.8, "matching_fields": ["name", "location"]}

class ReportSynthesizer:
    def __init__(self):
        '''
        self.llm = ChatGroq(
            groq_api_key=Constants.GROQ_API_KEY,
            model_name=f"{Constants.MODEL_FOR_WORKER}",
            temperature=0.1,
            # max_tokens=4096
        )
        '''
        self.llm = ChatOpenAI(
            model=Constants.SYNTHESIZER_MODEL,
            temperature=0.1,
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY or "")
        )
        self.logger = logging.getLogger(__name__)
    
    def run(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_template(REPORT_SYNTHESIZER_PROMPT)
        
        chain = prompt | self.llm
        try:
            report = chain.invoke({
                "original_query": state["original_query"],
                "aggregated_results": state["aggregated_results"]
            }, config).content
            
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
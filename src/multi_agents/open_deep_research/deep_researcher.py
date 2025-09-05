# Drop-in replacement. Early HITL after image tools; normalized image outputs.
import asyncio
import os
import operator
import logging
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, Union, cast
import re
from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr
from typing_extensions import TypedDict
import json
from ..common.judge import adjudicate_conflicts , judge_candidates
from ..constants.judge_constants import JudgeConstants
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage, ToolMessage, BaseMessage, get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, BaseTool
from langgraph.graph import END, StateGraph
# --- Candidate extraction from SerpApi web search outputs (stdlib only) ---
from urllib.parse import urlparse

from ..constants.constants import Constants
from ..tools import search_tools
from .configuration import Configuration
from multi_agents.Prompts.open_deep_research_prompts import (
    lead_researcher_prompt, research_system_prompt,
    transform_messages_into_research_topic_prompt, summarize_tool_output_prompt,
   

)
from multi_agents.tools.vision_tools import compare_profile_pictures_tool
import warnings
warnings.filterwarnings(
    "ignore",
    message=r"Parameters \{'max_tokens'\}.*`model_kwargs`",
    category=UserWarning
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


# ==== RICH MODE KNOBS (safe big defaults) ====
RICH_MODE = True  # set False if you want the old terse behavior

# Context shaping (only used to protect JSON, not to shorten content)
PER_TOOLMSG_CLIP = 12000      # characters per ToolMessage before clipping
PLANNER_CONTEXT_CAP = 180000  # total chars for planner input window (very high)

# Model output sizes (use values supported by your model)
PLANNER_MAX_TOKENS   = 8192
AGGREGATOR_MAX_TOKENS = 8192
RESEARCHER_MAX_TOKENS = 4096  # per-parallel proposer

# Execution breadth/depth
MAX_TOTAL_SERP_CALLS = 15     # overall search budget
MAX_TOOL_CALLS_PER_TURN = 6
MAX_RESEARCHER_ITERATIONS = 20
SEARCH_TIMEOUT_SECONDS = 30    # per call










def keep_first_value(current_value: Optional[Any], new_value: Any) -> Any:
    return current_value if current_value is not None else new_value

def today_str() -> str:
    return f"{datetime.now():%a %b %d, %Y}"


def _safe_json_loads(text):
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode JSON from LLM extractor. Raw text: '{text}'")
                        return []
def get_api_key_for_model(_: str, __: RunnableConfig) -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set.")
    return key

def safe_format(template: str, **kwargs) -> str:
    esc = template.replace("{", "{{").replace("}", "}}")
    for k in kwargs.keys():
        esc = esc.replace("{{" + k + "}}", "{" + k + "}")
    return esc.format(**kwargs)

def _shorten(text: str, limit: int = 10000) -> str:
    if not isinstance(text, str):
        text = str(text)
    if len(text) <= limit:
        return text
    head = text[:limit]
    return head + f"\n...[truncated {len(text)-limit} chars]..."


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

_SOCIAL_HOSTS = (
    "facebook.com", "m.facebook.com", "fb.com",
    "instagram.com", "tiktok.com", "x.com", "twitter.com",
    "linkedin.com", "lnkd.in", "youtube.com", "youtu.be",
)

def _extract_emails(text: str) -> List[str]:
    return sorted(set(_EMAIL_RE.findall(text or "")))

def _social_from_url(u: str) -> Optional[str]:
    try:
        host = urlparse(u).netloc.lower()
    except Exception:
        return None
    if any(host.endswith(h) for h in _SOCIAL_HOSTS):
        return u
    return None

def _clean_title(t: str) -> str:
    t = (t or "").strip()
    # Common SERP separators
    for sep in [" | ", " – ", " — ", " · ", " :: "]:
        if sep in t:
            left = t.split(sep, 1)[0].strip()
            if 2 <= len(left) <= 120:
                return left
    return t[:120]











def _candidate_from_item(item: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Accepts a SerpApi web result item (organic, knowledge, etc.) and returns a candidate dict if useful."""
    link = (item.get("link") or item.get("url") or "").strip()
    title = _clean_title(item.get("title") or item.get("name") or "")
    snippet = (item.get("snippet") or item.get("description") or "")
    if not link or not title:
        return None

    # try to pull emails from snippet and secondary fields
    emails = set(_extract_emails(snippet))
    # collect social links (self + sitelinks)
    socials: List[str] = []
    maybe_social = _social_from_url(link)
    if maybe_social:
        socials.append(maybe_social)

    for sl in item.get("sitelinks", {}).get("expanded", []) or []:
        sl_link = (sl.get("link") or sl.get("url") or "").strip()
        if sl_link:
            ms = _social_from_url(sl_link)
            if ms and ms not in socials:
                socials.append(ms)
        emails.update(_extract_emails(sl.get("title", "") + " " + sl.get("snippet", "")))

    # flatten
    why_bits = []
    if snippet:
        why_bits.append(snippet[:200])
    if emails:
        why_bits.append("emails: " + ", ".join(sorted(emails)))
    if socials:
        why_bits.append("socials: " + ", ".join(socials[:3]))
    why = " | ".join(why_bits) if why_bits else "SERP match"

    return {
        "name": title,
        "url": link,
        "why": why,
    }

def extract_candidates_from_serp_outputs(results: List[Any]) -> List[Dict[str, str]]:
    """
    results: list of raw tool outputs returned by google_search/bing_search/duckduckgo_search tools.
    Each element may be a dict with SerpApi-like shape or an error string/dict.

    Returns a de-duplicated list of {name,url,why}.
    """
    seen = set()
    out: List[Dict[str, str]] = []

    for r in results:
          #  accept plain lists returned by search tools

        # --- Skip news containers entirely ---
        if isinstance(r, dict):
            eng = (r.get("engine") or "").lower()
            if eng == "google_news" or "news_results" in r:
                continue  # do not turn news into candidates


        if isinstance(r, list):
            for item in r:
                cand = _candidate_from_item(item)
                if cand and cand["url"] not in seen:
                    seen.add(cand["url"])
                    out.append(cand)
            continue
        if not isinstance(r, dict):
            # ignore non-dicts (timeouts text, etc.)
            continue

        # Google style: "organic_results"
        for item in (r.get("organic_results") or []):
            cand = _candidate_from_item(item)
            if cand and cand["url"] not in seen:
                seen.add(cand["url"])
                out.append(cand)

        # Knowledge panels / Top stories can also include useful links
        kg = r.get("knowledge_graph")
        if isinstance(kg, dict):
            kg_iter = [kg]
        elif isinstance(kg, list):
            kg_iter = kg
        else:
            kg_iter = []
        for kp in kg_iter:
            cand = _candidate_from_item(kp)
            if cand and cand["url"] not in seen:
                seen.add(cand["url"])
                out.append(cand)

        for ts in (r.get("top_stories") or []):
            cand = _candidate_from_item(ts)
            if cand and cand["url"] not in seen:
                seen.add(cand["url"])
                out.append(cand)

        # DuckDuckGo or other shapes might place results under "results"
        for item in (r.get("results") or []):
            cand = _candidate_from_item(item)
            if cand and cand["url"] not in seen:
                seen.add(cand["url"])
                out.append(cand)

    # Light heuristic: prefer profile-like titles first
    def _score(c: Dict[str, str]) -> int:
        n = c["name"].lower()
        u = c["url"].lower()
        score = 0
        if any(host in u for host in _SOCIAL_HOSTS):
            score += 3
        if any(k in n for k in ["profile", "guide", "about", "abdel"]):
            score += 1
        return -score  # sort ascending -> highest score first
    out.sort(key=_score)
    return out









def _normalize_image_tool_output(raw: Any) -> Dict[str, Any]:
    """Normalize image tool outputs to:
       {"engine": str, "best_guess": Optional[str], "matches": [ {title, link, thumbnail, source}, ... ]}"""
    if not isinstance(raw, dict):
        return {"engine": "unknown", "best_guess": None, "matches": []}
    engine = raw.get("engine") or raw.get("search_parameters", {}).get("engine") or "unknown"
    if "matches" in raw:
        return {"engine": engine, "best_guess": raw.get("best_guess"), "matches": raw.get("matches", [])}
    matches = []
    if engine == "google_lens":
        for m in raw.get("visual_matches", []) or []:
            matches.append({"title": m.get("title"), "link": m.get("link"), "thumbnail": m.get("thumbnail"), "source": m.get("source")})
    elif engine == "google_reverse_image":
        for m in (raw.get("inline_images") or raw.get("image_results") or []):
            matches.append({"title": m.get("title"), "link": (m.get("link") or m.get("source")), "thumbnail": m.get("thumbnail"), "source": m.get("source")})
    return {"engine": engine, "best_guess": raw.get("best_guess_label"), "matches": matches}


class Candidate(TypedDict, total=False):
    name: str
    url: str
    why: str

class DeepResearchState(TypedDict):
    messages: List[BaseMessage]
    research_brief: Optional[str]
    image_url: Annotated[Optional[str], keep_first_value]
    planner_messages: Annotated[List[BaseMessage], operator.add]
    supervisor_iterations: int
    notes: Annotated[List[str], operator.add]
    serp_calls_used: int
    candidates: Annotated[List[Candidate], operator.add]
    awaiting_disambiguation: bool
    selected_candidate: Optional[Candidate]
    rejected_urls: Annotated[List[str], operator.add]
    image_probe_done: bool



class ResearchQuestion(BaseModel):
    research_brief: str

class PlannerTurnOutput(BaseModel):
    reflection: str
    tool_calls: List[Dict[str, Any]]


@tool(description="Pause and reflect on findings; plan next steps.")
def think_tool(reflection: str) -> str:
    logger.info("think_tool: %s", reflection)
    return f"Reflection recorded: {reflection}"


async def get_all_tools(config: RunnableConfig) -> List[BaseTool]:
    base: List[BaseTool] = [
        think_tool,
        search_tools.web_scraper,
        search_tools.google_search,
        search_tools.bing_search,
        search_tools.duckduckgo_search,
        search_tools.yahoo_search,
        search_tools.yandex_search,
        search_tools.baidu_search,
        search_tools.google_image_search,
        search_tools.bing_images_search,
        search_tools.google_lens_search,
        search_tools.google_reverse_image_search,
        search_tools.google_maps_search,
        search_tools.google_hotels_search,
        search_tools.google_news_search,
        search_tools.youtube_search,
        search_tools.yelp_search,
        compare_profile_pictures_tool,
        # advanced_search_and_retrieve is *not* exposed until a candidate is chosen (see supervisor)
    ]
    agent_name = (config.get("configurable", {}) or {}).get("agent_name", "")
    if "supervisor" in agent_name:
        @tool(description="Mark the investigation complete.")
        def research_complete() -> str:
            return "Research is complete!"

        @tool(description="Delegate a focused research topic to a proposer team (parallel workers).")
        def conduct_research(research_topic: str) -> str:
            logger.info("conduct_research topic: %s", research_topic)
            return f"Delegated: {research_topic}"

        base.extend([research_complete, conduct_research])
    return base


async def researcher_agent(topic: str, config: RunnableConfig, model_name: str) -> List[str]:
    cfg = Configuration.from_runnable_config(config)
    tools_all = await get_all_tools(config)
    research_tools = [t for t in tools_all if t.name not in ("research_complete", "conduct_research", "think_tool")]

    model = ChatOpenAI(
        model=model_name,
        api_key=SecretStr(get_api_key_for_model(model_name, config)),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.1,
        model_kwargs={"max_tokens": RESEARCHER_MAX_TOKENS},
    ).bind_tools(research_tools)

    sys = research_system_prompt.format(date=today_str(), max_react_tool_calls=cfg.max_react_tool_calls)
    msgs: List[BaseMessage] = [SystemMessage(content=sys), HumanMessage(content=topic)]
    notes: List[str] = []

    for _ in range(cfg.max_react_tool_calls):
        resp = await model.ainvoke(msgs)
        msgs.append(resp)
        calls = getattr(resp, "tool_calls", []) or []
        if not calls:
            break
        for tc in calls:
            tname = tc.get("name")
            tool_ = next((t for t in research_tools if t.name == tname), None)
            if not tool_:
                continue
            try:
                obs = await tool_.ainvoke(tc.get("args", {}))
                notes.append(str(obs))
                msgs.append(ToolMessage(content=str(obs), name=tname or "", tool_call_id=tc.get("id", "")))
            except Exception as e:
                err = f"Tool {tname} error in {model_name}: {e}"
                notes.append(err)
                msgs.append(ToolMessage(content=err, name=tname or "", tool_call_id=tc.get("id", "")))
    return notes


async def write_research_brief(state: DeepResearchState, config: RunnableConfig) -> Dict[str, Any]:
    text = get_buffer_string(state["messages"])
    image_url = None
    m = re.search(r"(https?://[^\s]+(?:im_w=\d+))", text)
    if m:
        image_url = m.group(0)

    cfg = Configuration.from_runnable_config(config)
    model = ChatOpenAI(
        model=cfg.planner_model,
        api_key=SecretStr(get_api_key_for_model(cfg.planner_model, config)),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.1,
        model_kwargs={"max_tokens": 4096},
    )
    model_struct = cast(Any, model).with_structured_output(ResearchQuestion)
    prompt = safe_format(transform_messages_into_research_topic_prompt, messages=text, date=today_str())
    rq = cast(ResearchQuestion, await model_struct.ainvoke([HumanMessage(content=prompt)]))

    sys = safe_format(lead_researcher_prompt, date=today_str())
    return {
        "research_brief": rq.research_brief,
        "image_url": image_url,
        "planner_messages": [SystemMessage(content=sys), HumanMessage(content=rq.research_brief)],
        "supervisor_iterations": 0,
        "notes": [],
        "serp_calls_used": 0,
        "candidates": [],
        "awaiting_disambiguation": False,
        "selected_candidate": None,
        "rejected_urls": [],  
    }


async def supervisor(state: DeepResearchState, config: RunnableConfig) -> Dict[str, Any]:
    cfg = Configuration.from_runnable_config(config)
    sup_cfg: RunnableConfig = {"configurable": {**(config.get("configurable", {}) or {}), "agent_name": "supervisor"}}
    tools = await get_all_tools(sup_cfg)

    model = ChatOpenAI(
        model=cfg.planner_model,
        api_key=SecretStr(get_api_key_for_model(cfg.planner_model, config)),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.1,
        model_kwargs={"max_tokens": PLANNER_MAX_TOKENS},
    ).bind_tools(tools)
    

    # Ask the planner to be terse to avoid JSON truncation
    model_struct = cast(Any, model).with_structured_output(PlannerTurnOutput)
    

    def _clip_toolmsgs(msgs, per_msg_limit=3000, total_limit=20000):
        total = 0
        clipped = []
        for m in msgs:
            if isinstance(m, ToolMessage):
                text = getattr(m, "content", "")
                if len(text) > per_msg_limit:
                    text = text[:per_msg_limit] + f"… [truncated {len(text)-per_msg_limit} chars]"
                total += len(text)
                clipped.append(
                    ToolMessage(content=text, name=m.name, tool_call_id=getattr(m, "tool_call_id", ""))
                )
            else:
                clipped.append(m)
        # safety: enforce total cap
        while len(get_buffer_string(clipped)) > total_limit and len(clipped) > 3:
            clipped.pop(0)
        return clipped

    pruned_msgs = _clip_toolmsgs(state["planner_messages"])

    # Prepend a terse SystemMessage just for this turn
    pruned_msgs = _clip_toolmsgs(state["planner_messages"])
    planner_input = pruned_msgs if RICH_MODE else [SystemMessage(content="Be concise. ")] + pruned_msgs
    try:
        out: PlannerTurnOutput = await model_struct.ainvoke(planner_input)
    except Exception as e:
        # If JSON parsing failed due to length, retry with even smaller window + explicit brevity
        if "LengthFinishReasonError" in str(e) or "length limit" in str(e).lower():
            tiny_msgs = [SystemMessage(content="Be extremely concise. Reflection <= 60 words. Max 2 tool calls.")]
            if pruned_msgs:
                tiny_msgs += pruned_msgs[-3:]  # keep only the last 3
            out = await model_struct.ainvoke(tiny_msgs)
        else:
            raise


    def tname(tc: Dict[str, Any]) -> str:
        return tc.get("name") or tc.get("tool") or tc.get("function") or ""

    think = [tc for tc in out.tool_calls if tname(tc) == "think_tool"][:1]
    rest = [tc for tc in out.tool_calls if tname(tc) != "think_tool"]

    # hide advanced_search_and_retrieve until a candidate is chosen
    if not state.get("selected_candidate"):
        rest = [tc for tc in rest if tname(tc) != "advanced_search_and_retrieve"]


    ALLOWED_TOOLS = {
    "google_search","bing_search","duckduckgo_search","yahoo_search",
    "yandex_search","baidu_search",
    "google_image_search","bing_images_search",
    "google_lens_search","google_reverse_image_search",
    "google_maps_search","youtube_search","yelp_search","web_scraper",
      }
    BLOCKED_UNTIL_SELECTION = {"google_news_search", "google_hotels_search"}

    rest = [
    tc for tc in rest
    if (tname(tc) in ALLOWED_TOOLS)
    and (tname(tc) not in BLOCKED_UNTIL_SELECTION or state.get("selected_candidate"))
      ]
    







    max_actions = max(0, getattr(cfg, "max_tool_calls_per_turn", MAX_TOOL_CALLS_PER_TURN) - len(think))
    broad = {"google_search", "bing_search", "duckduckgo_search", "yahoo_search", "yandex_search", "baidu_search"}
    rest_sorted = sorted(rest, key=lambda x: ((tname(x) in broad), tname(x) != "advanced_search_and_retrieve"))
    chosen = think + rest_sorted[:max_actions]

    std: List[Dict[str, Any]] = []
    for tc in chosen:
        nm = tname(tc)
        if not nm:
            continue
        args = tc.get("args") or tc.get("arguments") or {}
        std.append({"name": nm, "args": args, "id": tc.get("id", f"auto_{nm}_{len(std)}")})

    return {
        "planner_messages": [AIMessage(content=out.reflection, tool_calls=std)],
        "supervisor_iterations": state.get("supervisor_iterations", 0) + 1,
    }

async def supervisor_tools(state: DeepResearchState, config: RunnableConfig) -> Dict[str, Any]:
    if (state.get("candidates") and not state.get("selected_candidate")) or state.get("awaiting_disambiguation"):
        return {"awaiting_disambiguation": True}

    last = state["planner_messages"][-1]
    calls = getattr(last, "tool_calls", []) or []
    if not calls:
        return {}

    cfg = Configuration.from_runnable_config(config)

    agg = ChatOpenAI(
        model=getattr(cfg, "aggregator_model", Constants.AGGREGATOR_MODEL),
        api_key=SecretStr(get_api_key_for_model(getattr(cfg, "aggregator_model", Constants.AGGREGATOR_MODEL), config)),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.0,
        model_kwargs={"max_tokens": AGGREGATOR_MAX_TOKENS},
    )

    all_notes: List[str] = []
    tool_msgs: List[ToolMessage] = []

    serpish = {
        "google_search","bing_search","duckduckgo_search","yahoo_search","yandex_search","baidu_search",
        "google_image_search","bing_images_search","google_lens_search","google_reverse_image_search",
        "google_maps_search","google_hotels_search","google_news_search","youtube_search","yelp_search",
    }
    used = state.get("serp_calls_used", 0)
    max_serp = max(0, getattr(cfg, "max_total_serp_calls", MAX_TOTAL_SERP_CALLS))

    action_calls = [c for c in calls if c.get("name") != "think_tool"]
    conduct_calls = [c for c in action_calls if c.get("name") == "conduct_research"]
    search_calls = [c for c in action_calls if c.get("name") in serpish]
    image_tool_names = {"google_reverse_image_search", "google_lens_search"}
    image_calls_all = [c for c in search_calls if c.get("name") in image_tool_names]
    BLOCKED_UNTIL_SELECTION = {"google_news_search", "google_hotels_search"}
    if not state.get("selected_candidate"):
        search_calls = [c for c in search_calls if c.get("name") not in BLOCKED_UNTIL_SELECTION]
        # Rebuild image/non-image sets after pruning
        image_calls_all    = [c for c in search_calls if c.get("name") in image_tool_names]
        nonimage_calls_all = [c for c in search_calls if c.get("name") not in image_tool_names]
    else:
        nonimage_calls_all = [c for c in search_calls if c.get("name") not in image_tool_names]
    if state.get("image_url") and not state.get("image_probe_done"):
        have = {c.get("name") for c in image_calls_all}
        for nm in ("google_reverse_image_search", "google_lens_search"):
            if nm not in have:
                image_calls_all.append({
                    "name": nm,
                    "args": {},
                    "id": f"auto_{nm}_{len(image_calls_all)}"
                })



    other_calls = [c for c in action_calls if c not in conduct_calls and c not in search_calls]
    







    
    rejected = set(state.get("rejected_urls") or [])
    def _is_blocked(call: Dict[str, Any]) -> bool:
        if call.get("name") != "web_scraper":
            return False
        url = (call.get("args") or {}).get("url") or ""
        return url in rejected

    image_calls_all    = [c for c in image_calls_all if not _is_blocked(c)]
    nonimage_calls_all = [c for c in nonimage_calls_all if not _is_blocked(c)]
    other_calls        = [c for c in other_calls if not _is_blocked(c)]

    remaining = max(0, max_serp - used)
    reserve_for_images = 2 if (state.get("image_url") and not state.get("image_probe_done")) else 0
    budget_for_images = min(len(image_calls_all), max(0, min(remaining, reserve_for_images) if reserve_for_images else remaining))
    image_calls = image_calls_all[:budget_for_images]
    remaining_after_images = remaining - len(image_calls)
    nonimage_calls = nonimage_calls_all[:max(0, remaining_after_images)]

    new_candidates: List[Candidate] = []
    awaiting = False
    note_text = ""
    image_probe_done = state.get("image_probe_done", False)

    selected_candidate_update: Optional[Candidate] = None

    # ---------- helper: dedup with permissive input typing ----------
    def _dedup(lst: List[Dict[str, Any]]) -> List[Candidate]:
        seen = set()
        out: List[Candidate] = []
        for c in lst:
            u = (str(c.get("url") or "")).strip().lower()
            n = (str(c.get("name") or "")).strip().lower()
            key = u or n
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({"name": str(c.get("name","")), "url": str(c.get("url","")), "why": str(c.get("why",""))})
        return out
    # ---------------------------------------------------------------

    # --- Delegation (optional) ---
    if conduct_calls:
        proposer_models = getattr(cfg, "proposer_models", Constants.PROPOSER_MODELS)
        MOA_TIMEOUT = getattr(cfg, "moa_timeout_seconds", 30)

        async def run_proposer(topic: str, model_name: str) -> List[str]:
            try:
                return await asyncio.wait_for(researcher_agent(topic, config, model_name), timeout=MOA_TIMEOUT)
            except asyncio.TimeoutError:
                return [f"⏰ Timeout after {MOA_TIMEOUT}s in proposer {model_name}"]
            except Exception as e:
                return [f"❌ Error in proposer {model_name}: {e}"]

        async def team_job(topic: str):
            tasks = [asyncio.create_task(run_proposer(topic, m)) for m in proposer_models]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return topic, results

        team_tasks = [asyncio.create_task(team_job(c.get("args", {}).get("research_topic", ""))) for c in conduct_calls]
        team_out = await asyncio.gather(*team_tasks, return_exceptions=True)

        final_note = ""
        for item in team_out:
            if isinstance(item, Exception):
                final_note += f"\n\n--- Aggregated Findings (team error) ---\n{item}"
                continue
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                final_note += f"\n\n--- Aggregated Findings (malformed team output) ---\n{item!r}"
                continue
            topic, results = item
            final_note += f"\n\n--- Aggregated Findings for Topic: '{topic}' ---\n"
            norm = [r if isinstance(r, list) else [f"Exception: {r}"] for r in results]
            for m, r in zip(proposer_models, norm):
                final_note += f"\n--- Sub-findings from Agent {m} ---\n" + "\n".join(r)

        all_notes.append(final_note)
        tool_msgs.append(ToolMessage(content=final_note, name="conduct_research_team", tool_call_id=conduct_calls[0]["id"]))

    # --- IMAGE TOOLS FIRST ---
    if image_calls:
        tool_map = {t.name: t for t in await get_all_tools(config)}
        SEARCH_TIMEOUT = getattr(cfg, "search_timeout_seconds", 15)

        async def run_img_call(call):
            name = call.get("name", "")
            args = dict(call.get("args", {}))
            if state.get("image_url") and "image_url" not in args:
                args["image_url"] = state["image_url"]
            return await asyncio.wait_for(tool_map[name].ainvoke(args), timeout=SEARCH_TIMEOUT)

        img_results: List[Any] = []
        for c in image_calls:
            try:
                r = await run_img_call(c)
            except asyncio.TimeoutError:
                r = {"error": f"⏰ Timeout after {SEARCH_TIMEOUT}s in {c.get('name')}"}
            except Exception as e:
                r = {"error": f"❌ Error in {c.get('name')}: {e}"}
            img_results.append(r)

        image_candidates: List[Candidate] = []
        for raw in img_results:
            norm = _normalize_image_tool_output(raw if isinstance(raw, dict) else {})
            matches = norm.get("matches", []) or []
            for m in matches:
                title = (m.get("title") or "").strip()
                link  = (m.get("link") or m.get("source") or "").strip()
                if not (title or link):
                    continue
                image_candidates.append({
                    "name": title or "Unknown",
                    "url": link,
                    "why": "Visually similar match from reverse image/Lens search",
                })

        used += len(image_calls)
        image_probe_done = True

        if image_candidates:
            cand_lines = "\n".join(f"- {c.get('name','?')} — {c.get('url','')}" for c in image_candidates)
            short_img = _shorten(f"Image search produced {len(image_candidates)} candidates:\n{cand_lines}", limit=1200)
            all_notes.append(short_img)
            tool_msgs.append(ToolMessage(content=short_img, name="image_search", tool_call_id=image_calls[0].get("id", "auto_image_0")))
            # 👇 add trace
            from ..common.trace import trace_event
            trace_event("image_candidates_found", {
                "count": len(image_candidates),
                "candidates": image_candidates[:5],  # cap for readability
            })
        else:
            msg = "Image search returned no actionable profile matches; proceeding with name-based search."
            all_notes.append(msg)
            tool_msgs.append(ToolMessage(content=msg, name="image_search", tool_call_id=image_calls[0]["id"]))
            


        

    # --- NON-IMAGE PARALLEL SEARCHES ---
    if nonimage_calls:
        tool_map = {t.name: t for t in await get_all_tools(config)}
        SEARCH_TIMEOUT = getattr(cfg, "search_timeout_seconds", 15)

        async def run_one(tname: str, targs: dict) -> Any:
            try:
                return await asyncio.wait_for(tool_map[tname].ainvoke(targs), timeout=SEARCH_TIMEOUT)
            except asyncio.TimeoutError:
                return {"error": f"⏰ Timeout after {SEARCH_TIMEOUT}s in {tname}"}
            except Exception as e:
                return {"error": f"❌ Error in {tname}: {e}"}

        tasks: List[asyncio.Task[Any]] = []
        for c in nonimage_calls:
            name = c.get("name", "")
            args = dict(c.get("args", {}))
            tasks.append(asyncio.create_task(run_one(name, args)))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        raw_results = [r for r in results if isinstance(r, dict)]
        serp_candidates = extract_candidates_from_serp_outputs(raw_results)
        serp_candidates = [c for c in serp_candidates if (c.get("url") or "") not in rejected]

        combined_candidates: List[Candidate] = _dedup(serp_candidates)  # <-- typing fixed

        # Optional LLM top-up (no cap)
        raw_text_blob = ""
        try:
            parts: List[str] = []
            for rr in raw_results:
                parts.append(str(rr)[:4000])
            raw_text_blob = "\n\n".join(parts)[:12000]
        except Exception:
            raw_text_blob = ""

        if raw_text_blob:
            extraction_prompt = (
                "From the text below, extract ALL possible candidate entities (people/companies/profiles) "
                "that might match the brief.\nReturn STRICT JSON list of objects with fields: name, url, why.\n"
                f"Brief:\n{state.get('research_brief')}\n\nText:\n{raw_text_blob}\n"
            )
            extractor = ChatOpenAI(
                model=getattr(cfg, "candidate_extraction_model", getattr(cfg, "aggregator_model", Constants.AGGREGATOR_MODEL)),
                api_key=SecretStr(get_api_key_for_model(getattr(cfg, "candidate_extraction_model", getattr(cfg, "aggregator_model", Constants.AGGREGATOR_MODEL)), config)),
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                temperature=0.0,
            )
            try:
                ext = await extractor.ainvoke([HumanMessage(content=extraction_prompt)])
            
                extracted = _safe_json_loads(raw if isinstance(raw, str) else str(raw))
                extra_cands: List[Dict[str, Any]] = []
                for e in extracted or []:
                    extra_cands.append({
                        "name": str(e.get("name","")).strip(),
                        "url":  str(e.get("url","")).strip(),
                        "why":  str(e.get("why","")).strip(),
                    })
                combined_candidates = _dedup(combined_candidates + extra_cands)  # type: ignore[arg-type]
            except Exception as e:
                logger.warning("LLM top-up candidate extraction failed: %s", e)

        if combined_candidates:
            cand_lines = []
            for i, cand in enumerate(combined_candidates):
                nm = cand.get("name") or "?"
                url = cand.get("url") or ""
                why = cand.get("why") or ""
                cand_lines.append(f"[{i}] {nm} — {url}\n      why: {why}")
            note_text = "Candidates from web search:\n" + "\n".join(cand_lines)
            all_notes.append(note_text)
            tool_msgs.append(ToolMessage(content=note_text, name="web_search_candidates", tool_call_id=nonimage_calls[0].get("id", "auto_nonimage_0")))
            used += len(nonimage_calls)
            new_candidates = combined_candidates
            awaiting = True

            # Ask the judge to rank; hint what matters (relevance for search)
            judge_out = await judge_candidates(
                research_brief=state.get("research_brief") or "",
                candidates=new_candidates,
                notes=all_notes,                 # or [note_text] if you want only the latest
                config=config,
                aspect_hint="relevance",         # SMoA gate to relevance-savvy models
            )

            
            # Persist ranking + diagnostics for transparency
            diag = judge_out.get("diagnostics") or {}
            all_notes.append(
                "[judge] "
                f"ranking={judge_out.get('ranking')} "
                f"winner_index={judge_out.get('winner_index')} "
                f"conf={judge_out.get('confidence')} "
                f"diag={str(diag)[:800]}"
            )

            # Bias/uncertainty guardrails — force HITL if position bias looks high
            bias = (diag.get("bias") or {}) if isinstance(diag, dict) else {}
            pos_bias_rate = float(bias.get("position_bias_rate", 0.0)) if isinstance(bias, dict) else 0.0
            position_flip_alarm = float(getattr(JudgeConstants, "JUDGE_POSITION_FLIP_ALARM", 0.20))
            bias_alarm = pos_bias_rate >= position_flip_alarm

            # If confident and no bias alarm, auto-select; else pause for user disambiguation
            if (not judge_out.get("should_pause_for_human")) and (judge_out.get("winner_index") is not None) and (not bias_alarm):
                wi = int(judge_out["winner_index"])
                if 0 <= wi < len(new_candidates):
                    selected_candidate_update = new_candidates[wi]
                    awaiting = False
            else:
                awaiting = True

            # Human-readable tool message with diagnostics
            router_diag = (diag.get("router") or {}) if isinstance(diag, dict) else {}
            chosen_models = router_diag.get("chosen_models", [])
            tool_msgs.append(
                ToolMessage(
                    content=(
                        "LLM Judge decision:\n"
                        f"- winner_index: {judge_out.get('winner_index')}\n"
                        f"- confidence: {judge_out.get('confidence'):.3f}\n"
                        f"- pause: {judge_out.get('should_pause_for_human')} (bias_alarm={bias_alarm})\n"
                        f"- ranking (top 5): {str(judge_out.get('ranking', []))[:800]}\n"
                        f"- router chosen models: {chosen_models}\n"
                        f"- bias diag: {bias}"
                    ),
                    name="llm_judge",
                    tool_call_id="judge_candidates"
                )
            )






        else:
            combined_txt = ""
            for c, r in zip(nonimage_calls, results):
                combined_txt += f"\n\n--- Results from {c.get('name')} ---\n{r if not isinstance(r, Exception) else f'Exception: {r}'}"

            prompt = safe_format(
                summarize_tool_output_prompt,
                research_brief=state.get("research_brief"),
                tool_name="Parallel Search Batch",
                tool_args={c["name"]: c.get("args", {}) for c in nonimage_calls},
                tool_output=combined_txt[:25000],
            )
            summ = await agg.ainvoke([HumanMessage(content=prompt)])
            note_text = getattr(summ, "content", str(summ))
            all_notes.append(note_text)
            tool_msgs.append(ToolMessage(content=note_text, name="direct_search", tool_call_id=nonimage_calls[0].get("id", "auto_nonimage_0")))
            used += len(nonimage_calls)

            extraction_prompt = (
                "From the summary below, extract ALL candidate entities (people/companies/profiles) "
                "that might match the brief.\nReturn STRICT JSON list of objects with fields: name, url, why.\n"
                f"Brief:\n{state.get('research_brief')}\n\nSummary:\n{note_text}\n"
            )
            extractor = ChatOpenAI(
                model=getattr(cfg, "candidate_extraction_model", getattr(cfg, "aggregator_model", Constants.AGGREGATOR_MODEL)),
                api_key=SecretStr(get_api_key_for_model(getattr(cfg, "candidate_extraction_model", getattr(cfg, "aggregator_model", Constants.AGGREGATOR_MODEL)), config)),
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                temperature=0.0,
            )
            try:
                ext = await extractor.ainvoke([HumanMessage(content=extraction_prompt)])
                raw = getattr(ext, "content", "[]")
                import json
                extracted = json.loads(raw if isinstance(raw, str) else str(raw))
                cands_raw: List[Dict[str, Any]] = []
                for e in extracted or []:
                    cands_raw.append({
                        "name": str(e.get("name","")).strip(),
                        "url":  str(e.get("url","")).strip(),
                        "why":  str(e.get("why","")).strip(),
                    })
                new_candidates = _dedup(cands_raw)
                awaiting = bool(new_candidates)
            except Exception as e:
                logger.warning("candidate extraction failed: %s", e)
                new_candidates = []
                awaiting = False
    else:
        new_candidates = []
        awaiting = False

    # --- Other tools ---
    if other_calls:
        tool_map = {t.name: t for t in await get_all_tools(config)}
        for c in other_calls:
            t = tool_map.get(c.get("name", ""))
            if not t:
                continue
            obs = await t.ainvoke(c.get("args", {}))
            s = _shorten(str(obs), limit=20000)
            all_notes.append(s)
            tool_msgs.append(ToolMessage(content=s, name=c.get("name", ""), tool_call_id=c.get("id", f"auto_{c.get('name','tool')}_0")))

    # --- Judge (optional) ---
    try:
        judge_inputs = {}
        if note_text:
            judge_inputs["direct_search_summary"] = note_text

        if judge_inputs and getattr(cfg, "use_judge", True):
            arb = await adjudicate_conflicts(
                research_brief=state.get("research_brief") or "",
                agent_findings=judge_inputs,
                config=config,
            )
            tool_msgs.append(ToolMessage(content="Judge arbitration:\n" + str(arb), name="llm_judge", tool_call_id="judge_step"))
            judge_cands_raw: List[Dict[str, Any]] = []
            for c in arb.get("candidates") or []:
                judge_cands_raw.append({
                    "name": str(c.get("name","")).strip(),
                    "url":  str(c.get("url","")).strip(),
                    "why":  str(c.get("why","")).strip(),
                })
            if judge_cands_raw:
                new_candidates = _dedup((new_candidates or []) + judge_cands_raw)  # type: ignore[arg-type]
            if arb.get("should_pause_for_human"):
                awaiting = True
    except Exception as e:
        logger.warning(f"Judge arbitration failed: {e}")
    # --- SAFETY GUARD: no candidates, no URLs => stop early ---
    def _extract_urls_from_notes(notes: List[str]) -> set[str]:
        import re
        url_re = r'https?://[^\s,"\')<>]+'
        urls = set()
        for n in notes or []:
            urls.update(re.findall(url_re, n))
        return urls

    allowed_urls = _extract_urls_from_notes(all_notes)
    # --- SAFETY: stop early when there's nothing actionable ---
    if not new_candidates and not allowed_urls:
        tool_msgs.append(ToolMessage(
            content="No actionable candidates or URLs; stopping.",
            name="early_stop",
            tool_call_id="stop"))
        return {
            "planner_messages": tool_msgs,
            "notes": all_notes,
            "serp_calls_used": used,
            "candidates": new_candidates,
            "awaiting_disambiguation": False,   # make explicit
            "image_probe_done": image_probe_done,
            "selected_candidate": (
                selected_candidate_update
                if selected_candidate_update is not None
                else state.get("selected_candidate")
            ),
            "stop_now": True,                  
        }



    return {
    "planner_messages": tool_msgs,
    "notes": all_notes,
    "serp_calls_used": used,
    "candidates": new_candidates,
    "awaiting_disambiguation": awaiting,
    "image_probe_done": image_probe_done,

    "selected_candidate": selected_candidate_update if selected_candidate_update is not None else state.get("selected_candidate"),
}



# In deep_researcher.py

def should_continue_supervisor(state: DeepResearchState) -> Union[str, object]:
    # *** THIS IS THE CRITICAL ADDITION ***
    if state.get("awaiting_disambiguation"):
        logger.info("⛔ Awaiting human disambiguation on candidates; pausing graph.")
        return "__end__"

    # The rest of the function remains the same
    iters = state.get("supervisor_iterations", 0)
    cfg = Configuration.from_runnable_config()
    max_iters = getattr(cfg, "max_researcher_iterations", MAX_RESEARCHER_ITERATIONS)

    if not state["planner_messages"]:
        return "__end__"

    last = state["planner_messages"][-1]
    calls = getattr(last, "tool_calls", []) or []

    if iters >= max_iters:
        logger.info("⏰ Reached max planner iterations.")
        return "__end__"
    if not calls:
        logger.info("No tool calls; stopping.")
        return "__end__"
        
    # NEW: Check for an explicit stop signal
    if any(getattr(c, "name", "") == "research_complete" for c in calls):
        logger.info("✅ `research_complete` tool called. Ending.")
        return "__end__"

    return "supervisor_tools"

def _route_entry(state: DeepResearchState) -> str:
    return "supervisor" if state.get("research_brief") else "write_research_brief"


def init_state(query: str, image_url: Optional[str] = None) -> DeepResearchState:
    msg = query if not image_url else f"{query}\nProfile image: {image_url}"

    return {
    "messages": [HumanMessage(content=msg)],
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
    "image_probe_done": False,  # NEW
}


def resume_after_user_choice(prev_state: DeepResearchState, selection_index: int) -> DeepResearchState:
    cand_list = prev_state.get("candidates", []) or []
    chose_none = selection_index < 0 or selection_index >= len(cand_list)
    chosen = None if chose_none else cand_list[selection_index]

    new_state = dict(prev_state)
    new_state["selected_candidate"] = chosen
    new_state["awaiting_disambiguation"] = False

    # NEW: build a list of URLs we must not scrape if user said "none"
    if chose_none:
        # capture the candidate URLs that were proposed
        rejected = [c.get("url", "") for c in cand_list if c.get("url")]
        # persist them
        new_state["rejected_urls"] = list(set((prev_state.get("rejected_urls") or []) + rejected))
        # clear candidates so we don't immediately pause again
        new_state["candidates"] = []
        # also add a trace message to the conversation
        new_state["messages"] = list(prev_state.get("messages", [])) + [
            AIMessage(content="User rejected all proposed candidates. Do not scrape or follow these URLs again.")
        ]
    else:
        chosen_cand: Candidate = cast(Candidate, chosen)
        new_state["messages"] = list(prev_state.get("messages", [])) + [
            AIMessage(
                content=f"User selected candidate: {chosen_cand.get('name','?')} {chosen_cand.get('url','')}"
            )
        ]

    return cast(DeepResearchState, new_state)

async def start_research(query: str, image_url: Optional[str] = None, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    state = init_state(query, image_url)
    return await deep_researcher.ainvoke(state, config or {})

async def continue_research(prev_state: DeepResearchState, selection_index: int, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    state = resume_after_user_choice(prev_state, selection_index)
    return await deep_researcher.ainvoke(state, config or {})


def create_deep_researcher():
    g = StateGraph(DeepResearchState)
    g.add_node("write_research_brief", write_research_brief)
    g.add_node("supervisor", supervisor)
    g.add_node("supervisor_tools", supervisor_tools)

    g.add_conditional_edges("__start__", _route_entry, {
        "write_research_brief": "write_research_brief",
        "supervisor": "supervisor",
    })
    g.add_edge("write_research_brief", "supervisor")
    g.add_conditional_edges("supervisor", should_continue_supervisor, {
        "supervisor_tools": "supervisor_tools",
        "__end__": END,
    })
    g.add_edge("supervisor_tools", "supervisor")
    return g.compile()


deep_researcher = create_deep_researcher()

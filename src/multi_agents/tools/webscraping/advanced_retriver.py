# advanced_retriver.py
import os
import re
import time
import sqlite3
import logging
from typing import List, Tuple, Dict, Optional, Iterable, Any
from urllib.parse import urlparse

import numpy as np

try:
    import faiss  # type: ignore
except Exception:
    faiss = None  # Allow running without FAISS (will still work, just no ANN index)

from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import CrossEncoder

# ---- Your internal modules
from multi_agents.tools.webscraping import ScrapingUtils, Config

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("Retriever")

# --------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------
EMBED = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
_CE: Optional[CrossEncoder] = None

def _get_cross_encoder(name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> CrossEncoder:
    global _CE
    if _CE is None:
        _CE = CrossEncoder(name)
        log.info("Cross-encoder loaded: %s", name)
    return _CE

# --------------------------------------------------------------------------------------
# TRUST PROFILES (OSINT-friendly)
# --------------------------------------------------------------------------------------
TRUST_PROFILES: Dict[str, Dict[str, float]] = {
    "osint": {
        # Social
        "twitter.com": 1.30, "x.com": 1.30, "linkedin.com": 1.25, "facebook.com": 1.12,
        "instagram.com": 1.12, "tiktok.com": 1.05, "reddit.com": 1.15, "github.com": 1.18,
        "medium.com": 1.05, "stackexchange.com": 1.05, "stack overflow": 1.05,
        # Open docs / paste (soft)
        "pastebin.com": 1.03, "gist.github.com": 1.06,
        # OSINT tooling sites (soft bias)
        "intelx.io": 1.05, "haveibeenpwned.com": 1.05,
    },
    "academic": {
        "wikipedia.org": 1.20, "stanford.edu": 1.20, "mit.edu": 1.20, "nature.com": 1.15,
        "nasa.gov": 1.15, ".gov": 1.10, ".edu": 1.10,
    },
    "neutral": {},  # no domain boost
}

ACTIVE_TRUST: Dict[str, float] = TRUST_PROFILES["osint"]  # default profile

def set_trust_profile(name: str) -> None:
    global ACTIVE_TRUST
    ACTIVE_TRUST = TRUST_PROFILES.get(name, TRUST_PROFILES["neutral"])
    log.info("TRUST profile set to: %s", name)

# --------------------------------------------------------------------------------------
# SQLite feedback (keeps cheap up/down voting for domains/urls)
# --------------------------------------------------------------------------------------
def _db_conn():
    path = getattr(Config, "CONFIG_DB_FILE", "retriever.db")
    return sqlite3.connect(path)

def _ensure_feedback_tables():
    with _db_conn() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS retrieval_feedback(
          id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, query TEXT, url TEXT, label INTEGER
        );
        """)
        db.execute("""
        CREATE TABLE IF NOT EXISTS retrieval_seen(
          id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, query TEXT, url TEXT
        );
        """)
        db.commit()

def record_seen(query: str, url: str):
    with _db_conn() as db:
        db.execute("INSERT INTO retrieval_seen(ts,query,url) VALUES(?,?,?)",
                   (int(time.time()), query, url))
        db.commit()

def _feedback_boost(url: str) -> float:
    host = urlparse(url).netloc
    with _db_conn() as db:
        cur = db.execute("""
          SELECT SUM(CASE WHEN label>0 THEN 1 ELSE 0 END) up,
                 SUM(CASE WHEN label<0 THEN 1 ELSE 0 END) down
          FROM retrieval_feedback WHERE url LIKE ? OR url LIKE ?;
        """, (f"%{host}%", f"%{url}%"))
        row = cur.fetchone() or (0, 0)
    up, down = row[0] or 0, row[1] or 0
    total = up + down
    if total == 0:
        return 1.0
    return max(0.9, min(1.1, 1.0 + 0.10 * ((up - down) / max(1, total))))

# --------------------------------------------------------------------------------------
# SERP adapter
# --------------------------------------------------------------------------------------
_SERP_PAGE_PARAM = {"google": "start", "bing": "first", "duckduckgo": "start", "yandex": "p", "yahoo": "start"}
_SERP_QUERY_KEY  = {"google": "q",     "bing": "q",     "duckduckgo": "q",     "yandex": "text","yahoo": "p"   }
_PAGE_SIZE = 10

def _normalize_url(u: str) -> str:
    return (u or "").lower().split("#")[0].strip()

def _extract_links(engine: str, payload: Dict[str, Any]) -> List[str]:
    if engine == "duckduckgo":
        items = payload.get("results", []) or []
        return [_normalize_url(it.get("link") or it.get("url") or "") for it in items if it.get("link") or it.get("url")]
    items = payload.get("organic_results", []) or []
    return [_normalize_url(it.get("link") or "") for it in items if it.get("link")]

def _build_params(engine: str, query: str, start: int, num: int) -> Dict[str, Any]:
    qk, pk = _SERP_QUERY_KEY[engine], _SERP_PAGE_PARAM[engine]
    p: Dict[str, Any] = {"engine": engine, qk: query}
    if engine == "bing":
        p[pk] = max(1, start + 1); p["count"] = num
    elif engine == "yandex":
        p[pk] = start // _PAGE_SIZE; p["num"] = num
    else:
        p[pk] = start; p["num"] = num
    return p

def _serp_once(engine: str, query: str, start: int, page_size: int) -> List[str]:
    # ✅ Lazy import inside function instead of top
    from multi_agents.tools.search_tools import search_tools_instance
    res = search_tools_instance._execute_search(_build_params(engine, query, start, page_size))
    if isinstance(res, dict) and "error" in res:
        raise RuntimeError(res["error"])
    return _extract_links(engine, res if isinstance(res, dict) else {})


def bounded_multi_serp(
    query: str,
    engines: Iterable[str],
    serp_budget: int,
    page_size: int = _PAGE_SIZE
) -> Tuple[List[str], int]:
    """
    Crawl across engines but STOP when `serp_budget` calls are consumed.
    Returns (urls, serp_calls_used)
    """
    used = 0
    seen, out = set(), []
    for eng in engines:
        page = 0
        while used < serp_budget:
            try:
                links = _serp_once(eng, query, page * page_size, page_size)
                used += 1
                page += 1
                for u in links:
                    if not u: continue
                    if u in seen: continue
                    seen.add(u); out.append(u)
            except Exception as e:
                log.warning("SERP[%s] error '%s': %s", eng, query, e)
                used += 1
            # soft stop if engine yields nothing
            if used >= serp_budget or page > 20:
                break
        if used >= serp_budget:
            break
    return out, used

# --------------------------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------------------------
_NON_HTML_EXT = (".pdf",".csv",".tsv",".xls",".xlsx",".zip",".gz",".tar",".rar",".7z",
                 ".png",".jpg",".jpeg",".gif",".svg",".mp4",".mov",".mp3",".wav",
                 ".ppt",".pptx",".doc",".docx",".patch",".diff")

def _likely_non_html(u: str) -> bool:
    return any(urlparse(u).path.endswith(ext) for ext in _NON_HTML_EXT)

def _domain_boost(url: str) -> float:
    host = urlparse(url).netloc
    # precise match or suffix bias (".gov", ".edu")
    for key, w in ACTIVE_TRUST.items():
        if key.startswith("."):
            if host.endswith(key):
                return w
        elif key in host:
            return w
    return 1.0

def _bm25(query: str, doc: str, k1=1.5, b=0.75, avgdl=100.0) -> float:
    q = query.lower().split()
    d = doc.lower().split()
    dl = len(d) or 1
    score = 0.0
    for t in q:
        f = d.count(t)
        if f:
            idf = 1.5
            score += idf * ((f*(k1+1)) / (f + k1*(1 - b + b*(dl/avgdl))))
    return score

def _chunk(txt: str, size=800, overlap=120) -> List[str]:
    words = txt.split()
    out, i, step = [], 0, max(1, size-overlap)
    while i < len(words):
        out.append(" ".join(words[i:i+size])); i += step
    return out


def _is_good_chunk(s: str) -> bool:
    if not s: return False
    t = s.strip()
    if len(t) < 300:  # too short
        return False
    lower = t.lower()
    # Reject UI/boilerplate-y chunks
    bad_markers = (
        '"require":[["', "qpltimingsserverjs", "var __", "window.__", "cookie", "sign in",
        "log in", "enable javascript", "blocked this account"
    )
    if any(m in lower for m in bad_markers):
        return False
    # reject very high symbol density (likely JSON/JS)
    braces = sum(lower.count(c) for c in "{}[]")
    if braces > 0 and braces / max(1, len(lower)) > 0.015:
        return False
    # require some alphabetic density
    letters = sum(c.isalpha() for c in t)
    if letters / max(1, len(t)) < 0.55:
        return False
    return True



# --------------------------------------------------------------------------------------
# Cheap “think first” query planner (person-centric)
# --------------------------------------------------------------------------------------
def plan_osint_queries(seed: str) -> List[str]:
    seed = seed.strip()
    out = {seed}
    # add simple social-centric expansions
    out |= {f'{seed} site:linkedin.com', f'{seed} site:twitter.com OR site:x.com',
            f'{seed} site:instagram.com', f'{seed} site:facebook.com', f'{seed} site:github.com',
            f'{seed} profile', f'{seed} contact', f'{seed} email'}
    # reverse order tokens (helpful when names are “Last First”)
    toks = seed.split()
    if len(toks) > 1:
        out.add(" ".join(reversed(toks)))
    return list(out)

# --------------------------------------------------------------------------------------
# Retrieval core
# --------------------------------------------------------------------------------------
def _scrape_one(u: str) -> Optional[str]:
    """
    1) Force JS scrape on social/login-heavy domains.
    2) If fast scrape returns too little / too boilerplate, fall back to JS.
    3) Return None if content looks like UI strings (FB/IG JSON blobs).
    """
    SOCIAL_DOMAINS = (
        "instagram.com", "facebook.com", "m.facebook.com", "x.com", "twitter.com",
        "linkedin.com", "tiktok.com"
    )

    def _looks_like_boilerplate(txt: str) -> bool:
        t = (txt or "").strip()
        if len(t) < 400:  # very short => usually nav or cookie banners
            return True
        lower = t.lower()
        bad_markers = (
            "you must log in", "sign in", "cookies", "enable javascript",
            '"require":[["',  # FB/IG react init blobs
            "qpltimingsserverjs", "not now", "create account", "join to view profile",
        )
        if any(m in lower for m in bad_markers):
            return True
        # Very high punctuation/brace density is a sign of embedded JSON/JS
        braces = sum(lower.count(c) for c in "{}[]")
        if braces > 0 and braces / max(1, len(lower)) > 0.01:
            return True
        return False

    try:
        host = urlparse(u).netloc.lower()

        # 1) Force JS scrape for social
        if any(d in host for d in SOCIAL_DOMAINS):
            txt = ScrapingUtils.js_scrape(u) or ""
        else:
            # 2) Try fast first, fall back if “thin”
            txt = ScrapingUtils.fast_scrape(u) or ""
            if _looks_like_boilerplate(txt):
                js_txt = ScrapingUtils.js_scrape(u) or ""
                if len(js_txt) > len(txt):
                    txt = js_txt

        if not txt or _looks_like_boilerplate(txt):
            return None
        return txt

    except Exception as e:
        log.debug("scrape failed: %s -> %s", u, e)
        return None

def _hybrid(q_vec, c_vec, q_str: str, chunk: str, url: str) -> float:
    dense = float(np.dot(q_vec, c_vec.T))
    lex = _bm25(q_str, chunk)
    return (0.6 * dense + 0.4 * lex) * _domain_boost(url) * _feedback_boost(url)

def retrieve_context(
    query: str,
    subject_hint: Optional[str] = None,
    *,
    k_ctx: int = 10,
    trust_profile: str = "osint",
    engines: Iterable[str] = ("google","bing","duckduckgo"),  # leaner by default
    serp_budget: Optional[int] = None,                        # ← allow None
    apply_cross_encoder: bool = True,
    think_first: bool = True,
) -> Dict[str, Any]:
    """
    Returns:
      {
        "chunks": [{"text":..., "source":..., "score":...}, ...],
        "citations": [...],
        "metrics": {"serp_calls_used": int, "urls_scraped": int}
      }
    """
    if serp_budget is None:
        serp_budget = int(os.getenv("ADVANCED_SERP_BUDGET", "12"))
    _ensure_feedback_tables()
    set_trust_profile(trust_profile)

    # 0) Think-first (cheap planning)
    planned_queries: List[str] = plan_osint_queries(query) if think_first else [query]
    if subject_hint:
        planned_queries.insert(0, f'{query} "{subject_hint}"')

    # 1) Gather URLs with bounded SERP spend (across planned queries)
    all_urls, used = [], 0
    for q in planned_queries:
        if used >= serp_budget:
            break
        urls, inc = bounded_multi_serp(q, engines, serp_budget - used, page_size=_PAGE_SIZE)
        all_urls.extend(urls); used += inc

    # Deduplicate + filter non-HTML
    seen, urls_final = set(), []
    for u in all_urls:
        if not u: continue
        if _likely_non_html(u): continue
        if u in seen: continue
        seen.add(u); urls_final.append(u)

    # 2) Scrape lightweight first
    chunks: List[Tuple[str, str]] = []
    for u in urls_final:
        record_seen(query, u)
        txt = _scrape_one(u)
        if not txt: 
            continue
        for ch in _chunk(txt, 800, 120):
            if _is_good_chunk(ch):
              chunks.append((ch, u))

    if not chunks:
        return {"chunks": [], "citations": [], "metrics": {"serp_calls_used": used, "urls_scraped": 0}}

    texts = [c for c,_ in chunks]
    urls  = [u for _,u in chunks]

    q_vec = EMBED.encode([query], normalize_embeddings=True)[0]
    c_vecs = EMBED.encode(texts, normalize_embeddings=True)

    # Optionally ANN index; not required for correctness
    if faiss:
        try:
            idx = faiss.IndexFlatIP(c_vecs.shape[1])
            # ensure float32 & C-contiguous (FAISS requirement)
            X = np.ascontiguousarray(np.asarray(c_vecs, dtype=np.float32))
            # Most Python builds use the single-arg signature:
            idx.add(X)  # type: ignore[arg-type]  # silence strict type stubs
            # (If you *really* need to support ancient builds, you could try:
            #   except TypeError: idx.add_with_ids(X, np.arange(X.shape[0], dtype=np.int64))
            # but in practice the one-arg call is correct.)
        except Exception as e:
            log.debug("FAISS indexing disabled (non-fatal): %s", e)
            # it's optional; continue without ANN
            pass

    # Hybrid score
    scores = [_hybrid(q_vec, v, query, t, u) for (t,u), v in zip(chunks, c_vecs)]
    order = np.argsort(scores)[::-1]
    ranked = [(texts[i], urls[i], float(scores[i])) for i in order]

    # Cross-encoder rerank (top slice)
    final_docs: List[Tuple[str,str,float]]
    if apply_cross_encoder:
        ce = _get_cross_encoder()
        top = min(len(ranked), max(30, k_ctx*3))
        pairs = [(query, ranked[i][0]) for i in range(top)]
        ce_scores = ce.predict(pairs, convert_to_numpy=True)
        ce_order = np.argsort(ce_scores)[::-1][:k_ctx]
        final_docs = [(ranked[i][0], ranked[i][1], float(ce_scores[i])) for i in ce_order]
    else:
        final_docs = ranked[:k_ctx]

    citations, seen_u = [], set()
    for _, u, _ in final_docs:
        if u not in seen_u:
            citations.append(u); seen_u.add(u)

    return {
        "chunks": [{"text": t, "source": u, "score": s} for (t,u,s) in final_docs[:k_ctx]],
        "citations": citations,
        "metrics": {"serp_calls_used": used, "urls_scraped": len(set(urls))}
    }

def synthesize_answer(
    ctx: Dict[str, Any],
    *,
    k_ctx: int = 8,
) -> Dict[str, Any]:
    """
    Thin wrapper so callers can keep using advanced_retriver.synthesize_answer(...).
    """

    chunks = ctx.get("chunks", []) or []
    citations = ctx.get("citations", []) or []
    metrics = ctx.get("metrics", {}) or {}

    # Quick synthesis from top chunks
    bullets: List[str] = []
    for ch in chunks[: min(5, len(chunks))]:
        t = (ch.get("text") or "").strip().replace("\n", " ")
        if not t:
            continue
        short = t.split(". ")[0]
        bullets.append(f"- {short[:220].rstrip()}.")

    answer = "No high-confidence context found." if not bullets else "Key findings:\n" + "\n".join(bullets)

    return {
        "answer": answer,
        "citations": citations,
        "metrics": metrics,
    }
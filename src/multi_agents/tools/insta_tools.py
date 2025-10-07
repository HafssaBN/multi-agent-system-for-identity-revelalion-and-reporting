from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal

import duckdb
from apify_client import ApifyClient
from dotenv import load_dotenv
from langchain_core.tools import tool

# Local imports
from .database_manager import load_data_into_duckdb


# ---------- Config & Paths ----------
load_dotenv()

# Where to store JSON dumps and the DuckDB file
DATA_DIR = Path(os.getenv("INSTA_DATA_DIR", Path(__file__).resolve().parent / "instagram_data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "instagram_data.duckdb"

# Apify actor + token
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_INSTAGRAM_ACTOR = os.getenv("APIFY_INSTAGRAM_ACTOR", "shu8hvrXbJbY3Eb9W")  # default to your tested actor


def _owner_from_items(items: List[dict]) -> Optional[str]:
    """Best-effort owner username from post items."""
    for it in items or []:
        u = it.get("ownerUsername") or it.get("owner", {}).get("username")
        if u:
            return u
    return None


@tool
def instagram_scrape_and_load(
    username_or_url: str,
    results: Literal["details", "posts"] = "posts",
    results_limit: int = 20
) -> Dict[str, Any]:
    """
    Scrape Instagram profile 'details' or 'posts' via Apify, write JSON, then load into DuckDB.

    Args:
        username_or_url: "humansofny" or full profile URL.
        results: "details" | "posts".
        results_limit: number of posts to pull when results="posts".

    Returns:
        Dict with mode, json_path, db_path, counts, and owner_username.
    """
    if not APIFY_API_TOKEN:
        return {"error": True, "message": "Missing APIFY_API_TOKEN in environment/.env"}

    # Normalize URL
    if username_or_url.startswith(("http://", "https://")):
        url = username_or_url
        uname = username_or_url.rstrip("/").split("/")[-1] or "profile"
    else:
        uname = username_or_url.strip().lstrip("@")
        url = f"https://www.instagram.com/{uname}/"

    client = ApifyClient(APIFY_API_TOKEN)

    # Build actor input
    run_input: Dict[str, Any] = {"directUrls": [url], "resultsType": results}
    if results == "posts" and results_limit:
        run_input["resultsLimit"] = int(results_limit)

    # Run actor & fetch dataset
    run = client.actor(APIFY_INSTAGRAM_ACTOR).call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    # Save JSON
    json_path = DATA_DIR / f"instagram_{results}_{uname}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

    # Load into DuckDB
    mode = "details" if results == "details" else "posts"
    load_data_into_duckdb(json_path, DB_PATH, mode=mode)

    # Quick counts
    counts: Dict[str, int] = {}
    try:
        con = duckdb.connect(str(DB_PATH))
        if mode == "posts":
            counts["posts"] = con.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            counts["comments"] = con.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
            counts["images"] = con.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        else:
            counts["profiles"] = con.execute("SELECT COUNT(*) FROM instagram_profiles").fetchone()[0]
        con.close()
    except Exception:
        pass

    return {
        "mode": mode,
        "json_path": str(json_path),
        "db_path": str(DB_PATH),
        "counts": counts,
        "owner_username": _owner_from_items(items) or uname,
    }


@tool
def instagram_db_get_posts(username: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent posts for an ownerUsername from DuckDB (after scraping)."""
    q = """
      SELECT id, type, shortCode, caption, url, commentsCount, likesCount,
             strftime(timestamp, '%Y-%m-%d %H:%M:%S') AS timestamp,
             displayUrl, alt, ownerFullName, ownerUsername, ownerId, isSponsored
      FROM posts
      WHERE lower(ownerUsername) = lower(?)
      ORDER BY timestamp DESC NULLS LAST
      LIMIT ?
    """
    con = duckdb.connect(str(DB_PATH))
    cur = con.execute(q, [username, limit])
    rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    con.close()
    return rows


@tool
def instagram_db_get_images(post_id: str) -> List[Dict[str, Any]]:
    """Return image URLs for a given post_id."""
    q = "SELECT post_id, ownerId, ownerUsername, image_url FROM images WHERE post_id = ?"
    con = duckdb.connect(str(DB_PATH))
    cur = con.execute(q, [post_id])
    rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    con.close()
    return rows


@tool
def instagram_db_get_comments(post_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return latest comments for a given post_id."""
    q = """
      SELECT comment_id, post_id, comment_text,
             strftime(comment_timestamp, '%Y-%m-%d %H:%M:%S') AS comment_timestamp,
             comment_likes_count, owner_username, owner_id, owner_profile_pic_url
      FROM comments
      WHERE post_id = ?
      ORDER BY comment_timestamp DESC NULLS LAST
      LIMIT ?
    """
    con = duckdb.connect(str(DB_PATH))
    cur = con.execute(q, [post_id, limit])
    rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    con.close()
    return rows

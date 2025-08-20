# src/multi_agents/open_deep_research/database.py
import sqlite3
import json
import logging

DATABASE_FILE = "research_cache.db"
logger = logging.getLogger(__name__)

def setup_database():
    """Creates the database and the cache table if they don't exist."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            id INTEGER PRIMARY KEY,
            tool_name TEXT NOT NULL,
            tool_args_json TEXT NOT NULL,
            result_note TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tool_name, tool_args_json)
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database setup complete.")

def check_cache(tool_name: str, tool_args: dict) -> str | None:
    """Checks if a result for a given tool and arguments exists in the cache."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        args_json = json.dumps(tool_args, sort_keys=True)
        cursor.execute(
            "SELECT result_note FROM cache WHERE tool_name = ? AND tool_args_json = ?",
            (tool_name, args_json)
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            logger.info(f"✅ Cache HIT for tool '{tool_name}'")
            return result[0]
        return None
    except sqlite3.Error as e:
        logger.error(f"Database error in check_cache: {e}")
        return None


def add_to_cache(tool_name: str, tool_args: dict, result_note: str):
    """Adds a new result to the cache."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        args_json = json.dumps(tool_args, sort_keys=True)
        cursor.execute(
            "INSERT INTO cache (tool_name, tool_args_json, result_note) VALUES (?, ?, ?)",
            (tool_name, args_json, result_note)
        )
        conn.commit()
        conn.close()
        logger.info(f"📝 Cache MISS. Added result for tool '{tool_name}' to cache.")
    except sqlite3.IntegrityError:
        logger.warning(f"Cache entry for {tool_name} with args {tool_args} already exists.")
    except sqlite3.Error as e:
        logger.error(f"Database error in add_to_cache: {e}")
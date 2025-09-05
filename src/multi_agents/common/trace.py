# src/multi_agents/common/trace.py
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from .nosql_store import MongoTraceSink

# ---------- Config ----------
TRACES_DIR = os.getenv("TRACES_DIR", "./traces")

# Fallback run id if caller doesn’t pass one
_default_run_id = str(uuid.uuid4())


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")


def _date_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*\n\r\t'
    for ch in bad:
        name = name.replace(ch, "_")
    return name


def trace_event(kind: str, payload: Optional[Dict[str, Any]] = None, run_id: Optional[str] = None) -> None:
    """
    Save each trace event as a pretty JSON file and send it to MongoDB.

    Directory structure:
    traces/<date>/<run_id>/<kind>/<timestamp>.json
    """
    if payload is None:
        payload = {}

    rid = run_id or _default_run_id
    ts = _ts()
    today = _date_str()

    # Build the event object
    event = {
        "ts": ts,
        "kind": kind,
        "run_id": rid,
        "payload": payload,
    }

    # --- Write to local file (existing functionality) ---
    base_dir = os.path.join(TRACES_DIR, today, _sanitize_filename(rid), _sanitize_filename(kind))
    _ensure_dir(base_dir)
    file_path = os.path.join(base_dir, f"{ts}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(event, f, ensure_ascii=False, indent=2)

    # --- NEW: Send the event to MongoDB ---
    # This will send every event logged by any agent to your database.
    MongoTraceSink.save(kind, event)
# src/multi_agents/common/nosql_store.py
from __future__ import annotations
import certifi 
import os
import socket
from typing import Any, Dict, Optional
from urllib.parse import quote

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

class MongoTraceSink:
    """
    Optional MongoDB sink for trace events.
    Enabled when MONGO_URI is set.
    Writes each event as one document into <db>.traces.
    """

    _client: Optional[MongoClient] = None
    _enabled: bool = False

    @classmethod
    def init(cls) -> None:
        uri = os.getenv("MONGO_URI", "").strip()
        db_name = os.getenv("MONGO_DB", "multi_agents")
        if not uri:
            print("\n[MongoTraceSink] 🔴 MongoDB sink is DISABLED. Reason: MONGO_URI environment variable not set.")
            cls._enabled = False
            return

        # Hide credentials in log output for security
        safe_uri_display = "@".join(uri.split('@')[1:]) if '@' in uri else uri
        print(f"\n[MongoTraceSink] 🟡 Attempting to connect to MongoDB cluster: {safe_uri_display}")

        try:
            # Increase timeout to handle slower network conditions
            cls._client = MongoClient(uri, appname="multi-agents-traces", serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
            # Force a connection test by pinging the admin database
            cls._client.admin.command("ping")
            cls._enabled = True
            print("[MongoTraceSink] ✅ MongoDB connection successful. Tracing is ENABLED.")

            # Ensure indexes exist for efficient querying
            db = cls._client[db_name]
            col = db["traces"]
            col.create_index([("date", ASCENDING)])
            col.create_index([("run_id", ASCENDING)])
            col.create_index([("kind", ASCENDING)])
            col.create_index([("ts", ASCENDING)])
            print(f"[MongoTraceSink] ⚙️  Ensured indexes on '{db_name}.traces' collection.")
        except Exception as e:
            cls._client = None
            cls._enabled = False
            print(f"\n[MongoTraceSink] ❌ MongoDB connection FAILED. Tracing is DISABLED. Error: {e}\n")

    @classmethod
    def save(cls, kind: str, event: Dict[str, Any]) -> None:
        if not cls._enabled or not cls._client:
            return
        try:
            db = cls._client[os.getenv("MONGO_DB", "multi_agents")]
            col = db["traces"]
            # Add helpful metadata for filtering and analysis
            doc = {
                **event,
                "kind": kind,
                "date": event.get("ts", "")[:10],   # YYYY-MM-DD for easy date filtering
                "host": socket.gethostname(),
                "env": os.getenv("ENV", "dev"),
            }
            col.insert_one(doc)
        except PyMongoError as e:
            # Log write errors but don't crash the application
            print(f"[MongoTraceSink] ⚠️  Could not write to MongoDB. Error: {e}")
            pass

# Initialize the connection when the module is first imported
MongoTraceSink.init()
# src/multi_agents/database/airbnb_db.py
import sqlite3
from typing import Any, Dict, List, Optional
from pathlib import Path
from urllib.parse import quote
import re

class AirbnbDB:
    def __init__(self, db_path: str = "Airbnb.db"):
        p = Path(db_path).resolve()
        uri_path = quote(p.as_posix())
        uri = f"file:{uri_path}?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True)
        self.conn.row_factory = sqlite3.Row

    # ---------- helpers ----------
    def _row(self, q: str, *p) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(q, p)
        r = cur.fetchone()
        return dict(r) if r else None

    def _rows(self, q: str, *p) -> List[Dict[str, Any]]:
        cur = self.conn.execute(q, p)
        return [dict(r) for r in cur.fetchall()]

    def parse_user_id(self, s: str) -> Optional[str]:
        if not s:
            return None
        if s.isdigit():
            return s
        m = re.search(r"/users/show/(\d+)", s)
        return m.group(1) if m else None

    def parse_listing_id(self, s: str) -> Optional[str]:
        if not s:
            return None
        if s.isdigit():
            return s
        m = re.search(r"/rooms/(\d+)", s)
        return m.group(1) if m else None

    # ---------- HOST (ALL COLUMNS) ----------
    def host_core_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._row("""
            SELECT * FROM host_tracking
            WHERE userId = ?
            ORDER BY scraping_time DESC
            LIMIT 1
        """, user_id)

    def host_core_by_url(self, host_url: str) -> Optional[Dict[str, Any]]:
        return self._row("""
            SELECT * FROM host_tracking
            WHERE userUrl = ?
            ORDER BY scraping_time DESC
            LIMIT 1
        """, host_url)

    def host_listings(self, user_id: str) -> List[Dict[str, Any]]:
        return self._rows("""
            SELECT * FROM host_listings
            WHERE userId = ?
            ORDER BY rowid
        """, user_id)

    def host_reviews(self, user_id: str, limit: int = 2000) -> List[Dict[str, Any]]:
        return self._rows("""
            SELECT * FROM host_reviews
            WHERE userId = ?
            ORDER BY rowid
            LIMIT ?
        """, user_id, limit)

    def host_guidebooks(self, user_id: str) -> List[Dict[str, Any]]:
        return self._rows("""
            SELECT * FROM host_guidebooks
            WHERE userId = ?
            ORDER BY rowid
        """, user_id)

    def host_travels(self, user_id: str) -> List[Dict[str, Any]]:
        return self._rows("""
            SELECT * FROM host_travels
            WHERE userId = ?
            ORDER BY rowid
        """, user_id)

    def host_all(self, host: str, reviews_limit: int = 2000) -> Optional[Dict[str, Any]]:
        uid = self.parse_user_id(host)
        core = self.host_core_by_id(uid) if uid else None
        if not core and host.startswith("http"):
            core = self.host_core_by_url(host)
        if not core:
            return None
        user_id = str(core["userId"])
        return {
            "userId": user_id,
            "core": core,
            "listings": self.host_listings(user_id),
            "reviews": self.host_reviews(user_id, limit=reviews_limit),
            "guidebooks": self.host_guidebooks(user_id),
            "travels": self.host_travels(user_id),
        }

    # ---------- LISTING (ALL COLUMNS) ----------
    def listing_core(self, listing_id: str) -> Optional[Dict[str, Any]]:
        return self._row("""
            SELECT * FROM listing_tracking
            WHERE ListingId = ?
            ORDER BY scraping_time DESC
            LIMIT 1
        """, listing_id)

    def listing_pictures(self, listing_id: str) -> List[Dict[str, Any]]:
        row = self._row("""
            SELECT * FROM listing_pictures
            WHERE ListingId = ?
            LIMIT 1
        """, listing_id)
        if not row:
            return []
        pics = []
        for i in range(1, 200):
            k = f"picture_{i}"
            if k in row and row[k]:
                pics.append({"idx": i, "url": row[k]})
        return pics

    def listing_all(self, listing: str) -> Optional[Dict[str, Any]]:
        lid = self.parse_listing_id(listing)
        if not lid:
            return None
        core = self.listing_core(lid)
        if not core:
            return None
        return {
            "ListingId": lid,
            "core": core,
            "pictures": self.listing_pictures(lid),
        }

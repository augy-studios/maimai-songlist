"""
db.py — Database layer for maimai Songs Bot

Song data is fetched from Supabase (maimai_songlist table).
SQLite is used for any local bot state (future use: user preferences, etc.)
"""

import os
import sqlite3
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

_supabase: Client = None
SQLITE_PATH = "bot_state.db"


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ─── SQLite (local state) ─────────────────────────────────────────────────────

def init_db():
    """Initialise local SQLite database for bot state."""
    conn = sqlite3.connect(SQLITE_PATH)
    c = conn.cursor()
    # Placeholder table for future user preferences / history
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id     INTEGER PRIMARY KEY,
            last_cat    TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("SQLite initialised.")


# ─── Supabase queries ─────────────────────────────────────────────────────────

def _rows_to_dicts(rows) -> list[dict]:
    return rows if rows else []


def get_songs_by_category(category: str) -> list[dict]:
    sb = get_supabase()
    res = (
        sb.table("maimai_songlist")
        .select("*")
        .eq("catcode", category)
        .order("sort")
        .execute()
    )
    return _rows_to_dicts(res.data)


def search_songs(query: str) -> list[dict]:
    """Full-text style search across title and artist using ilike."""
    sb = get_supabase()
    q = f"%{query}%"
    # Supabase postgrest: filter with or
    res = (
        sb.table("maimai_songlist")
        .select("*")
        .or_(f"title.ilike.{q},artist.ilike.{q}")
        .order("sort")
        .execute()
    )
    return _rows_to_dicts(res.data)


def get_song_by_id(song_id: int) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table("maimai_songlist")
        .select("*")
        .eq("id", song_id)
        .single()
        .execute()
    )
    return res.data


def get_all_categories() -> list[str]:
    sb = get_supabase()
    res = (
        sb.table("maimai_songlist")
        .select("catcode")
        .execute()
    )
    seen = set()
    cats = []
    for row in (res.data or []):
        c = row["catcode"]
        if c not in seen:
            seen.add(c)
            cats.append(c)
    return cats


def get_song_count() -> int:
    sb = get_supabase()
    res = (
        sb.table("maimai_songlist")
        .select("id", count="exact")
        .execute()
    )
    return res.count or 0


def get_random_song() -> dict | None:
    """Fetch a random song. Uses Postgres random() via RPC or offset trick."""
    import random
    sb = get_supabase()
    # Get total count then fetch one at random offset
    count_res = (
        sb.table("maimai_songlist")
        .select("id", count="exact")
        .execute()
    )
    total = count_res.count or 0
    if total == 0:
        return None
    offset = random.randint(0, total - 1)
    res = (
        sb.table("maimai_songlist")
        .select("*")
        .range(offset, offset)
        .execute()
    )
    data = res.data
    return data[0] if data else None


def get_stats() -> dict[str, int]:
    """Return {catcode: count} for all categories."""
    sb = get_supabase()
    # Fetch all catcodes and count in Python (Supabase free tier has no group-by)
    res = (
        sb.table("maimai_songlist")
        .select("catcode")
        .execute()
    )
    counts: dict[str, int] = {}
    for row in (res.data or []):
        cat = row["catcode"]
        counts[cat] = counts.get(cat, 0) + 1
    return counts
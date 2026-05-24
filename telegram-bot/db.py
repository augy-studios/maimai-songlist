"""Database layer: Supabase for songs, SQLite for bot state."""

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


# ─── SQLite (local state)

def init_db():
    """Initialise local SQLite database for bot state."""
    conn = sqlite3.connect(SQLITE_PATH)
    c = conn.cursor()
    # user_prefs: placeholder for future preferences
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


# ─── Supabase queries

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
    """Search title and artist with ilike."""
    sb = get_supabase()
    q = f"%{query}%"
    # postgrest OR filter
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
    """Fetch a random song via random offset."""
    import random
    sb = get_supabase()
    # random offset into total count
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
    """Return {catcode: count} per category."""
    sb = get_supabase()
    counts: dict[str, int] = {}
    page_size = 1000
    offset = 0
    while True:
        res = (
            sb.table("maimai_songlist")
            .select("catcode")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = res.data or []
        for row in batch:
            cat = row["catcode"]
            counts[cat] = counts.get(cat, 0) + 1
        if len(batch) < page_size:
            break
        offset += page_size
    return counts
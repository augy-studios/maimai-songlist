"""
db.py - Database layer for maimai Songs Discord Bot

Song data is fetched from Supabase (maimai_songlist table).
SQLite is used for local bot state.
"""

import os
import json
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
    conn = sqlite3.connect(SQLITE_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id     INTEGER PRIMARY KEY,
            last_cat    TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS active_views (
            message_id  INTEGER PRIMARY KEY,
            view_type   TEXT    NOT NULL,
            state       TEXT    NOT NULL DEFAULT '{}'
        )
    """)
    conn.commit()
    conn.close()
    logger.info("SQLite initialised.")


def save_active_view(message_id: int, view_type: str, state: dict) -> None:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO active_views (message_id, view_type, state) VALUES (?, ?, ?)",
        (message_id, view_type, json.dumps(state, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def load_all_active_views() -> list[tuple[int, str, dict]]:
    conn = sqlite3.connect(SQLITE_PATH)
    rows = conn.execute(
        "SELECT message_id, view_type, state FROM active_views"
    ).fetchall()
    conn.close()
    return [(r[0], r[1], json.loads(r[2])) for r in rows]


# ─── Supabase queries ─────────────────────────────────────────────────────────

def _rows(res) -> list[dict]:
    return res.data if res.data else []


def get_songs_by_category(category: str) -> list[dict]:
    sb = get_supabase()
    res = (
        sb.table("maimai_songlist")
        .select("*")
        .eq("catcode", category)
        .order("sort")
        .execute()
    )
    return _rows(res)


def search_songs(query: str) -> list[dict]:
    sb = get_supabase()
    q = f"%{query}%"
    res = (
        sb.table("maimai_songlist")
        .select("*")
        .or_(f"title.ilike.{q},artist.ilike.{q}")
        .order("sort")
        .execute()
    )
    return _rows(res)


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


def get_song_count() -> int:
    sb = get_supabase()
    res = (
        sb.table("maimai_songlist")
        .select("id", count="exact")
        .execute()
    )
    return res.count or 0


def get_random_song() -> dict | None:
    import random
    sb = get_supabase()
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
    return res.data[0] if res.data else None


def get_stats() -> dict[str, int]:
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

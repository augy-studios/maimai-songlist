import os
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
from telethon.tl.types import InputPeerEmpty
from db import init_db, get_songs_by_category, search_songs, get_all_categories, get_song_count

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

client = TelegramClient("maimai_bot", API_ID, API_HASH)

SONGS_PER_PAGE = 8

CATEGORY_DISPLAY = {
    "POPS＆ANIME":         "POPS & ANIME",
    "niconico＆VOCALOID™": "niconico & VOCALOID™",
    "東方Project":          "東方Project",
    "GAME＆VARIETY":        "GAME & VARIETY",
    "maimai":               "maimai",
    "オンゲキ＆CHUNITHM":   "ONGEKI & CHUNITHM",
    "宴会場":               "宴会場",
}

CATEGORY_KEYS = list(CATEGORY_DISPLAY.keys())

CATEGORY_EMOJI = {
    "POPS＆ANIME":         "🎵",
    "niconico＆VOCALOID™": "🎤",
    "東方Project":          "🌸",
    "GAME＆VARIETY":        "🎮",
    "maimai":               "🍀",
    "オンゲキ＆CHUNITHM":   "🎯",
    "宴会場":               "🎊",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_category_buttons():
    """8 category buttons in a 2-column grid."""
    buttons = []
    row = []
    for key, label in CATEGORY_DISPLAY.items():
        emoji = CATEGORY_EMOJI.get(key, "🎵")
        row.append(Button.inline(f"{emoji} {label}", data=f"cat|{key}|0"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return buttons


def format_song(song: dict) -> str:
    """Format a single song entry for display."""
    cat = CATEGORY_DISPLAY.get(song["catcode"], song["catcode"])
    lines = [
        f"🎵 **{song['title']}**",
        f"👤 {song['artist']}",
        f"📂 {cat}",
    ]

    # Standard charts
    std = []
    for diff, label in [("lev_bas", "BAS"), ("lev_adv", "ADV"), ("lev_exp", "EXP"),
                         ("lev_mas", "MAS"), ("lev_remas", "Re:MAS")]:
        if song.get(diff):
            std.append(f"{label} {song[diff]}")
    if std:
        lines.append("📊 **STD:** " + " │ ".join(std))

    # DX charts
    dx = []
    for diff, label in [("dx_lev_bas", "BAS"), ("dx_lev_adv", "ADV"), ("dx_lev_exp", "EXP"),
                         ("dx_lev_mas", "MAS"), ("dx_lev_remas", "Re:MAS")]:
        if song.get(diff):
            dx.append(f"{label} {song[diff]}")
    if dx:
        lines.append("📊 **DX:** " + " │ ".join(dx))

    # Utage (宴会場)
    if song.get("lev_utage"):
        utage_info = f"🎊 **UTAGE:** {song['lev_utage']}"
        if song.get("kanji"):
            utage_info += f"  [{song['kanji']}]"
        if song.get("comment"):
            utage_info += f"\n💬 _{song['comment']}_"
        if song.get("buddy") == "○":
            utage_info += "  👥 Buddy"
        lines.append(utage_info)

    # Extra flags
    if song.get("key") == "○":
        lines.append("🔑 Key song")
    if song.get("date") == "NEW":
        lines.append("🆕 New!")

    return "\n".join(lines)


def paginate_song_list(songs: list, page: int, context: str) -> tuple[str, list]:
    """Return (text, buttons) for a paginated song list."""
    total = len(songs)
    total_pages = max(1, (total + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    start = page * SONGS_PER_PAGE
    chunk = songs[start: start + SONGS_PER_PAGE]

    lines = [f"📄 Page {page + 1}/{total_pages}  ({total} songs)\n"]
    for i, s in enumerate(chunk, start=start + 1):
        lines.append(f"{i}. **{s['title']}** — _{s['artist']}_")

    text = "\n".join(lines)

    # Navigation buttons
    nav = []
    if page > 0:
        nav.append(Button.inline("◀ Prev", data=f"{context}|{page - 1}"))
    if page < total_pages - 1:
        nav.append(Button.inline("Next ▶", data=f"{context}|{page + 1}"))

    # Detail buttons — one per song on this page
    detail_buttons = []
    for s in chunk:
        detail_buttons.append(
            [Button.inline(f"ℹ️ {s['title'][:30]}", data=f"detail|{s['id']}|{context}|{page}")]
        )

    back_row = [Button.inline("🔙 Categories", data="back_to_categories")]

    buttons = []
    if nav:
        buttons.append(nav)
    buttons.extend(detail_buttons)
    buttons.append(back_row)

    return text, buttons


# ─── /start ───────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern=r"^/start$"))
async def cmd_start(event):
    if event.is_group or event.is_channel:
        return
    total = get_song_count()
    text = (
        "👋 **Welcome to the maimai Song Browser!**\n\n"
        f"I have **{total} songs** in my database.\n\n"
        "**What I can do:**\n"
        "• Browse songs by category using the buttons below\n"
        "• Type any song title or artist name to search\n\n"
        "**Commands:**\n"
        "/start — Show this menu\n"
        "/random — Get a random song\n"
        "/stats — Show database statistics\n"
        "/help — Show detailed help\n\n"
        "👇 **Pick a category to browse:**"
    )
    await event.respond(text, buttons=make_category_buttons())


# ─── /help ────────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern=r"^/help$"))
async def cmd_help(event):
    if event.is_group or event.is_channel:
        return
    text = (
        "📖 **How to use this bot**\n\n"
        "**Browsing:**\n"
        "Use /start to open the category menu. Select a category to see all songs in it. "
        "Navigate pages with the ◀ Prev / Next ▶ buttons. "
        "Tap any song title to see its full details.\n\n"
        "**Searching:**\n"
        "Just type anything — a song title, artist name, or part of either. "
        "The search is instant and matches both fields.\n"
        "_Example:_ `bad apple`\n"
        "_Example:_ `DECO*27`\n\n"
        "**Commands:**\n"
        "/start — Main menu with category browser\n"
        "/random — Surprise me with a random song\n"
        "/stats — Song counts by category\n"
        "/help — This message\n\n"
        "**Difficulty labels:**\n"
        "BAS = Basic  │  ADV = Advanced  │  EXP = Expert\n"
        "MAS = Master  │  Re:MAS = Re:Master\n"
        "STD = Standard charts  │  DX = Deluxe charts"
    )
    await event.respond(text)


# ─── /random ──────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern=r"^/random$"))
async def cmd_random(event):
    if event.is_group or event.is_channel:
        return
    import random as rnd
    from db import get_random_song
    song = get_random_song()
    if not song:
        await event.respond("No songs found in the database.")
        return
    text = "🎲 **Random Song**\n\n" + format_song(song)
    await event.respond(
        text,
        buttons=[[Button.inline("🎲 Another random", data="random"),
                  Button.inline("🔙 Categories", data="back_to_categories")]]
    )


# ─── /stats ───────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern=r"^/stats$"))
async def cmd_stats(event):
    if event.is_group or event.is_channel:
        return
    from db import get_stats
    stats = get_stats()
    total = sum(v for v in stats.values())
    lines = ["📊 **Song Database Statistics**\n"]
    for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
        label = CATEGORY_DISPLAY.get(cat, cat)
        emoji = CATEGORY_EMOJI.get(cat, "🎵")
        bar = "█" * min(20, count // 10)
        lines.append(f"{emoji} **{label}**\n   {count} songs  {bar}")
    lines.append(f"\n**Total: {total} songs**")
    await event.respond("\n".join(lines))


# ─── Free-text search ─────────────────────────────────────────────────────────

@client.on(events.NewMessage())
async def handle_search(event):
    if event.is_group or event.is_channel:
        return
    text = event.raw_text.strip()
    if not text or text.startswith("/"):
        return

    results = search_songs(text)
    if not results:
        await event.respond(
            f"🔍 No songs found for **{text}**\n\nTry a different keyword or browse by category with /start"
        )
        return

    if len(results) == 1:
        await event.respond("🔍 **Found 1 song:**\n\n" + format_song(results[0]))
        return

    # Cache search results temporarily using inline data with query embedded
    # For multi-page search results we encode the query in callback data
    query_encoded = text[:40].replace("|", " ")  # sanitise for callback data
    page_text, buttons = paginate_song_list(results, 0, f"search|{query_encoded}")
    await event.respond(f"🔍 **Results for \"{text}\":**\n\n" + page_text, buttons=buttons)


# ─── Callback queries ─────────────────────────────────────────────────────────

@client.on(events.CallbackQuery())
async def handle_callback(event):
    data = event.data.decode("utf-8")
    parts = data.split("|")
    action = parts[0]

    # ── Category browse ──
    if action == "cat":
        cat_key = parts[1]
        page = int(parts[2])
        songs = get_songs_by_category(cat_key)
        label = CATEGORY_DISPLAY.get(cat_key, cat_key)
        emoji = CATEGORY_EMOJI.get(cat_key, "🎵")
        page_text, buttons = paginate_song_list(songs, page, f"cat|{cat_key}")
        await event.edit(f"{emoji} **{label}**\n\n" + page_text, buttons=buttons)

    # ── Search pagination ──
    elif action == "search":
        query = parts[1]
        page = int(parts[2])
        results = search_songs(query)
        page_text, buttons = paginate_song_list(results, page, f"search|{query}")
        await event.edit(f"🔍 **Results for \"{query}\":**\n\n" + page_text, buttons=buttons)

    # ── Song detail ──
    elif action == "detail":
        song_id = int(parts[1])
        back_page = int(parts[-1])
        back_context = "|".join(parts[2:-1])  # e.g. "cat|POPS＆ANIME" or "search|Ado"
        from db import get_song_by_id
        song = get_song_by_id(song_id)
        if not song:
            await event.answer("Song not found.", alert=True)
            return
        text = format_song(song)
        back_data = f"{back_context}|{back_page}"
        await event.edit(text, buttons=[[Button.inline("🔙 Back to list", data=back_data)]])

    # ── Back to categories ──
    elif action == "back_to_categories":
        total = get_song_count()
        text = (
            "👇 **Pick a category to browse:**\n"
            f"_(Total: {total} songs)_"
        )
        await event.edit(text, buttons=make_category_buttons())

    # ── Random ──
    elif action == "random":
        from db import get_random_song
        song = get_random_song()
        if not song:
            await event.answer("No songs found.", alert=True)
            return
        text = "🎲 **Random Song**\n\n" + format_song(song)
        await event.edit(
            text,
            buttons=[[Button.inline("🎲 Another random", data="random"),
                      Button.inline("🔙 Categories", data="back_to_categories")]]
        )

    await event.answer()


# ─── Block group usage ────────────────────────────────────────────────────────

@client.on(events.ChatAction())
async def block_group_adds(event):
    if event.user_added or event.user_joined:
        try:
            await client.leave_chat(event.chat_id)
            logger.info(f"Left group/channel: {event.chat_id}")
        except Exception as e:
            logger.warning(f"Could not leave chat {event.chat_id}: {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    init_db()
    await client.start(bot_token=BOT_TOKEN)
    logger.info("maimai Songs Bot started.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
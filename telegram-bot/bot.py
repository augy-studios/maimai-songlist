import os
import asyncio
import logging
import html
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
client.parse_mode = "html"

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
        f"🎵 <b>{html.escape(song['title'])}</b>",
        f"👤 {html.escape(song['artist'])}",
        f"📂 {html.escape(cat)}",
    ]

    # Standard charts
    std = []
    for diff, label in [("lev_bas", "BAS"), ("lev_adv", "ADV"), ("lev_exp", "EXP"),
                         ("lev_mas", "MAS"), ("lev_remas", "Re:MAS")]:
        if song.get(diff):
            std.append(f"{label} {html.escape(str(song[diff]))}")
    if std:
        lines.append("📊 <b>STD:</b> " + " │ ".join(std))

    # DX charts
    dx = []
    for diff, label in [("dx_lev_bas", "BAS"), ("dx_lev_adv", "ADV"), ("dx_lev_exp", "EXP"),
                         ("dx_lev_mas", "MAS"), ("dx_lev_remas", "Re:MAS")]:
        if song.get(diff):
            dx.append(f"{label} {html.escape(str(song[diff]))}")
    if dx:
        lines.append("📊 <b>DX:</b> " + " │ ".join(dx))

    # Utage (宴会場)
    if song.get("lev_utage"):
        utage_info = f"🎊 <b>UTAGE:</b> {html.escape(str(song['lev_utage']))}"
        if song.get("kanji"):
            utage_info += f"  [{html.escape(str(song['kanji']))}]"
        if song.get("comment"):
            utage_info += f"\n💬 <i>{html.escape(str(song['comment']))}</i>"
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
        lines.append(f"{i}. <b>{html.escape(s['title'])}</b> - <i>{html.escape(s['artist'])}</i>")

    text = "\n".join(lines)

    # Navigation buttons
    nav = []
    if page > 0:
        nav.append(Button.inline("◀ Prev", data=f"{context}|{page - 1}"))
    if page < total_pages - 1:
        nav.append(Button.inline("Next ▶", data=f"{context}|{page + 1}"))

    # Detail buttons - one per song on this page
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

def make_start_text() -> str:
    total = get_song_count()
    return (
        "👋 <b>Welcome to the maimai Song Browser!</b>\n\n"
        f"I have <b>{total} songs</b> in my database.\n\n"
        "<b>What I can do:</b>\n"
        "• Browse songs by category using the buttons below\n"
        "• Type any song title or artist name to search\n\n"
        "<b>Commands:</b>\n"
        "/start - Show this menu\n"
        "/random - Get a random song\n"
        "/stats - Show database statistics\n"
        "/help - Show detailed help\n\n"
        "👇 <b>Pick a category to browse:</b>"
    )


@client.on(events.NewMessage(pattern=r"^/start$"))
async def cmd_start(event):
    if event.is_group or event.is_channel:
        return
    await event.respond(make_start_text(), buttons=make_category_buttons())


# ─── /help ────────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern=r"^/help$"))
async def cmd_help(event):
    if event.is_group or event.is_channel:
        return
    text = (
        "📖 <b>How to use this bot</b>\n\n"
        "<b>Browsing:</b>\n"
        "Use /start to open the category menu. Select a category to see all songs in it. "
        "Navigate pages with the ◀ Prev / Next ▶ buttons. "
        "Tap any song title to see its full details.\n\n"
        "<b>Searching:</b>\n"
        "Just type anything - a song title, artist name, or part of either. "
        "The search is instant and matches both fields.\n"
        "<i>Example:</i> <code>bad apple</code>\n"
        "<i>Example:</i> <code>DECO*27</code>\n\n"
        "<b>Commands:</b>\n"
        "/start - Main menu with category browser\n"
        "/random - Surprise me with a random song\n"
        "/stats - Song counts by category\n"
        "/help - This message\n\n"
        "<b>Difficulty labels:</b>\n"
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
    text = "🎲 <b>Random Song</b>\n\n" + format_song(song)
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
    lines = ["📊 <b>Song Database Statistics</b>\n"]
    for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
        label = CATEGORY_DISPLAY.get(cat, cat)
        emoji = CATEGORY_EMOJI.get(cat, "🎵")
        bar = "█" * min(20, count // 10)
        lines.append(f"{emoji} <b>{html.escape(label)}</b>\n   {count} songs  {bar}")
    lines.append(f"\n<b>Total: {total} songs</b>")
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
            f"🔍 No songs found for <b>{html.escape(text)}</b>\n\nTry a different keyword or browse by category with /start"
        )
        return

    if len(results) == 1:
        await event.respond("🔍 <b>Found 1 song:</b>\n\n" + format_song(results[0]))
        return

    # Cache search results temporarily using inline data with query embedded
    # For multi-page search results we encode the query in callback data
    query_encoded = text[:40].replace("|", " ")  # sanitise for callback data
    page_text, buttons = paginate_song_list(results, 0, f"search|{query_encoded}")
    await event.respond(f"🔍 <b>Results for \"{html.escape(text)}\":</b>\n\n" + page_text, buttons=buttons)


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
        await event.edit(f"{emoji} <b>{html.escape(label)}</b>\n\n" + page_text, buttons=buttons)

    # ── Search pagination ──
    elif action == "search":
        query = parts[1]
        page = int(parts[2])
        results = search_songs(query)
        page_text, buttons = paginate_song_list(results, page, f"search|{query}")
        await event.edit(f"🔍 <b>Results for \"{html.escape(query)}\":</b>\n\n" + page_text, buttons=buttons)

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
        await event.edit(make_start_text(), buttons=make_category_buttons())

    # ── Random ──
    elif action == "random":
        from db import get_random_song
        song = get_random_song()
        if not song:
            await event.answer("No songs found.", alert=True)
            return
        text = "🎲 <b>Random Song</b>\n\n" + format_song(song)
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
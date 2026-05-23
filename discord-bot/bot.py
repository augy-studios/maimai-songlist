import os
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

from db import (
    init_db,
    get_songs_by_category,
    search_songs,
    get_song_by_id,
    get_song_count,
    get_random_song,
    get_stats,
)

# ─── Config ───────────────────────────────────────────────────────────────────

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")  # optional: instant sync to one server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

SONGS_PER_PAGE = 8
EMBED_COLOR = discord.Color.from_rgb(255, 102, 153)

CATEGORY_DISPLAY = {
    "POPS＆ANIME":         "POPS & ANIME",
    "niconico＆VOCALOID™": "niconico & VOCALOID™",
    "東方Project":          "東方Project",
    "GAME＆VARIETY":        "GAME & VARIETY",
    "maimai":               "maimai",
    "オンゲキ＆CHUNITHM":   "ONGEKI & CHUNITHM",
    "宴会場":               "宴会場",
}

CATEGORY_EMOJI = {
    "POPS＆ANIME":         "🎵",
    "niconico＆VOCALOID™": "🎤",
    "東方Project":          "🌸",
    "GAME＆VARIETY":        "🎮",
    "maimai":               "🍀",
    "オンゲキ＆CHUNITHM":   "🎯",
    "宴会場":               "🎊",
}

CATEGORY_KEYS = list(CATEGORY_DISPLAY.keys())

intents = discord.Intents.default()
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)


# ─── Embed helpers ─────────────────────────────────────────────────────────────

def make_start_embed(count: int) -> discord.Embed:
    return discord.Embed(
        title="🎵 maimai Song Browser",
        description=(
            f"**{count} songs** in the database.\n\n"
            "**Commands:**\n"
            "`/start` — This menu\n"
            "`/random` — Random song\n"
            "`/stats` — Database statistics\n"
            "`/help` — Help & usage guide\n"
            "`/search <query>` — Search by title or artist\n\n"
            "👇 **Pick a category to browse:**"
        ),
        color=EMBED_COLOR,
    )


def make_song_list_embed(songs: list, page: int, title: str) -> discord.Embed:
    total = len(songs)
    total_pages = max(1, (total + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * SONGS_PER_PAGE
    chunk = songs[start : start + SONGS_PER_PAGE]

    lines = []
    for i, s in enumerate(chunk, start=start + 1):
        artist = s.get("artist") or ""
        lines.append(f"**{i}.** {s['title']} — *{artist}*")

    embed = discord.Embed(title=title, description="\n".join(lines), color=EMBED_COLOR)
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  ·  {total} songs total")
    return embed


def make_song_detail_embed(song: dict) -> discord.Embed:
    cat_key = song.get("catcode", "")
    cat_label = CATEGORY_DISPLAY.get(cat_key, cat_key)
    cat_emoji = CATEGORY_EMOJI.get(cat_key, "🎵")

    embed = discord.Embed(title=song["title"], color=EMBED_COLOR)
    embed.add_field(name="Artist", value=song.get("artist") or "—", inline=True)
    embed.add_field(name="Category", value=f"{cat_emoji} {cat_label}", inline=True)

    std_parts = []
    for field, label in [
        ("lev_bas", "BAS"), ("lev_adv", "ADV"), ("lev_exp", "EXP"),
        ("lev_mas", "MAS"), ("lev_remas", "Re:MAS"),
    ]:
        if song.get(field):
            std_parts.append(f"`{label}` {song[field]}")
    if std_parts:
        embed.add_field(name="📊 STD Charts", value="  ".join(std_parts), inline=False)

    dx_parts = []
    for field, label in [
        ("dx_lev_bas", "BAS"), ("dx_lev_adv", "ADV"), ("dx_lev_exp", "EXP"),
        ("dx_lev_mas", "MAS"), ("dx_lev_remas", "Re:MAS"),
    ]:
        if song.get(field):
            dx_parts.append(f"`{label}` {song[field]}")
    if dx_parts:
        embed.add_field(name="📊 DX Charts", value="  ".join(dx_parts), inline=False)

    if song.get("lev_utage"):
        parts = [f"Level {song['lev_utage']}"]
        if song.get("kanji"):
            parts.append(f"[{song['kanji']}]")
        if song.get("comment"):
            parts.append(f"*{song['comment']}*")
        if song.get("buddy") == "○":
            parts.append("👥 Buddy")
        embed.add_field(name="🎊 Utage", value="  ".join(parts), inline=False)

    flags = []
    if song.get("key") == "○":
        flags.append("🔑 Key Song")
    if song.get("date") == "NEW":
        flags.append("🆕 New!")
    if flags:
        embed.add_field(name="Flags", value="  ".join(flags), inline=False)

    return embed


# ─── Views ─────────────────────────────────────────────────────────────────────

class CategorySelectView(discord.ui.View):
    """Welcome screen: category dropdown + random button."""

    def __init__(self):
        super().__init__(timeout=1800)

        options = [
            discord.SelectOption(
                label=f"{CATEGORY_EMOJI[k]} {CATEGORY_DISPLAY[k]}",
                value=k,
            )
            for k in CATEGORY_KEYS
        ]
        sel = discord.ui.Select(placeholder="Choose a category…", options=options, row=0)
        sel.callback = self._on_category
        self.add_item(sel)

        rand = discord.ui.Button(
            label="🎲 Random Song", style=discord.ButtonStyle.secondary, row=1
        )
        rand.callback = self._on_random
        self.add_item(rand)

    async def _on_category(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cat_key = interaction.data["values"][0]
        songs = await asyncio.to_thread(get_songs_by_category, cat_key)
        if not songs:
            await interaction.followup.send("No songs in this category.", ephemeral=True)
            return
        title = f"{CATEGORY_EMOJI.get(cat_key, '')} {CATEGORY_DISPLAY.get(cat_key, cat_key)}"
        embed = make_song_list_embed(songs, 0, title)
        view = SongListView(songs, 0, "cat", cat_key)
        await interaction.edit_original_response(embed=embed, view=view)

    async def _on_random(self, interaction: discord.Interaction):
        await interaction.response.defer()
        song = await asyncio.to_thread(get_random_song)
        if not song:
            await interaction.followup.send("No songs found.", ephemeral=True)
            return
        embed = make_song_detail_embed(song)
        embed.set_author(name="🎲 Random Song")
        await interaction.edit_original_response(embed=embed, view=RandomSongView())


class SongListView(discord.ui.View):
    """Paginated song list with a select-dropdown for details."""

    def __init__(self, songs: list, page: int, ctx_type: str, ctx_data: str):
        super().__init__(timeout=1800)
        self.songs = songs
        self.page = max(0, min(page, max(0, (len(songs) - 1) // SONGS_PER_PAGE)))
        self.ctx_type = ctx_type
        self.ctx_data = ctx_data
        self._total_pages = max(1, (len(songs) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE)
        self._add_items()

    def _add_items(self):
        start = self.page * SONGS_PER_PAGE
        chunk = self.songs[start : start + SONGS_PER_PAGE]

        # Row 0: navigation + back
        if self.page > 0:
            btn = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=0)
            btn.callback = self._prev
            self.add_item(btn)
        if self.page < self._total_pages - 1:
            btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
            btn.callback = self._next
            self.add_item(btn)
        back = discord.ui.Button(label="🔙 Categories", style=discord.ButtonStyle.secondary, row=0)
        back.callback = self._back_cats
        self.add_item(back)

        # Row 1: song selector
        options = [
            discord.SelectOption(
                label=s["title"][:100],
                description=(s.get("artist") or "")[:100],
                value=str(s["id"]),
            )
            for s in chunk
        ]
        sel = discord.ui.Select(
            placeholder="Select a song to view details…", options=options, row=1
        )
        sel.callback = self._on_song
        self.add_item(sel)

    def _title(self) -> str:
        if self.ctx_type == "cat":
            k = self.ctx_data
            return f"{CATEGORY_EMOJI.get(k, '')} {CATEGORY_DISPLAY.get(k, k)}"
        return f'🔍 Results for "{self.ctx_data}"'

    async def _prev(self, interaction: discord.Interaction):
        view = SongListView(self.songs, self.page - 1, self.ctx_type, self.ctx_data)
        await interaction.response.edit_message(
            embed=make_song_list_embed(self.songs, self.page - 1, self._title()), view=view
        )

    async def _next(self, interaction: discord.Interaction):
        view = SongListView(self.songs, self.page + 1, self.ctx_type, self.ctx_data)
        await interaction.response.edit_message(
            embed=make_song_list_embed(self.songs, self.page + 1, self._title()), view=view
        )

    async def _back_cats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        count = await asyncio.to_thread(get_song_count)
        await interaction.edit_original_response(
            embed=make_start_embed(count), view=CategorySelectView()
        )

    async def _on_song(self, interaction: discord.Interaction):
        await interaction.response.defer()
        song_id = int(interaction.data["values"][0])
        song = await asyncio.to_thread(get_song_by_id, song_id)
        if not song:
            await interaction.followup.send("Song not found.", ephemeral=True)
            return
        embed = make_song_detail_embed(song)
        view = SongDetailView(self.ctx_type, self.ctx_data, self.page, self.songs)
        await interaction.edit_original_response(embed=embed, view=view)


class SongDetailView(discord.ui.View):
    """Song detail screen with back-to-list, categories, and random buttons."""

    def __init__(
        self,
        ctx_type: str,
        ctx_data: str,
        page: int,
        songs: list | None = None,
    ):
        super().__init__(timeout=1800)
        self.ctx_type = ctx_type
        self.ctx_data = ctx_data
        self.page = page
        self._songs = songs  # cached to skip re-fetch on Back

        btn = discord.ui.Button(label="🔙 Back to list", style=discord.ButtonStyle.secondary, row=0)
        btn.callback = self._back_list
        self.add_item(btn)

        btn = discord.ui.Button(label="🏠 Categories", style=discord.ButtonStyle.secondary, row=0)
        btn.callback = self._back_cats
        self.add_item(btn)

        btn = discord.ui.Button(label="🎲 Random", style=discord.ButtonStyle.secondary, row=0)
        btn.callback = self._random
        self.add_item(btn)

    async def _back_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        songs = self._songs
        if songs is None:
            if self.ctx_type == "cat":
                songs = await asyncio.to_thread(get_songs_by_category, self.ctx_data)
            else:
                songs = await asyncio.to_thread(search_songs, self.ctx_data)
        if self.ctx_type == "cat":
            k = self.ctx_data
            title = f"{CATEGORY_EMOJI.get(k, '')} {CATEGORY_DISPLAY.get(k, k)}"
        else:
            title = f'🔍 Results for "{self.ctx_data}"'
        embed = make_song_list_embed(songs, self.page, title)
        view = SongListView(songs, self.page, self.ctx_type, self.ctx_data)
        await interaction.edit_original_response(embed=embed, view=view)

    async def _back_cats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        count = await asyncio.to_thread(get_song_count)
        await interaction.edit_original_response(
            embed=make_start_embed(count), view=CategorySelectView()
        )

    async def _random(self, interaction: discord.Interaction):
        await interaction.response.defer()
        song = await asyncio.to_thread(get_random_song)
        if not song:
            await interaction.followup.send("No songs found.", ephemeral=True)
            return
        embed = make_song_detail_embed(song)
        embed.set_author(name="🎲 Random Song")
        await interaction.edit_original_response(embed=embed, view=RandomSongView())


class RandomSongView(discord.ui.View):
    """Random song screen with another-random and categories buttons."""

    def __init__(self):
        super().__init__(timeout=1800)

        btn = discord.ui.Button(
            label="🎲 Another Random", style=discord.ButtonStyle.secondary, row=0
        )
        btn.callback = self._random
        self.add_item(btn)

        btn = discord.ui.Button(
            label="🏠 Categories", style=discord.ButtonStyle.secondary, row=0
        )
        btn.callback = self._back_cats
        self.add_item(btn)

    async def _random(self, interaction: discord.Interaction):
        await interaction.response.defer()
        song = await asyncio.to_thread(get_random_song)
        if not song:
            await interaction.followup.send("No songs found.", ephemeral=True)
            return
        embed = make_song_detail_embed(song)
        embed.set_author(name="🎲 Random Song")
        await interaction.edit_original_response(embed=embed, view=RandomSongView())

    async def _back_cats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        count = await asyncio.to_thread(get_song_count)
        await interaction.edit_original_response(
            embed=make_start_embed(count), view=CategorySelectView()
        )


# ─── Slash commands ────────────────────────────────────────────────────────────

@bot.tree.command(name="start", description="Show the main menu with category browser")
async def cmd_start(interaction: discord.Interaction):
    await interaction.response.defer()
    count = await asyncio.to_thread(get_song_count)
    await interaction.followup.send(embed=make_start_embed(count), view=CategorySelectView())


@bot.tree.command(name="help", description="Show detailed help and usage guide")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 How to use this bot",
        color=EMBED_COLOR,
        description=(
            "**Browsing:**\n"
            "Use `/start` to open the category menu. Pick a category from the dropdown "
            "to see all songs. Navigate pages with **◀ Prev** / **Next ▶**, then select "
            "a song from the dropdown to view its full details.\n\n"
            "**Searching:**\n"
            "Use `/search <query>` to search by song title or artist. "
            "Partial, case-insensitive matches are supported.\n"
            "*Example:* `/search bad apple`  ·  `/search DECO*27`\n\n"
            "**Commands:**\n"
            "`/start` — Main menu with category browser\n"
            "`/random` — Get a random song\n"
            "`/stats` — Song counts by category\n"
            "`/search <query>` — Search by title or artist\n"
            "`/help` — This message\n\n"
            "**Difficulty labels:**\n"
            "`BAS` Basic  ·  `ADV` Advanced  ·  `EXP` Expert\n"
            "`MAS` Master  ·  `Re:MAS` Re:Master\n"
            "**STD** = Standard charts  ·  **DX** = Deluxe charts"
        ),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="random", description="Get a random maimai song")
async def cmd_random(interaction: discord.Interaction):
    await interaction.response.defer()
    song = await asyncio.to_thread(get_random_song)
    if not song:
        await interaction.followup.send("No songs found in the database.")
        return
    embed = make_song_detail_embed(song)
    embed.set_author(name="🎲 Random Song")
    await interaction.followup.send(embed=embed, view=RandomSongView())


@bot.tree.command(name="stats", description="Show song database statistics by category")
async def cmd_stats(interaction: discord.Interaction):
    await interaction.response.defer()
    stats = await asyncio.to_thread(get_stats)
    total = sum(stats.values())

    lines = []
    for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
        label = CATEGORY_DISPLAY.get(cat, cat)
        emoji = CATEGORY_EMOJI.get(cat, "🎵")
        bar = "█" * min(15, count // 10)
        lines.append(f"{emoji} **{label}** — {count}  {bar}")

    embed = discord.Embed(
        title="📊 Song Database Statistics",
        description="\n".join(lines) + f"\n\n**Total: {total} songs**",
        color=EMBED_COLOR,
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="search", description="Search for songs by title or artist")
@app_commands.describe(query="Song title or artist name to search for")
async def cmd_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    results = await asyncio.to_thread(search_songs, query)

    if not results:
        embed = discord.Embed(
            description=(
                f"🔍 No songs found for **{discord.utils.escape_markdown(query)}**\n\n"
                "Try a different keyword or browse by category with `/start`."
            ),
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)
        return

    if len(results) == 1:
        embed = make_song_detail_embed(results[0])
        embed.set_author(name=f'🔍 1 result for "{query}"')
        await interaction.followup.send(
            embed=embed, view=SongDetailView("search", query, 0, results)
        )
        return

    title = f'🔍 Results for "{query}"'
    embed = make_song_list_embed(results, 0, title)
    view = SongListView(results, 0, "search", query)
    await interaction.followup.send(embed=embed, view=view)


# ─── Bot events ───────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        logger.info(f"Slash commands synced to guild {GUILD_ID}.")
    else:
        await bot.tree.sync()
        logger.info("Slash commands synced globally (may take up to 1 hour to propagate).")


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    init_db()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

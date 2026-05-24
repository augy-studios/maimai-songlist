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
    save_active_view,
    load_all_active_views,
)

# ─── Config

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")  # optional: guild-only sync

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


# ─── Embed helpers

def make_start_embed(count: int) -> discord.Embed:
    return discord.Embed(
        title="🎵 maimai Song Browser",
        description=(
            f"**{count} songs** in the database.\n\n"
            "**Commands:**\n"
            "`/start` - This menu\n"
            "`/random` - Random song\n"
            "`/stats` - Database statistics\n"
            "`/help` - Help & usage guide\n"
            "`/search <query>` - Search by title or artist\n\n"
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
        lines.append(f"**{i}.** {s['title']} - *{artist}*")

    embed = discord.Embed(title=title, description="\n".join(lines), color=EMBED_COLOR)
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  ·  {total} songs total")
    return embed


def make_song_detail_embed(song: dict) -> discord.Embed:
    cat_key = song.get("catcode", "")
    cat_label = CATEGORY_DISPLAY.get(cat_key, cat_key)
    cat_emoji = CATEGORY_EMOJI.get(cat_key, "🎵")

    embed = discord.Embed(title=song["title"], color=EMBED_COLOR)
    embed.add_field(name="Artist", value=song.get("artist") or "-", inline=True)
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


# ─── Views

class BaseView(discord.ui.View):
    def __init__(self, **kwargs):
        kwargs.setdefault("timeout", None)
        super().__init__(**kwargs)
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    def _view_type_and_state(self) -> tuple[str, dict]:
        raise NotImplementedError


class CategorySelectView(BaseView):
    """Welcome screen with category picker."""

    def __init__(self):
        super().__init__()

        options = [
            discord.SelectOption(
                label=f"{CATEGORY_EMOJI[k]} {CATEGORY_DISPLAY[k]}",
                value=k,
            )
            for k in CATEGORY_KEYS
        ]
        sel = discord.ui.Select(
            placeholder="Choose a category…", options=options, row=0,
            custom_id="mai_cat_sel",
        )
        sel.callback = self._on_category
        self.add_item(sel)

        rand = discord.ui.Button(
            label="🎲 Random Song", style=discord.ButtonStyle.secondary, row=1,
            custom_id="mai_cat_rand",
        )
        rand.callback = self._on_random
        self.add_item(rand)

    def _view_type_and_state(self):
        return "category", {}

    async def _on_category(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cat_key = interaction.data["values"][0]
        songs = await asyncio.to_thread(get_songs_by_category, cat_key)
        if not songs:
            await interaction.followup.send("No songs in this category.", ephemeral=False)
            return
        title = f"{CATEGORY_EMOJI.get(cat_key, '')} {CATEGORY_DISPLAY.get(cat_key, cat_key)}"
        embed = make_song_list_embed(songs, 0, title)
        view = SongListView(songs, 0, "cat", cat_key)
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        await _persist(view, msg.id)

    async def _on_random(self, interaction: discord.Interaction):
        await interaction.response.defer()
        song = await asyncio.to_thread(get_random_song)
        if not song:
            await interaction.followup.send("No songs found.", ephemeral=False)
            return
        embed = make_song_detail_embed(song)
        embed.set_author(name="🎲 Random Song")
        view = RandomSongView()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        await _persist(view, msg.id)


class SongListView(BaseView):
    """Paginated song list."""

    def __init__(self, songs: list, page: int, ctx_type: str, ctx_data: str):
        super().__init__()
        self.songs = songs
        self.ctx_type = ctx_type
        self.ctx_data = ctx_data
        total = len(songs)
        self._total_pages = max(1, (total + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE)
        self.page = max(0, min(page, self._total_pages - 1))
        start = self.page * SONGS_PER_PAGE
        self._page_chunk = songs[start : start + SONGS_PER_PAGE]
        self._add_items()

    @classmethod
    def restored(cls, state: dict) -> "SongListView":
        """Restore from SQLite (no full song list)."""
        obj = cls.__new__(cls)
        discord.ui.View.__init__(obj, timeout=None)
        obj.message = None
        obj.songs = []
        obj.ctx_type = state["ctx_type"]
        obj.ctx_data = state["ctx_data"]
        obj.page = state["page"]
        obj._total_pages = state["total_pages"]
        obj._page_chunk = state["page_chunk"]
        obj._add_items()
        return obj

    def _view_type_and_state(self):
        return "songlist", {
            "ctx_type": self.ctx_type,
            "ctx_data": self.ctx_data,
            "page": self.page,
            "total_pages": self._total_pages,
            "page_chunk": [
                {"id": s["id"], "title": s["title"], "artist": s.get("artist") or ""}
                for s in self._page_chunk
            ],
        }

    def _add_items(self):
        # prev/next always present; disabled when inapplicable
        prev = discord.ui.Button(
            label="◀ Prev", style=discord.ButtonStyle.secondary, row=0,
            custom_id="mai_sl_prev", disabled=(self.page == 0),
        )
        prev.callback = self._prev
        self.add_item(prev)

        nxt = discord.ui.Button(
            label="Next ▶", style=discord.ButtonStyle.secondary, row=0,
            custom_id="mai_sl_next", disabled=(self.page >= self._total_pages - 1),
        )
        nxt.callback = self._next
        self.add_item(nxt)

        back = discord.ui.Button(
            label="🔙 Categories", style=discord.ButtonStyle.secondary, row=0,
            custom_id="mai_sl_back",
        )
        back.callback = self._back_cats
        self.add_item(back)

        # Row 1: song selector
        options = [
            discord.SelectOption(
                label=s["title"][:100],
                description=(s.get("artist") or "")[:100],
                value=str(s["id"]),
            )
            for s in self._page_chunk
        ]
        sel = discord.ui.Select(
            placeholder="Select a song to view details…", options=options, row=1,
            custom_id="mai_sl_sel",
        )
        sel.callback = self._on_song
        self.add_item(sel)

    def _title(self) -> str:
        if self.ctx_type == "cat":
            k = self.ctx_data
            return f"{CATEGORY_EMOJI.get(k, '')} {CATEGORY_DISPLAY.get(k, k)}"
        return f'🔍 Results for "{self.ctx_data}"'

    async def _ensure_songs(self) -> list[dict]:
        """Lazy-load songs (after SQLite restore)."""
        if not self.songs:
            if self.ctx_type == "cat":
                self.songs = await asyncio.to_thread(get_songs_by_category, self.ctx_data)
            else:
                self.songs = await asyncio.to_thread(search_songs, self.ctx_data)
            self._total_pages = max(1, (len(self.songs) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE)
        return self.songs

    async def _prev(self, interaction: discord.Interaction):
        songs = await self._ensure_songs()
        view = SongListView(songs, self.page - 1, self.ctx_type, self.ctx_data)
        view.message = interaction.message
        await _persist(view, interaction.message.id)
        await interaction.response.edit_message(
            embed=make_song_list_embed(songs, self.page - 1, self._title()), view=view
        )

    async def _next(self, interaction: discord.Interaction):
        songs = await self._ensure_songs()
        view = SongListView(songs, self.page + 1, self.ctx_type, self.ctx_data)
        view.message = interaction.message
        await _persist(view, interaction.message.id)
        await interaction.response.edit_message(
            embed=make_song_list_embed(songs, self.page + 1, self._title()), view=view
        )

    async def _back_cats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        count = await asyncio.to_thread(get_song_count)
        view = CategorySelectView()
        msg = await interaction.edit_original_response(embed=make_start_embed(count), view=view)
        view.message = msg
        await _persist(view, msg.id)

    async def _on_song(self, interaction: discord.Interaction):
        await interaction.response.defer()
        song_id = int(interaction.data["values"][0])
        song = await asyncio.to_thread(get_song_by_id, song_id)
        if not song:
            await interaction.followup.send("Song not found.", ephemeral=False)
            return
        embed = make_song_detail_embed(song)
        view = SongDetailView(self.ctx_type, self.ctx_data, self.page, self.songs or None)
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        await _persist(view, msg.id)


class SongDetailView(BaseView):
    """Song detail screen."""

    def __init__(
        self,
        ctx_type: str,
        ctx_data: str,
        page: int,
        songs: list | None = None,
    ):
        super().__init__()
        self.ctx_type = ctx_type
        self.ctx_data = ctx_data
        self.page = page
        self._songs = songs  # cache to avoid re-fetch

        btn = discord.ui.Button(
            label="🔙 Back to list", style=discord.ButtonStyle.secondary, row=0,
            custom_id="mai_sd_back",
        )
        btn.callback = self._back_list
        self.add_item(btn)

        btn = discord.ui.Button(
            label="🏠 Categories", style=discord.ButtonStyle.secondary, row=0,
            custom_id="mai_sd_cats",
        )
        btn.callback = self._back_cats
        self.add_item(btn)

        btn = discord.ui.Button(
            label="🎲 Random", style=discord.ButtonStyle.secondary, row=0,
            custom_id="mai_sd_rand",
        )
        btn.callback = self._random
        self.add_item(btn)

    def _view_type_and_state(self):
        return "songdetail", {
            "ctx_type": self.ctx_type,
            "ctx_data": self.ctx_data,
            "page": self.page,
        }

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
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        await _persist(view, msg.id)

    async def _back_cats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        count = await asyncio.to_thread(get_song_count)
        view = CategorySelectView()
        msg = await interaction.edit_original_response(embed=make_start_embed(count), view=view)
        view.message = msg
        await _persist(view, msg.id)

    async def _random(self, interaction: discord.Interaction):
        await interaction.response.defer()
        song = await asyncio.to_thread(get_random_song)
        if not song:
            await interaction.followup.send("No songs found.", ephemeral=False)
            return
        embed = make_song_detail_embed(song)
        embed.set_author(name="🎲 Random Song")
        view = RandomSongView()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        await _persist(view, msg.id)


class RandomSongView(BaseView):
    """Random song screen."""

    def __init__(self):
        super().__init__()

        btn = discord.ui.Button(
            label="🎲 Another Random", style=discord.ButtonStyle.secondary, row=0,
            custom_id="mai_rv_rand",
        )
        btn.callback = self._random
        self.add_item(btn)

        btn = discord.ui.Button(
            label="🏠 Categories", style=discord.ButtonStyle.secondary, row=0,
            custom_id="mai_rv_cats",
        )
        btn.callback = self._back_cats
        self.add_item(btn)

    def _view_type_and_state(self):
        return "random", {}

    async def _random(self, interaction: discord.Interaction):
        await interaction.response.defer()
        song = await asyncio.to_thread(get_random_song)
        if not song:
            await interaction.followup.send("No songs found.", ephemeral=False)
            return
        embed = make_song_detail_embed(song)
        embed.set_author(name="🎲 Random Song")
        view = RandomSongView()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        await _persist(view, msg.id)

    async def _back_cats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        count = await asyncio.to_thread(get_song_count)
        view = CategorySelectView()
        msg = await interaction.edit_original_response(embed=make_start_embed(count), view=view)
        view.message = msg
        await _persist(view, msg.id)


# ─── Persistence helpers

async def _persist(view: BaseView, message_id: int) -> None:
    """Persist view state and re-register."""
    vtype, vstate = view._view_type_and_state()
    await asyncio.to_thread(save_active_view, message_id, vtype, vstate)
    bot.add_view(view, message_id=message_id)


def _reconstruct_view(view_type: str, state: dict) -> BaseView | None:
    if view_type == "category":
        return CategorySelectView()
    if view_type == "random":
        return RandomSongView()
    if view_type == "songlist":
        return SongListView.restored(state)
    if view_type == "songdetail":
        return SongDetailView(state["ctx_type"], state["ctx_data"], state["page"])
    return None


# ─── Slash commands

@bot.tree.command(name="start", description="Show the main menu with category browser")
async def cmd_start(interaction: discord.Interaction):
    await interaction.response.defer()
    count = await asyncio.to_thread(get_song_count)
    view = CategorySelectView()
    msg = await interaction.followup.send(embed=make_start_embed(count), view=view)
    view.message = msg
    await _persist(view, msg.id)


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
            "`/start` - Main menu with category browser\n"
            "`/random` - Get a random song\n"
            "`/stats` - Song counts by category\n"
            "`/search <query>` - Search by title or artist\n"
            "`/help` - This message\n\n"
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
    view = RandomSongView()
    msg = await interaction.followup.send(embed=embed, view=view)
    view.message = msg
    await _persist(view, msg.id)


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
        lines.append(f"{emoji} **{label}** - {count}  {bar}")

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
        view = SongDetailView("search", query, 0, results)
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg
        await _persist(view, msg.id)
        return

    title = f'🔍 Results for "{query}"'
    embed = make_song_list_embed(results, 0, title)
    view = SongListView(results, 0, "search", query)
    msg = await interaction.followup.send(embed=embed, view=view)
    view.message = msg
    await _persist(view, msg.id)


# ─── Bot events

async def update_presence():
    count = len(bot.guilds)
    await bot.change_presence(
        activity=discord.Game(name=f"maimai with {count} guild{'s' if count != 1 else ''}")
    )


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    rows = await asyncio.to_thread(load_all_active_views)
    restored = 0
    for message_id, view_type, state in rows:
        view = _reconstruct_view(view_type, state)
        if view:
            bot.add_view(view, message_id=message_id)
            restored += 1
    logger.info(f"Restored {restored} persistent view(s) from SQLite.")

    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        logger.info(f"Slash commands synced to guild {GUILD_ID} (instant).")
    await bot.tree.sync()
    logger.info("Slash commands synced globally (DMs supported; up to 1 hour to propagate in new servers).")
    await update_presence()


@bot.event
async def on_guild_join(guild: discord.Guild):
    await update_presence()


@bot.event
async def on_guild_remove(guild: discord.Guild):
    await update_presence()


# ─── Entry point

async def main():
    init_db()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

# 🎵 maimai Songs Bot

A Telegram bot for browsing and searching the maimai DX song list. Browse by category or search by song title / artist name. Runs in your DMs only — cannot be added to groups.

---

## Features

- **Category browser** — 8 categories with paginated song lists
- **Song details** — full chart info (STD & DX difficulties, Re:Master, Utage)
- **Free-text search** — type any title or artist at any time, no command needed
- **Random song** — `/random` for a surprise pick
- **Stats** — `/stats` shows song counts per category
- **DM-only** — bot automatically leaves any group it gets added to

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Open the main menu with category buttons |
| `/random` | Get a random song |
| `/stats` | Song counts by category |
| `/help` | Detailed usage instructions |

You can also **type anything** (no command needed) to search by song title or artist name.

---

## Prerequisites

- Python 3.11+
- A Telegram account (to get API credentials)
- A bot token from @BotFather
- Your `maimai_songlist` table populated in Supabase

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/maimai-songs-bot.git
cd maimai-songs-bot
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
nano .env
```

Fill in:

| Variable | Where to get it |
|----------|----------------|
| `API_ID` | https://my.telegram.org/apps |
| `API_HASH` | https://my.telegram.org/apps |
| `BOT_TOKEN` | @BotFather on Telegram |
| `SUPABASE_URL` | Supabase project → Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase project → Settings → API (service role key) |

### 4. Run the bot

```bash
python bot.py
```

On first run, Telethon will create a `maimai_bot.session` file. This is normal.

---

## Running on a VPS with tmux

### Start a new tmux session

```bash
tmux new-session -s maimai-bot
```

### Inside the session, activate venv and start the bot

```bash
cd ~/maimai-songs-bot
source venv/bin/activate
python bot.py
```

### Detach from the session (bot keeps running)

```bash
Ctrl+B, then D
```

### Re-attach later

```bash
tmux attach-session -t maimai-bot
```

### Stop the bot

Re-attach to the session, then press `Ctrl+C`.

---

## BotFather Setup

See the **BotFather Setup Guide** section at the bottom of this README, or follow the in-repo guide.

---

## Project Structure

```bash
maimai-songs-bot/
├── bot.py          # Main bot logic, handlers, and formatting
├── db.py           # Database layer (Supabase queries + SQLite init)
├── requirements.txt
├── .env.example    # Template for environment variables
├── .env            # Your actual secrets (gitignored)
├── .gitignore
└── README.md
```

---

## BotFather Setup Guide

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Enter a display name, e.g. `maimai Songs`
4. Enter a username ending in `bot`, e.g. `maimaisongsbot`
5. BotFather will give you a **token** — copy it into your `.env` as `BOT_TOKEN`

### Recommended BotFather settings

After creating the bot, run these commands with BotFather:

**Disable group joining:**

```bash
/setjoingroups
→ select your bot
→ Disable
```

**Set commands list** (so users see them in the menu):

```bash
/setcommands
→ select your bot
→ paste the following:
```

```bash
start - Browse songs by category
random - Get a random song
stats - Song counts by category
help - How to use this bot
```

**Set description** (shown before the user starts the bot):

```bash
/setdescription
→ Browse and search the full maimai DX song list. Pick a category or just type a song title or artist name.
```

**Set about text** (shown on the bot's profile):

```bash
/setabouttext
→ maimai DX song browser — search by title or artist, or browse by category.
```

---

## Notes

- The `maimai_bot.session` file stores your Telethon session. Keep it safe and never commit it.
- The `bot_state.db` SQLite file is used for local bot state and is also gitignored.
- The bot uses the Supabase anon key for read-only queries, which is safe to use in production.
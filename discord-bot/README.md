# maimai Song Browser - Discord Bot

A Discord slash-commands bot for browsing the maimai DX song list, backed by Supabase.

## Features

| Command | Description |
|---------|-------------|
| `/start` | Main menu with category browser and interactive dropdowns |
| `/search <query>` | Search songs by title or artist name |
| `/random` | Get a random song |
| `/stats` | Song counts by category |
| `/help` | Usage guide and difficulty label reference |

All song lists are paginated (8 per page). Selecting a song from the dropdown shows full chart details including STD/DX difficulties, Utage info, and flags.

---

## Prerequisites

- Python 3.11+
- A [Discord application](https://discord.com/developers/applications) with a bot token
- A Supabase project with the `maimai_songlist` table populated

---

## Setup

### 1. Clone and navigate

```bash
git clone https://github.com/your-username/maimai-songlist.git
cd maimai-songlist/discord-bot
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
nano .env
```

Fill in:

| Variable | Where to find it |
|----------|-----------------|
| `DISCORD_BOT_TOKEN` | Discord Developer Portal → Your App → Bot → Token |
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase Dashboard → Project Settings → API → `service_role` key |
| `DISCORD_GUILD_ID` | *(Optional)* Right-click your server in Discord → Copy Server ID (enable Developer Mode first). Set this for instant slash command sync during development; leave blank for global sync. |

---

## Creating the Discord Bot

1. Go to <https://discord.com/developers/applications> and click **New Application**.
2. Under **Bot**, click **Add Bot**. Copy the token into `.env`.
3. Under **Bot → Privileged Gateway Intents**, no extra intents are needed.
4. Under **OAuth2 → URL Generator**, select scopes: `bot` + `applications.commands`.  
   Bot permissions needed: **Send Messages**, **Embed Links**, **Read Message History**.
5. Open the generated URL to invite the bot to your server.

---

## Running

### Directly

```bash
source .venv/bin/activate
python3 bot.py
```

### With tmux (recommended for VPS)

```bash
# Start a new session
tmux new-session -s discord-bot

# Inside tmux:
cd ~/maimai-songlist/discord-bot
source .venv/bin/activate
python3 bot.py

# Detach: Ctrl+B then D
# Reattach later:
tmux attach -t discord-bot
```

### Auto-restart on crash with a simple loop

```bash
# Inside your tmux session:
while true; do python3 bot.py; echo "Restarting in 5s…"; sleep 5; done
```

---

## Slash command sync

On first start the bot syncs slash commands automatically:

- **With `DISCORD_GUILD_ID` set** - commands appear in that server **instantly**.
- **Without `DISCORD_GUILD_ID`** - global sync, takes **up to 1 hour** to propagate everywhere.

For development, set `DISCORD_GUILD_ID` to your test server. Remove it (or clear the value) before deploying to production.

---

## Project structure

```
discord-bot/
├── bot.py            # Bot logic, slash commands, interactive views
├── db.py             # Supabase + SQLite database layer
├── requirements.txt
├── .env.example      # Template - copy to .env and fill in secrets
├── .gitignore
└── README.md
```

---

## Difficulty labels

| Label | Meaning |
|-------|---------|
| BAS | Basic |
| ADV | Advanced |
| EXP | Expert |
| MAS | Master |
| Re:MAS | Re:Master |
| STD | Standard chart type |
| DX | Deluxe chart type |

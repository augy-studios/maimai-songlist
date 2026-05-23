# maimai Song Browser Bots

Two bots for browsing the maimai DX song list, both backed by the same Supabase table.

| Directory                        | Platform                            | Live Bot                                                                              | README                           |
|----------------------------------|-------------------------------------|---------------------------------------------------------------------------------------|----------------------------------|
| [`telegram-bot/`](telegram-bot/) | Telegram (Telethon)                 | [@maimai_songs_bot](https://t.me/maimai_songs_bot)                                    | [README](telegram-bot/README.md) |
| [`discord-bot/`](discord-bot/)   | Discord (discord.py slash commands) | [Add to server](https://discord.com/oauth2/authorize?client_id=1507762344023818240)   | [README](discord-bot/README.md)  |

Each bot has its own `requirements.txt`, `.env.example`, and setup instructions. See the individual READMEs for deployment details.

All database info is sourced from [the official maimai DX songs API](https://maimai.sega.com/assets/data/maimai_songs.json).

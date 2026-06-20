# TGAS Discord Bot

A Discord bot for managing **The Gambling Addicts (TGAS)** Wynncraft guild statistics, raid tracking, tome distribution, and Annihilation party organization. The bot integrates with the Wynncraft API to provide real-time guild data and automated tracking.

## Features

### Guild Annihilation Parties
- Automated signup system for Guild Annihilation events via Discord buttons
- Players can specify their preferred server region (EU/NA/AS), weapon, and playstyle
- Live-updating party dashboard showing parties, unconfirmed members, and outsiders
- `/setup_anni_parties` — Configure the channel, ping role, and minimum role requirement
- `/start-anni-party-signups` — Start a new Annihilation signup session

### Wynncraft API Integration
- Queries the [Wynncraft API v3](https://docs.wynncraft.com/) every 2 minutes for up-to-date guild member data
- Tracks member playtime, contribution, guild rank, weekly completion, and raid completions
- `/get_user_playtime_graph` — Generate a playtime history chart for any guild member
  This does not work yet.
- Automated playtime snapshots stored every 2 hours

### Tome Requesting System
- Interactive button-based system for requesting guild tomes
- Configurable cooldown period and required weekly streak
- Live-updating overview of who is on cooldown and who still needs to receive their tome
- `/setup_tomes` — Configure cooldown (days) and required weekly streak
- `/send_tome_requests_message` — Send the tome request dashboard to the current channel
- `/reward_tomes` — Modal interface for marking tomes as rewarded in-game

### Guild Raid Tracking
WIP
- Automatically detects when guild members complete guild raids (NotG, NoL, TCC, TNA, WTP)
- Tracks progress toward earning aspects (2 guild raids = 1 aspect)
- Sends real-time Discord embeds when raids are completed, showing which players ran which raid
- `/set_graid_channel` — Set the channel for raid completion announcements
- `/set_aspects_rewarded` — Modal interface for marking aspects as rewarded in-game

### Random Gambling Messages
- Responds to gambling-related keywords (`gamble`, `roll`, `luck`, etc.) with random encouragement messages
- Lightweight, no configuration needed

## Commands

| Command | Description |
|---|---|
| `/setup_anni_parties <channel> <role_to_mention> <minimum_needed_role>` | Configure Annihilation party system |
| `/start-anni-party-signups` | Start a new Annihilation signup session |
| `/get_user_playtime_graph <member>` | View playtime history chart |
| `/setup_tomes <cooldown> <required_weekly_streak>` | Configure tome request settings |
| `/send_tome_requests_message` | Send tome request dashboard |
| `/reward_tomes` | Mark tomes as rewarded |
| `/set_graid_channel <channel>` | Set raid tracking announcement channel |
| `/set_aspects_rewarded` | Mark aspects as rewarded |

## Project Structure

```
├── main.py                     # Bot entry point
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker build configuration
├── INSTALL.md                  # Build & deployment instructions
├── cogs/
│   ├── anni_party.py           # Annihilation party management
│   ├── database.py             # Database abstractions (MetaTable, UpdatingTable, TrackingTable)
│   ├── random_gambling_messages.py  # Gambling encouragement responses
│   └── api_depending/
│       ├── api_queries.py      # Wynncraft API polling, playtime tracking, chart generation
│       ├── tome_requesting.py  # Guild tome request system
│       └── graid_tracking.py   # Guild raid completion tracking & aspect rewards
├── utils/
│   ├── added_exceptions.py     # Custom exception classes
│   ├── discordutils.py         # Shared Discord helper functions
│   └── general_classes.py      # APIMember data class
├── data/                       # Runtime data (fonts, etc.)
├── persistent_data/            # SQLite databases (persisted across restarts)
└── temp_data/                  # Temporary files (generated charts, etc.)
```

## Tech Stack

- **Python 3.12+**
- **[discord.py](https://github.com/Rapptz/discord.py) 2.7.1** — Discord API wrapper with app_command (slash command) support
- **matplotlib / pillow** — Chart and image generation
- **SQLite** — Local database for persistent data storage
- **requests** — Wynncraft API communication

## Getting Started

1. Clone the repository:
   ```
   git clone https://github.com/JacobsPieter/TGAS-bot
   cd TGAS-bot
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory:
   ```
   BOT_TOKEN=your_discord_bot_token
   WYNN_API_TOKEN=your_wynncraft_api_token
   ```

4. Run the bot:
   ```
   python main.py
   ```

For building an executable or deployment, see [INSTALL.md](INSTALL.md).

## Configuration

The bot stores all configuration and tracking data in SQLite databases under `persistent_data/`. No manual configuration is needed beyond setting up Discord slash commands in server settings (see INSTALL.md) and running the setup commands.

## License

This project is maintained by Pieter Jacobs for The Gambling Addicts.
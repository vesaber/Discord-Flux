# Discord-Flux
OOOOOOOOOye like bridge between Discord and Fluxer.
written in Python.

# This project is not actively being worked, I instead suggest [Fluxcord](https://git.gay/Fluxcord/core)

## Requirements
```
  - Python 3.10 or higher
  - uv Python Package Manager
  - Discord Bot
  - Fluxer Bot
```

## Setup

### Clone and sync the Project
```
# Clone the project
1. git clone https://github.com/vesaber/Discord-Flux.git

# Install uv
2. curl -LsSf https://astral.sh/uv/install.sh | sh # For Linux
# or
2. powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" # For Windows

# Install dependencies
3. uv sync
```

### Create the `.env` file
```
discordtoken = "<discord bot token>"
fluxertoken = "<fluxer bot token>"
commandprefix = "!"
```

### Bot Permissions

When Creating a bot on Fluxer or Discord, you would need some specific OAuth2 URL permissions, so the expected server doesn't get nuked or bombarded with @everyone pings.

If there's a chance, you don't even know how to create a bot, I suggest watching the first 7 minutes of [this video](https://www.youtube.com/watch?v=CHbN_gB30Tw).
The Process is pretty similar on Fluxer, but the bot creation page is located in the `User Settings` all the way at the bottom. And so is the OAuth2 URL generator.

needed OAuth2 permissions for the bot to work:
```
- bot
  - View Channel
  - Attach Files (now implemented..!)
  - Use External Emojis
  - Send Messages
  - Read Message History
  - Use External Stickers
  - Manage Webhooks (important)
  - Embed Links
  - Add Reaction
```

## Usage

### Starting the Bot
```
uv run discord-flux.py
```

### Commands

#### bridge
Bridges a channel
```
# Works only on discord
!bridge <fluxer channel id>
```

#### unbridge
Unbridges the channel it's sent in
```
# Works only on discord
!unbridge
```

# Roadmap

```
  - Sticker and Emoji support
  - Make this more accessible for self hosted instances
  - Docker image
  - Reactions
  - After I finish the Fluxer Rust API Wrapper I will be rewriting this in the rust language
  - Multi-Channel support for big servers, maybe even automatic server building with permissions
```

# Discord-Flux
OOOOOOOOOye like bridge between Discord and Fluxer.
written in Python.

## Setup
```bash
python3 -m venv .venv
pip install -r requirements.txt
```

create `.env` file:
```
discordtoken = "<discord bot token>"
fluxertoken = "<fluxer bot token>"
commandprefix = "!"
```

## Usage
Invite both your Fluxer Bot and Discord Bot to their designed servers. Then run specified command.

```bash
# Linux
source .venv/bin/activate
python discord-flux.py

# Windows
.venv\Scripts\activate
python discord-flux.py
```

## Commands

`bridge`
### Example
```
# Run on the Discord Server
!bridge <fluxer channel id>
```
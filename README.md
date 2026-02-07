# web-status

A Telegram bot that monitors a list of websites per chat. Each chat has its own list; the bot runs scheduled HTTP checks and notifies only when something is down.

## Requirements

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.

2. In the project root, create a `.env` file:

   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```

   Alternatively you can set the `BOT_TOKEN` environment variable.

## Run

```bash
uv run main.py
```

## Commands

| Command | Description |
|--------|-------------|
| `/start` | Show welcome and command list |
| `/add <url>` | Add a website to this chat’s list |
| `/remove <url>` | Remove a website from this chat’s list |
| `/list` | Show this chat’s websites |
| `/check` | Check all websites now and reply with full results (OK + errors) |

URLs are normalized (e.g. `example.com` → `http://example.com`).

## Scheduled checks

- Runs every **15 minutes** (at :00, :15, :30, :45 UTC).
- For each chat that has at least one site, the bot runs a check.
- **Only errors are reported:** if any site is down or unreachable, the bot sends one message with the failing URLs. If everything is OK, it sends nothing.

## Data

Site lists are stored in `data.json` in the project root (per-chat under a `chats` key). Keep this file safe if you rely on it.
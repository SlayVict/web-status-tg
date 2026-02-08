from __future__ import annotations

import os

from dotenv import load_dotenv

from src.bot import create_bot, setup_commands_and_scheduler


load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set TELEGRAM_BOT_TOKEN or BOT_TOKEN in your environment/.env file.")


def main() -> None:
    api, bot = create_bot(TOKEN)
    bot.loop_wrapper.add_task(setup_commands_and_scheduler(api))
    bot.run_forever()


if __name__ == "__main__":
    main()

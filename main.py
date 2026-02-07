from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from src.ping import UrlStatus, check_urls
from src.storage import (
    add_site,
    get_chat_ids_with_sites,
    get_sites,
    remove_site,
)

from telegrinder import API, Message, Telegrinder, Token
from telegrinder.rules import Argument, Command, Text


def format_results(results: list[UrlStatus], errors_only: bool = False) -> str:
    lines: list[str] = []
    for r in results:
        if errors_only and r.ok:
            continue
        if r.ok:
            lines.append(f"• {r.url} — OK ({r.status_code})")
        else:
            msg = r.error or f"HTTP {r.status_code}"
            lines.append(f"• {r.url} — Error: {msg}")
    return "\n".join(lines) if lines else ""


async def scheduled_check(api: API) -> None:
    """Run checks for all chats; send a message only when there are errors."""
    for chat_id in get_chat_ids_with_sites():
        sites = get_sites(chat_id)
        if not sites:
            continue
        results = check_urls(sites)
        text = format_results(results, errors_only=True)
        if not text:
            continue
        try:
            await api.send_message(chat_id=chat_id, text=f"Status check (errors):\n{text}")
        except Exception:
            pass


async def run_scheduler(api: API, interval_minutes: int = 15) -> None:
    """Every `interval_minutes`, run scheduled_check at :00, :15, :30, :45."""
    while True:
        now = datetime.now(timezone.utc)
        # Next aligned time (e.g. 0, 15, 30, 45); if current minute is already aligned, next is +interval
        next_minute = (now.minute // interval_minutes + 1) * interval_minutes
        add_hour = 1 if next_minute >= 60 else 0
        next_minute = next_minute % 60
        target = now.replace(minute=next_minute, second=0, microsecond=0) + (
            timedelta(hours=1) * add_hour
        )
        delta = (target - now).total_seconds()
        if delta <= 0:
            delta += interval_minutes * 60
        await asyncio.sleep(delta)
        await scheduled_check(api)


load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set TELEGRAM_BOT_TOKEN or BOT_TOKEN in your environment/.env file.")

api = API(token=Token(TOKEN))
bot = Telegrinder(api)


@bot.on.message(Text("/start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hello! I monitor your website list and can run scheduled checks.\n\n"
        "Commands (your list is per-chat):\n"
        "/add <url> — add a website\n"
        "/remove <url> — remove a website\n"
        "/list — show your websites\n"
        "/check — check all your websites now and show results",
    )


@bot.on.message(Command("add", Argument("url"), ignore_case=True))
async def cmd_add(message: Message, url: str) -> None:
    chat_id = message.chat.id
    normalized = add_site(chat_id, url)
    if not normalized:
        await message.answer("Please provide a non-empty URL.")
        return
    await message.answer(f"Added: {normalized}")


@bot.on.message(Command("remove", Argument("url"), ignore_case=True))
async def cmd_remove(message: Message, url: str) -> None:
    chat_id = message.chat.id
    ok = remove_site(chat_id, url)
    if ok:
        await message.answer("Removed from your list.")
    else:
        await message.answer("URL not found in your list. Use /list to see current sites.")


@bot.on.message(Text("/list"))
async def cmd_list(message: Message) -> None:
    chat_id = message.chat.id
    sites = get_sites(chat_id)
    if not sites:
        await message.answer("No websites in your list. Use /add <url> to add one.")
        return
    lines = ["Your websites:"] + [f"• {u}" for u in sites]
    await message.answer("\n".join(lines))


@bot.on.message(Text("/check"))
async def cmd_check(message: Message) -> None:
    chat_id = message.chat.id
    sites = get_sites(chat_id)
    if not sites:
        await message.answer("No websites in your list. Use /add <url> to add one.")
        return
    await message.answer("Checking…")
    results = check_urls(sites)
    text = format_results(results, errors_only=False)
    await message.answer(f"Status check:\n{text}")


def main() -> None:
    bot.loop_wrapper.add_task(run_scheduler(api))
    bot.run_forever()


if __name__ == "__main__":
    main()

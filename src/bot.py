from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from telegrinder import API, ABCRule, CallbackQuery, Context, Message, Telegrinder, Token
from telegrinder.rules import Argument, CallbackDataEq, Command, Text
from telegrinder.tools.keyboard import InlineKeyboard, InlineButton, RowButtons
from telegrinder.types import BotCommand, LinkPreviewOptions

from src.ping import UrlStatus, check_urls
from src.storage import (
    add_site,
    get_chat_ids_with_sites,
    get_sites,
    remove_site,
    get_state,
    set_state,
    ChatState,
)


def get_keyboard(state: ChatState):
    """Inline keyboard for current state: default = add/remove/list + check; add/remove = back only."""
    if state == ChatState.DEFAULT:
        return (
            InlineKeyboard()
            .add(
                RowButtons(
                    InlineButton("Add", callback_data="add"),
                    InlineButton("Remove", callback_data="remove"),
                    InlineButton("List", callback_data="list"),
                )
            )
            .row()
            .add(InlineButton("Check", callback_data="check"))
        )
    # ADD or REMOVE: only Back
    return InlineKeyboard().add(InlineButton("Back", callback_data="back"))


def get_keyboard_markup(state: ChatState):
    return get_keyboard(state).get_markup()


def format_results(results: list[UrlStatus], errors_only: bool = False) -> str:
    lines: list[str] = []
    for r in results:
        if errors_only and r.ok:
            continue
        if r.ok:
            lines.append(f"• {r.url} — OK ({r.status_code})")
        else:
            lines.append(f"• {r.url} — Error")
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
            await api.send_message(
                chat_id=chat_id,
                text=f"Status check (errors):\n{text}",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception:
            pass


BOT_COMMANDS = [
    BotCommand(command="start", description="Start the bot"),
    BotCommand(command="add", description="Add a website"),
    BotCommand(command="remove", description="Remove a website"),
    BotCommand(command="list", description="Show your websites"),
    BotCommand(command="check", description="Check all websites now"),
    BotCommand(command="help", description="Show help"),
]


class IsStateMessage(ABCRule):
    def __init__(self, state: ChatState):
        self.state = state

    async def check(self, message: Message, ctx: Context):
        if message.text.unwrap_or("").startswith("/"):
            return False
        state = get_state(message.chat.id)
        if state == self.state:
            return True
        return False



async def setup_commands_and_scheduler(api: API, interval_minutes: int = 15) -> None:
    """Set bot menu commands (for Telegram UI), then run the scheduler."""
    await api.set_my_commands(commands=BOT_COMMANDS)
    await run_scheduler(api, interval_minutes)


async def run_scheduler(api: API, interval_minutes: int = 15) -> None:
    """Every `interval_minutes`, run scheduled_check at :00, :15, :30, :45."""
    while True:
        now = datetime.now(timezone.utc)
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


def create_bot(token: str) -> tuple[API, Telegrinder]:
    """Create API and bot, register handlers. Returns (api, bot)."""
    api = API(token=Token(token))
    bot = Telegrinder(api)

    @bot.on.message(IsStateMessage(ChatState.ADD))
    async def add_url_state(message: Message) -> None:
        await cmd_add(message, message.text.unwrap())

    @bot.on.message(IsStateMessage(ChatState.REMOVE))
    async def remove_url_state(message: Message) -> None:
        await cmd_remove(message, message.text.unwrap())

    @bot.on.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        set_state(message.chat.id, ChatState.DEFAULT)
        await message.answer(
            "Hello! I monitor your website list and can run scheduled checks.\n\n"
            "Commands (your list is per-chat):\n"
            "/add <url> — add a website\n"
            "/remove <url> — remove a website\n"
            "/list — show your websites\n"
            "/check — check all your websites now and show results",
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )

    @bot.on.message(Command("add", Argument("url"), ignore_case=True))
    async def cmd_add(message: Message, url: str) -> None:
        chat_id = message.chat.id
        normalized = add_site(chat_id, url)
        if not normalized:
            await message.answer(
                "Please provide URL:",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=get_keyboard_markup(ChatState.ADD),
            )
            set_state(chat_id, ChatState.ADD)
            return
        await message.answer(
            f"Added: {normalized}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )
        set_state(message.chat.id, ChatState.DEFAULT)


    @bot.on.message(Command("remove", Argument("url"), ignore_case=True))
    async def cmd_remove(message: Message, url: str) -> None:
        chat_id = message.chat.id
        if not url or not url.strip():
            await message.answer(
                "Please provide URL(s) to remove:",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=get_keyboard_markup(ChatState.REMOVE),
            )
            set_state(chat_id, ChatState.REMOVE)
            return
        ok = remove_site(chat_id, url)
        if ok:
            await message.answer(
                "Removed from your list.",
                reply_markup=get_keyboard_markup(ChatState.DEFAULT),
            )
        else:
            await message.answer(
                "URL not found in your list. Use /list to see current sites.",
                reply_markup=get_keyboard_markup(ChatState.DEFAULT),
            )
        set_state(chat_id, ChatState.DEFAULT)

    @bot.on.message(Command("list"))
    async def cmd_list(message: Message) -> None:
        chat_id = message.chat.id
        sites = get_sites(chat_id)
        if not sites:
            await message.answer(
                "No websites in your list. Use /add <url> to add one.",
                reply_markup=get_keyboard_markup(ChatState.DEFAULT),
            )
            return
        lines = ["Your websites:"] + [f"• {u}" for u in sites]
        await message.answer(
            "\n".join(lines),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )
        set_state(chat_id, ChatState.DEFAULT)

    @bot.on.message(Command("check"))
    async def cmd_check(message: Message) -> None:
        chat_id = message.chat.id
        sites = get_sites(chat_id)
        if not sites:
            await message.answer(
                "No websites in your list. Use /add <url> to add one.",
                reply_markup=get_keyboard_markup(ChatState.DEFAULT),
            )
            return
        await message.answer(
            "Checking…",
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )
        results = check_urls(sites)
        text = format_results(results, errors_only=False)
        await message.answer(
            f"Status check:\n{text}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )
        set_state(chat_id, ChatState.DEFAULT)

    @bot.on.callback_query(CallbackDataEq("add"))
    async def cb_add(cq: CallbackQuery) -> None:
        await cq.answer()
        chat_id = cq.chat.unwrap().id
        set_state(chat_id, ChatState.ADD)
        await cq.edit_text(
            "Please provide URL:",
            reply_markup=get_keyboard_markup(ChatState.ADD),
        )

    @bot.on.callback_query(CallbackDataEq("remove"))
    async def cb_remove(cq: CallbackQuery) -> None:
        await cq.answer()
        chat_id = cq.chat.unwrap().id
        set_state(chat_id, ChatState.REMOVE)
        await cq.edit_text(
            "Please provide URL(s) to remove:",
            reply_markup=get_keyboard_markup(ChatState.REMOVE),
        )

    @bot.on.callback_query(CallbackDataEq("back"))
    async def cb_back(cq: CallbackQuery) -> None:
        await cq.answer()
        set_state(cq.chat.unwrap().id, ChatState.DEFAULT)
        await cq.edit_text(
            "Choose an action:",
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )

    @bot.on.callback_query(CallbackDataEq("list"))
    async def cb_list(cq: CallbackQuery) -> None:
        await cq.answer()
        chat_id = cq.chat.unwrap().id
        set_state(chat_id, ChatState.DEFAULT)
        sites = get_sites(chat_id)
        if not sites:
            await cq.edit_text(
                "No websites in your list. Use /add <url> or Add to add one.",
                reply_markup=get_keyboard_markup(ChatState.DEFAULT),
            )
            return
        lines = ["Your websites:"] + [f"• {u}" for u in sites]
        await cq.edit_text(
            "\n".join(lines),
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )

    @bot.on.callback_query(CallbackDataEq("check"))
    async def cb_check(cq: CallbackQuery) -> None:
        await cq.answer()
        chat_id = cq.chat.unwrap().id
        set_state(chat_id, ChatState.DEFAULT)
        sites = get_sites(chat_id)
        if not sites:
            await cq.edit_text(
                "No websites in your list. Use /add <url> or Add to add one.",
                reply_markup=get_keyboard_markup(ChatState.DEFAULT),
            )
            return
        await cq.edit_text(
            "Checking…",
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )
        results = check_urls(sites)
        text = format_results(results, errors_only=False)
        await cq.edit_text(
            f"Status check:\n{text}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=get_keyboard_markup(ChatState.DEFAULT),
        )

    return api, bot


from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import List

from src.ping import _normalize_url

import re

# Keep data.json at project root (parent of src)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data.json"


class ChatState(Enum):
    DEFAULT = "default"
    ADD = "add"
    REMOVE = "remove"


def _load_raw() -> dict:
    if not DATA_FILE.exists():
        return {}

    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
        
    return data


def _save_raw(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _strip_scheme(url: str) -> str:
    """
    Helper to compare URLs ignoring scheme.

    Examples:
        "http://example.com"  -> "example.com"
        "https://example.com" -> "example.com"
        "example.com"         -> "example.com"
    """
    for prefix in ("http://", "https://"):
        if url.startswith(prefix):
            return url[len(prefix) :]
    return url


def get_sites(chat_id: int) -> List[str]:
    """Return the list of sites for a chat. Each chat has its own list."""
    data = _load_raw()
    chats = data.get("chats", {})
    sites = chats.get(str(chat_id), [])
    return list(dict.fromkeys(sites)) if isinstance(sites, list) else []

def add_site(chat_id: int, url: str) -> list[str]:
    """Add one or more URLs to the chat's site list. Accepts URLs separated by spaces or newlines.
    Returns list of normalized URLs added (empty if none valid).
    """
    # Split url on whitespace (spaces and newlines)
    url_list = re.split(r"[\s\n]+", url.strip())
    norm_urls = []
    for part in url_list:
        norm = _normalize_url(part)
        if not norm:
            continue
        norm_urls.append(norm)

    if not norm_urls:
        return []

    data = _load_raw()
    chats = data.setdefault("chats", {})
    sites = chats.setdefault(str(chat_id), [])
    for norm in norm_urls:
        if norm not in sites:
            sites.append(norm)
    _save_raw(data)
    return norm_urls


def remove_site(chat_id: int, url: str) -> bool:
    """
    Remove one or more URLs from the chat's site list.
    Accepts URLs separated by spaces or newlines.
    Returns True if at least one URL was removed.
    """
    # Split url on whitespace (spaces and newlines)
    url_list = re.split(r"[\s\n]+", url.strip())
    norm_urls: list[str] = []
    for part in url_list:
        norm = _normalize_url(part)
        if norm:
            norm_urls.append(norm)
    if not norm_urls:
        return False

    data = _load_raw()
    chats = data.get("chats", {})
    sites = chats.get(str(chat_id), [])
    if not isinstance(sites, list):
        return False

    # Match URLs either exactly or by hostname/path ignoring scheme so that:
    # - adding "https://example.com" can be removed by "example.com"
    # - adding "example.com" can be removed by "https://example.com"
    targets_no_scheme = {_strip_scheme(u) for u in norm_urls}

    original_len = len(sites)
    sites[:] = [
        existing
        for existing in sites
        if existing not in norm_urls
        and _strip_scheme(existing) not in targets_no_scheme
    ]
    removed = len(sites) != original_len

    if removed:
        if not sites:
            del chats[str(chat_id)]
        _save_raw(data)
    return removed


def get_chat_ids_with_sites() -> List[int]:
    """Return all chat IDs that have at least one site (for scheduled checks)."""
    data = _load_raw()
    chats = data.get("chats", {})
    return [
        int(cid)
        for cid, sites in chats.items()
        if isinstance(sites, list) and len(sites) > 0
        and all(isinstance(u, str) for u in sites)
    ]

def get_state(chat_id: int) -> ChatState:
    """Get chat state from storage. Returns DEFAULT if not set or unknown."""
    data = _load_raw()
    states = data.get("states", {})
    raw = states.get(str(chat_id))
    if raw is None:
        return ChatState.DEFAULT
    try:
        return ChatState(raw)
    except ValueError:
        return ChatState.DEFAULT

def set_state(chat_id: int, state: ChatState) -> None:
    """
    Save chat state in storage. When state is DEFAULT, remove chat from states.
    """
    data = _load_raw()
    states = data.setdefault("states", {})

    if state is ChatState.DEFAULT:
        states.pop(str(chat_id), None)
    else:
        states[str(chat_id)] = state.value

    if not states:
        data.pop("states", None)
    _save_raw(data)

__all__ = [
    "ChatState",
    "get_sites",
    "add_site",
    "remove_site",
    "get_chat_ids_with_sites",
    "get_state",
    "set_state",
]

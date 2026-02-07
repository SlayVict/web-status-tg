from __future__ import annotations

import json
from pathlib import Path
from typing import List

from src.ping import _normalize_url

# Keep data.json at project root (parent of src)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data.json"


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


def _chats_key() -> str:
    return "chats"


def get_sites(chat_id: int) -> List[str]:
    """Return the list of sites for a chat. Each chat has its own list."""
    data = _load_raw()
    chats = data.get(_chats_key(), {})
    sites = chats.get(str(chat_id), [])
    return list(dict.fromkeys(sites)) if isinstance(sites, list) else []


def add_site(chat_id: int, url: str) -> str:
    """Add a URL to the chat's site list. Returns normalized URL or empty string."""
    norm = _normalize_url(url)
    if not norm:
        return ""

    data = _load_raw()
    chats = data.setdefault(_chats_key(), {})
    sites = chats.setdefault(str(chat_id), [])
    if not isinstance(sites, list):
        sites = []
        chats[str(chat_id)] = sites
    if norm not in sites:
        sites.append(norm)
    _save_raw(data)
    return norm


def remove_site(chat_id: int, url: str) -> bool:
    """Remove a URL from the chat's site list. Returns True if removed."""
    norm = _normalize_url(url)
    if not norm:
        return False

    data = _load_raw()
    chats = data.get(_chats_key(), {})
    sites = chats.get(str(chat_id), [])
    if not isinstance(sites, list) or norm not in sites:
        return False
    sites.remove(norm)
    if not sites:
        del chats[str(chat_id)]
    _save_raw(data)
    return True


def get_chat_ids_with_sites() -> List[int]:
    """Return all chat IDs that have at least one site (for scheduled checks)."""
    data = _load_raw()
    chats = data.get(_chats_key(), {})
    return [
        int(cid)
        for cid, sites in chats.items()
        if isinstance(sites, list) and len(sites) > 0
        and all(isinstance(u, str) for u in sites)
    ]


__all__ = [
    "get_sites",
    "add_site",
    "remove_site",
    "get_chat_ids_with_sites",
]

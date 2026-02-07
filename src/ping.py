from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests


@dataclass
class UrlStatus:
    """
    Result of checking a single URL.

    Attributes:
        url: The URL that was checked.
        ok: True if the request succeeded with a 2xx or 3xx status code.
        status_code: HTTP status code if a response was received, otherwise None.
        error: Error message if the request failed, otherwise None.
    """

    url: str
    ok: bool
    status_code: Optional[int] = None
    error: Optional[str] = None


def _normalize_url(url: str) -> str:
    """
    Ensure the URL has a scheme so that requests can handle it.
    Strips angle brackets if present (e.g. "<example.com>" → "http://example.com").

    Example:
        "example.com" -> "http://example.com"
        "<example.com>" -> "http://example.com"
    """
    url = url.strip()
    # Remove surrounding angle brackets if present
    if url.startswith("<") and url.endswith(">"):
        url = url[1:-1].strip()

    if not url:
        return url

    if url.startswith(("http://", "https://")):
        return url

    return "http://" + url


def check_urls(
    urls: Iterable[str],
    timeout: float = 5.0,
    allow_redirects: bool = True,
) -> List[UrlStatus]:
    """
    Check a list of web addresses and return their status.

    Args:
        urls: Iterable of URLs or hostnames.
        timeout: Request timeout in seconds for each URL.
        allow_redirects: Whether to follow redirects.

    Returns:
        List of UrlStatus objects with information for each URL.
    """
    results: List[UrlStatus] = []

    for raw_url in urls:
        normalized = _normalize_url(raw_url)
        if not normalized:
            # Skip empty strings
            continue

        try:
            response = requests.get(normalized, timeout=timeout, allow_redirects=allow_redirects)
            results.append(
                UrlStatus(
                    url=normalized,
                    ok=response.ok,
                    status_code=response.status_code,
                    error=None,
                )
            )
        except requests.RequestException as exc:
            results.append(
                UrlStatus(
                    url=normalized,
                    ok=False,
                    status_code=None,
                    error=str(exc),
                )
            )

    return results


__all__ = ["UrlStatus", "check_urls"]

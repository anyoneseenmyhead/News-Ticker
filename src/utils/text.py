from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from src.feeds.models import HeadlineItem


WHITESPACE_RE = re.compile(r"\s+")


def normalize_headline_key(title: str, url: str) -> str:
    collapsed = WHITESPACE_RE.sub(" ", title.strip().lower())
    domain = urlparse(url).netloc.lower()
    return f"{domain}::{collapsed}"


def format_headline_digest(items: list[HeadlineItem]) -> str:
    if not items:
        return "No headlines available."

    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        published = _format_digest_timestamp(item.published_at)
        lines.extend(
            [
                f"{index}. {item.title}",
                f"   Source: {item.source_name}",
                f"   Published: {published}",
                f"   URL: {item.url}",
            ]
        )
        if index < len(items):
            lines.append("")
    return "\n".join(lines)


def _format_digest_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.astimezone().strftime("%Y-%m-%d %H:%M %Z")

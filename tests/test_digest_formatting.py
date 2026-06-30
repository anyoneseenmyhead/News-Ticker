from __future__ import annotations

from datetime import datetime, timezone

from src.feeds.models import HeadlineItem
from src.utils.text import format_headline_digest


def make_item(title: str, source_name: str, published_at: datetime, url: str) -> HeadlineItem:
    return HeadlineItem(
        title=title,
        url=url,
        source_name=source_name,
        published_at=published_at,
        source_id="example.com",
        guid=title,
    )


def test_format_headline_digest_includes_current_headline_details() -> None:
    items = [
        make_item(
            "First story",
            "Example News",
            datetime(2026, 6, 30, 14, 30, tzinfo=timezone.utc),
            "https://example.com/first",
        ),
        make_item(
            "Second story",
            "Another Feed",
            datetime(2026, 6, 30, 10, 15),
            "https://example.com/second",
        ),
    ]

    digest = format_headline_digest(items)

    assert "1. First story" in digest
    assert "Source: Example News" in digest
    assert "Published:" in digest
    assert "URL: https://example.com/first" in digest
    assert "2. Second story" in digest
    assert "Published: 2026-06-30 10:15" in digest


def test_format_headline_digest_handles_empty_lists() -> None:
    assert format_headline_digest([]) == "No headlines available."

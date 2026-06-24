from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.feeds.models import HeadlineItem
from src.feeds.store import FeedStore


def make_item(
    title: str,
    *,
    hours_ago: int = 0,
    url: str = "https://example.com/story",
    guid: str | None = None,
) -> HeadlineItem:
    return HeadlineItem(
        title=title,
        url=url,
        source_name="Example",
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        source_id="example.com",
        guid=title if guid is None else guid,
    )


def test_merge_deduplicates_by_guid_and_keeps_newest_item() -> None:
    older = make_item("Older title", hours_ago=2, guid="shared-guid")
    newer = make_item("Newer title", hours_ago=0, guid="shared-guid")
    distinct = make_item("Distinct", hours_ago=1, guid="distinct-guid")
    store = FeedStore(max_items=10, max_age_hours=5)

    merged = store.merge([older, newer, distinct])

    assert [item.title for item in merged] == ["Newer title", "Distinct"]


def test_merge_falls_back_to_normalized_key_when_guid_is_blank() -> None:
    original = make_item("Big   Story", guid="   ")
    duplicate = make_item("big story", guid="", url="https://example.com/other-path")
    store = FeedStore(max_items=10, max_age_hours=5)

    merged = store.merge([original, duplicate])

    assert len(merged) == 1
    assert merged[0].title in {"Big   Story", "big story"}


def test_prune_removes_stale_items_and_enforces_max_items() -> None:
    fresh_a = make_item("Fresh A", hours_ago=0)
    fresh_b = make_item("Fresh B", hours_ago=1)
    stale = make_item("Stale", hours_ago=8)
    store = FeedStore(max_items=2, max_age_hours=5)

    merged = store.merge([fresh_b, stale, fresh_a])

    assert [item.title for item in merged] == ["Fresh A", "Fresh B"]

    store.set_max_items(1)
    assert [item.title for item in store.items] == ["Fresh A"]

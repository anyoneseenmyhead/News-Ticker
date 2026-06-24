from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone

from src.feeds.models import HeadlineItem
from src.utils.text import normalize_headline_key


class FeedStore:
    def __init__(self, max_items: int = 100, max_age_hours: int = 5) -> None:
        self.max_items = max_items
        self.max_age_hours = max(1, int(max_age_hours))
        self.items: list[HeadlineItem] = []

    def set_max_items(self, max_items: int) -> list[HeadlineItem]:
        self.max_items = max(1, int(max_items))
        self.items = self._prune_items(self.items)
        return self.items

    def set_max_age_hours(self, max_age_hours: int) -> list[HeadlineItem]:
        self.max_age_hours = max(1, int(max_age_hours))
        self.items = self._prune_items(self.items)
        return self.items

    def merge(self, incoming: list[HeadlineItem]) -> list[HeadlineItem]:
        deduped: OrderedDict[str, HeadlineItem] = OrderedDict()

        for item in sorted(self.items + incoming, key=lambda current: current.published_at, reverse=True):
            key = item.guid.strip() or normalize_headline_key(item.title, item.url)
            if key in deduped:
                continue
            deduped[key] = item

        self.items = self._prune_items(list(deduped.values()))
        return self.items

    def _prune_items(self, items: list[HeadlineItem]) -> list[HeadlineItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.max_age_hours)
        fresh_items = [item for item in items if item.published_at >= cutoff]
        return fresh_items[: self.max_items]

from __future__ import annotations

from collections import OrderedDict

from src.feeds.models import HeadlineItem
from src.utils.text import normalize_headline_key


class FeedStore:
    def __init__(self, max_items: int = 100) -> None:
        self.max_items = max_items
        self.items: list[HeadlineItem] = []

    def merge(self, incoming: list[HeadlineItem]) -> list[HeadlineItem]:
        deduped: OrderedDict[str, HeadlineItem] = OrderedDict()

        for item in sorted(self.items + incoming, key=lambda current: current.published_at, reverse=True):
            key = item.guid.strip() or normalize_headline_key(item.title, item.url)
            if key in deduped:
                continue
            deduped[key] = item

        self.items = list(deduped.values())[: self.max_items]
        return self.items

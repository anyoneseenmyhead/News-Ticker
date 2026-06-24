from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class FeedSource:
    name: str
    url: str
    enabled: bool = True


@dataclass(slots=True)
class HeadlineItem:
    title: str
    url: str
    source_name: str
    published_at: datetime
    source_id: str
    guid: str

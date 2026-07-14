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


@dataclass(slots=True)
class FeedDiagnostic:
    feed_name: str
    feed_url: str
    fetched_at: datetime
    elapsed_ms: int
    result: str
    stage: str
    item_count: int = 0
    http_status: int | None = None
    content_type: str = ""
    bytes_read: int = 0
    root_tag: str = ""
    final_url: str = ""
    error_message: str = ""
    exception_type: str = ""
    payload_preview: str = ""

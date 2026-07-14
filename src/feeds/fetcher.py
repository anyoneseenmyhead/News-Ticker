from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Iterable
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from PySide6.QtCore import QObject, Signal

from src.feeds.models import FeedDiagnostic, HeadlineItem


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class FeedFetchWorker(QObject):
    finished = Signal(list, list)
    failed = Signal(str, list)

    def __init__(self, feeds: Iterable[dict]) -> None:
        super().__init__()
        self.feeds = list(feeds)

    def run(self) -> None:
        try:
            items: list[HeadlineItem] = []
            diagnostics: list[FeedDiagnostic] = []
            for feed in self.feeds:
                feed_items, diagnostic = fetch_feed_with_diagnostics(feed)
                diagnostics.append(diagnostic)
                if not feed_items:
                    continue
                items.extend(feed_items)
            if not items:
                messages = [format_diagnostic_message(diagnostic) for diagnostic in diagnostics]
                self.failed.emit(
                    "; ".join(message for message in messages if message)
                    if messages
                    else "no headlines returned from enabled feeds"
                    ,
                    diagnostics,
                )
                return
            self.finished.emit(items, diagnostics)
        except Exception as exc:  # pragma: no cover - GUI error surface
            self.failed.emit(str(exc), [])


def fetch_feed(feed: dict) -> list[HeadlineItem]:
    items, diagnostic = fetch_feed_with_diagnostics(feed)
    if diagnostic.result == "error":
        raise RuntimeError(format_diagnostic_message(diagnostic))
    return items


def fetch_feed_with_diagnostics(feed: dict) -> tuple[list[HeadlineItem], FeedDiagnostic]:
    started_at = datetime.now(timezone.utc)
    start_clock = perf_counter()
    request = Request(
        feed["url"],
        headers={
            "User-Agent": "NewsTicker/0.1 (+https://local-app)",
            "Accept": "application/rss+xml, application/atom+xml, text/xml, application/xml",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = response.read()
            http_status = response.getcode() if hasattr(response, "getcode") else None
            headers = getattr(response, "headers", None)
            content_type = headers.get_content_type() if headers and hasattr(headers, "get_content_type") else ""
            final_url = getattr(response, "url", "") or feed["url"]
    except URLError as exc:
        return [], build_diagnostic(
            feed,
            started_at=started_at,
            start_clock=start_clock,
            result="error",
            stage="request",
            error_message=str(exc.reason),
            exception_type=type(exc).__name__,
        )

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        return [], build_diagnostic(
            feed,
            started_at=started_at,
            start_clock=start_clock,
            result="error",
            stage="parse",
            http_status=http_status,
            content_type=content_type,
            bytes_read=len(payload),
            final_url=final_url,
            error_message=str(exc),
            exception_type=type(exc).__name__,
            payload_preview=preview_payload(payload),
        )

    tag = strip_namespace(root.tag)
    if tag == "rss":
        items = parse_rss(root, feed)
    elif tag == "feed":
        items = parse_atom(root, feed)
    else:
        return [], build_diagnostic(
            feed,
            started_at=started_at,
            start_clock=start_clock,
            result="error",
            stage="format",
            http_status=http_status,
            content_type=content_type,
            bytes_read=len(payload),
            root_tag=tag,
            final_url=final_url,
            error_message="unsupported feed format",
            payload_preview=preview_payload(payload),
        )

    if not items:
        return [], build_diagnostic(
            feed,
            started_at=started_at,
            start_clock=start_clock,
            result="warning",
            stage="empty",
            http_status=http_status,
            content_type=content_type,
            bytes_read=len(payload),
            root_tag=tag,
            final_url=final_url,
            error_message="no headlines returned",
        )

    return items, build_diagnostic(
        feed,
        started_at=started_at,
        start_clock=start_clock,
        result="success",
        stage="success",
        item_count=len(items),
        http_status=http_status,
        content_type=content_type,
        bytes_read=len(payload),
        root_tag=tag,
        final_url=final_url,
    )


def parse_rss(root: ET.Element, feed: dict) -> list[HeadlineItem]:
    channel = root.find("channel")
    if channel is None:
        return []

    items: list[HeadlineItem] = []
    for node in channel.findall("item"):
        title = text_or_default(node.findtext("title"), "Untitled headline")
        link = text_or_default(node.findtext("link"), feed["url"])
        guid = text_or_default(node.findtext("guid"), f"{feed['name']}::{title}")
        published_at = parse_datetime(node.findtext("pubDate"))
        items.append(
            HeadlineItem(
                title=title,
                url=link,
                source_name=feed["name"],
                published_at=published_at,
                source_id=source_key(feed["url"]),
                guid=guid,
            )
        )
    return items


def parse_atom(root: ET.Element, feed: dict) -> list[HeadlineItem]:
    items: list[HeadlineItem] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = text_or_default(entry.findtext("atom:title", namespaces=ATOM_NS), "Untitled headline")
        link = resolve_atom_link(entry, feed["url"])
        guid = text_or_default(entry.findtext("atom:id", namespaces=ATOM_NS), f"{feed['name']}::{title}")
        published = entry.findtext("atom:published", namespaces=ATOM_NS)
        if not published:
            published = entry.findtext("atom:updated", namespaces=ATOM_NS)
        items.append(
            HeadlineItem(
                title=title,
                url=link,
                source_name=feed["name"],
                published_at=parse_datetime(published),
                source_id=source_key(feed["url"]),
                guid=guid,
            )
        )
    return items


def resolve_atom_link(entry: ET.Element, fallback: str) -> str:
    for link in entry.findall("atom:link", ATOM_NS):
        href = link.attrib.get("href")
        rel = link.attrib.get("rel", "alternate")
        if href and rel == "alternate":
            return href
    return fallback


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1]


def text_or_default(value: str | None, default: str) -> str:
    cleaned = (value or "").strip()
    return cleaned or default


def source_key(url: str) -> str:
    return urlparse(url).netloc.lower()


def build_diagnostic(
    feed: dict,
    *,
    started_at: datetime,
    start_clock: float,
    result: str,
    stage: str,
    item_count: int = 0,
    http_status: int | None = None,
    content_type: str = "",
    bytes_read: int = 0,
    root_tag: str = "",
    final_url: str = "",
    error_message: str = "",
    exception_type: str = "",
    payload_preview: str = "",
) -> FeedDiagnostic:
    elapsed_ms = max(0, int((perf_counter() - start_clock) * 1000))
    return FeedDiagnostic(
        feed_name=feed["name"],
        feed_url=feed["url"],
        fetched_at=started_at,
        elapsed_ms=elapsed_ms,
        result=result,
        stage=stage,
        item_count=item_count,
        http_status=http_status,
        content_type=content_type,
        bytes_read=bytes_read,
        root_tag=root_tag,
        final_url=final_url,
        error_message=error_message,
        exception_type=exception_type,
        payload_preview=payload_preview,
    )


def preview_payload(payload: bytes, limit: int = 500) -> str:
    return payload[:limit].decode("utf-8", errors="replace").strip()


def format_diagnostic_message(diagnostic: FeedDiagnostic) -> str:
    message = diagnostic.error_message or "no headlines returned"
    return f"{diagnostic.feed_name}: {message}"

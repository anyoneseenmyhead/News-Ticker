from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from PySide6.QtCore import QObject, Signal

from src.feeds.models import HeadlineItem


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class FeedFetchWorker(QObject):
    finished = Signal(list, list)
    failed = Signal(str)

    def __init__(self, feeds: Iterable[dict]) -> None:
        super().__init__()
        self.feeds = list(feeds)

    def run(self) -> None:
        try:
            items: list[HeadlineItem] = []
            errors: list[str] = []
            for feed in self.feeds:
                try:
                    feed_items = fetch_feed(feed)
                except Exception as exc:
                    errors.append(str(exc))
                    continue
                if not feed_items:
                    errors.append(f"{feed['name']}: no headlines returned")
                    continue
                items.extend(feed_items)
            if not items:
                self.failed.emit("; ".join(errors) if errors else "no headlines returned from enabled feeds")
                return
            self.finished.emit(items, errors)
        except Exception as exc:  # pragma: no cover - GUI error surface
            self.failed.emit(str(exc))


def fetch_feed(feed: dict) -> list[HeadlineItem]:
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
    except URLError as exc:
        raise RuntimeError(f"{feed['name']}: {exc.reason}") from exc

    root = ET.fromstring(payload)
    tag = strip_namespace(root.tag)
    if tag == "rss":
        return parse_rss(root, feed)
    if tag == "feed":
        return parse_atom(root, feed)
    raise RuntimeError(f"{feed['name']}: unsupported feed format")


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

from __future__ import annotations

from contextlib import contextmanager
from datetime import timezone
from email.message import Message
from urllib.error import URLError

import pytest

from src.feeds import fetcher


RSS_SAMPLE = b"""
<rss version="2.0">
  <channel>
    <item>
      <title>Breaking Story</title>
      <link>https://example.com/breaking</link>
      <guid>story-1</guid>
      <pubDate>Wed, 24 Jun 2026 10:30:00 GMT</pubDate>
    </item>
    <item>
      <title>   </title>
    </item>
  </channel>
</rss>
"""


ATOM_SAMPLE = b"""
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Atom Story</title>
    <id>tag:example.com,2026:1</id>
    <updated>2026-06-24T10:45:00Z</updated>
    <link rel="self" href="https://example.com/self" />
    <link rel="alternate" href="https://example.com/atom-story" />
  </entry>
</feed>
"""


@contextmanager
def fake_response(payload: bytes):
    class Response:
        def __init__(self) -> None:
            self.headers = Message()
            self.headers["Content-Type"] = "application/rss+xml"
            self.url = "https://example.com/final.xml"

        def read(self) -> bytes:
            return payload

        def getcode(self) -> int:
            return 200

    yield Response()


def test_fetch_feed_parses_rss_and_applies_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = {"name": "Example RSS", "url": "https://example.com/rss.xml"}
    monkeypatch.setattr(fetcher, "urlopen", lambda request, timeout=10: fake_response(RSS_SAMPLE))

    items = fetcher.fetch_feed(feed)

    assert len(items) == 2
    assert items[0].title == "Breaking Story"
    assert items[0].url == "https://example.com/breaking"
    assert items[0].guid == "story-1"
    assert items[0].published_at.tzinfo == timezone.utc
    assert items[1].title == "Untitled headline"
    assert items[1].url == "https://example.com/rss.xml"
    assert items[1].guid == "Example RSS::Untitled headline"


def test_fetch_feed_parses_atom_and_prefers_alternate_link(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = {"name": "Example Atom", "url": "https://example.com/atom.xml"}
    monkeypatch.setattr(fetcher, "urlopen", lambda request, timeout=10: fake_response(ATOM_SAMPLE))

    items = fetcher.fetch_feed(feed)

    assert len(items) == 1
    assert items[0].title == "Atom Story"
    assert items[0].url == "https://example.com/atom-story"
    assert items[0].guid == "tag:example.com,2026:1"


def test_fetch_feed_wraps_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = {"name": "Example", "url": "https://example.com/rss.xml"}

    def raise_urlerror(request, timeout=10):
        raise URLError("timed out")

    monkeypatch.setattr(fetcher, "urlopen", raise_urlerror)

    with pytest.raises(RuntimeError, match="Example: timed out"):
        fetcher.fetch_feed(feed)


def test_feed_fetch_worker_emits_partial_success_with_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_ok = {"name": "Good Feed", "url": "https://example.com/good.xml"}
    feed_empty = {"name": "Empty Feed", "url": "https://example.com/empty.xml"}
    feed_bad = {"name": "Bad Feed", "url": "https://example.com/bad.xml"}
    result_item = fetcher.HeadlineItem(
        title="Story",
        url="https://example.com/story",
        source_name="Good Feed",
        published_at=fetcher.parse_datetime("2026-06-24T10:30:00Z"),
        source_id="example.com",
        guid="story-guid",
    )

    def fake_fetch_feed(feed: dict):
        if feed["name"] == "Good Feed":
            return [result_item], fetcher.FeedDiagnostic(
                feed_name=feed["name"],
                feed_url=feed["url"],
                fetched_at=fetcher.datetime.now(fetcher.timezone.utc),
                elapsed_ms=12,
                result="success",
                stage="success",
                item_count=1,
            )
        if feed["name"] == "Empty Feed":
            return [], fetcher.FeedDiagnostic(
                feed_name=feed["name"],
                feed_url=feed["url"],
                fetched_at=fetcher.datetime.now(fetcher.timezone.utc),
                elapsed_ms=8,
                result="warning",
                stage="empty",
                error_message="no headlines returned",
            )
        return [], fetcher.FeedDiagnostic(
            feed_name=feed["name"],
            feed_url=feed["url"],
            fetched_at=fetcher.datetime.now(fetcher.timezone.utc),
            elapsed_ms=5,
            result="error",
            stage="request",
            error_message="Bad Feed exploded",
        )

    monkeypatch.setattr(fetcher, "fetch_feed_with_diagnostics", fake_fetch_feed)
    worker = fetcher.FeedFetchWorker([feed_ok, feed_empty, feed_bad])
    events: dict[str, object] = {}
    worker.finished.connect(lambda items, diagnostics: events.update({"items": items, "diagnostics": diagnostics}))
    worker.failed.connect(lambda message, diagnostics: events.update({"failed": message, "failed_diagnostics": diagnostics}))

    worker.run()

    assert "failed" not in events
    assert events["items"] == [result_item]
    diagnostics = events["diagnostics"]
    assert [diagnostic.result for diagnostic in diagnostics] == ["success", "warning", "error"]


def test_fetch_feed_with_diagnostics_captures_response_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = {"name": "Example RSS", "url": "https://example.com/rss.xml"}
    monkeypatch.setattr(fetcher, "urlopen", lambda request, timeout=10: fake_response(RSS_SAMPLE))

    items, diagnostic = fetcher.fetch_feed_with_diagnostics(feed)

    assert len(items) == 2
    assert diagnostic.result == "success"
    assert diagnostic.http_status == 200
    assert diagnostic.content_type == "application/rss+xml"
    assert diagnostic.root_tag == "rss"
    assert diagnostic.item_count == 2
    assert diagnostic.final_url == "https://example.com/final.xml"


def test_fetch_feed_with_diagnostics_records_parse_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = {"name": "Broken Feed", "url": "https://example.com/broken.xml"}
    monkeypatch.setattr(fetcher, "urlopen", lambda request, timeout=10: fake_response(b"<rss><channel>"))

    items, diagnostic = fetcher.fetch_feed_with_diagnostics(feed)

    assert items == []
    assert diagnostic.result == "error"
    assert diagnostic.stage == "parse"
    assert diagnostic.payload_preview == "<rss><channel>"

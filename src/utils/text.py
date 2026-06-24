from __future__ import annotations

import re
from urllib.parse import urlparse


WHITESPACE_RE = re.compile(r"\s+")


def normalize_headline_key(title: str, url: str) -> str:
    collapsed = WHITESPACE_RE.sub(" ", title.strip().lower())
    domain = urlparse(url).netloc.lower()
    return f"{domain}::{collapsed}"

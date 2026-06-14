"""Utility functions for the OSINT research pipeline."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


def extract_domain(url: str) -> str:
    return urlparse(url).netloc.lower().lstrip("www.")


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_filename(text: str, max_len: int = 100) -> str:
    safe = re.sub(r"[^a-zA-Z0-9\-_]", "_", text)
    return safe[:max_len]


def decode_html_entities(text: str) -> str:
    import html
    return html.unescape(text)


def clean_text(text: str) -> str:
    text = decode_html_entities(text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def load_config(config_path: Path | str = "kilo.json") -> dict[str, Any]:
    import json
    path = Path(config_path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

"""Wayback Machine collector — fetches archived snapshots for blocked sites."""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

from lobby_nl.models import OpacityMechanism, OpacitySignal, Source


class WaybackCollector:
    """Fetches archived snapshots via Wayback Machine CDX API.

    Used as final fallback in the chain:
    WebCollector -> Playwright -> Crawl4AI -> WaybackCollector -> opacity_signal
    """

    CDX_API = "https://web.archive.org/cdx/search/cdx"
    WAYBACK_BASE = "https://web.archive.org/web"

    def __init__(self, output_dir: Path = Path("exports/raw")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._opacity_signals: list[OpacitySignal] = []

    @property
    def opacity_signals(self) -> list[OpacitySignal]:
        return self._opacity_signals

    def search_snapshot(self, url: str, limit: int = 3) -> list[dict[str, str]]:
        """Search Wayback Machine for snapshots of a URL."""
        params = {
            "url": url,
            "output": "json",
            "limit": str(limit),
            "fl": "timestamp,original,statuscode",
            "filter": "statuscode:200",
        }
        try:
            resp = requests.get(self.CDX_API, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if len(data) > 1:
                return [
                    {"timestamp": row[0], "original": row[1], "statuscode": row[2]}
                    for row in data[1:]
                ]
        except Exception:
            pass
        return []

    def fetch_snapshot(self, timestamp: str, url: str) -> Optional[str]:
        """Fetch a specific Wayback Machine snapshot."""
        snapshot_url = f"{self.WAYBACK_BASE}/{timestamp}/{url}"
        try:
            resp = requests.get(snapshot_url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (compatible; OSINT-research-bot/1.0)"
            })
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None

    def collect_wayback(self, url: str) -> Optional[Source]:
        """Try to collect a URL via Wayback Machine. Returns Source or None."""
        snapshots = self.search_snapshot(url)
        if not snapshots:
            return None

        latest = snapshots[0]
        timestamp = latest["timestamp"]
        html = self.fetch_snapshot(timestamp, url)
        if not html:
            return None

        title = ""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)
        except Exception:
            text = html

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        signal = OpacitySignal(
            signal_type=OpacityMechanism.wayback_only,
            description=f"Live site geblokkeerd, opgehaald via Wayback Machine: {url}",
            alternative_explanation=f"Wayback snapshot van {timestamp} gebruikt als bron",
            source_ids=[],
            follow_up_target=True,
        )
        self._opacity_signals.append(signal)

        return Source(
            url=url,
            title=f"[Wayback {timestamp}] {title}",
            source_type="wayback_archive",
            content_text=text,
            content_hash=content_hash,
            archive_url=f"{self.WAYBACK_BASE}/{timestamp}/{url}",
            archive_available=True,
            metadata={
                "collector": "WaybackCollector",
                "wayback_timestamp": timestamp,
                "wayback_snapshot_url": f"{self.WAYBACK_BASE}/{timestamp}/{url}",
            },
        )

    def collect_seeds_from_csv(self, csv_path: Path) -> list[Source]:
        """Collect all seed_only URLs from manual_seeds.csv via Wayback."""
        import csv
        sources: list[Source] = []
        if not csv_path.exists():
            return sources
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("url", "").strip()
                notes = row.get("notes", "").strip()
                if url and ("seed_only" in notes.lower()):
                    time.sleep(0.5)
                    src = self.collect_wayback(url)
                    if src:
                        sources.append(src)
        return sources

"""Crawl4AI collector for JS-heavy pages and advanced extraction.

Supplements the standard WebCollector with:
- JavaScript rendering for SPA and dynamic content
- Markdown extraction via crawl4ai's built-in converter
- Async crawling for better throughput
- Graceful fallback to WebCollector if crawl4ai not installed
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any, Optional

from lobby_nl.collectors import BaseCollector, WebCollector
from lobby_nl.models import Source


class Crawl4AICollector(BaseCollector):
    """Advanced collector using Crawl4AI for JS-heavy and complex pages.

    crawl4ai provides:
    - AsyncWebCrawler for Playwright-based crawling
    - Built-in markdown extraction
    - Screenshot capture
    - Structured data extraction (LLM-based)

    Falls back to WebCollector (requests + BeautifulSoup) when:
    - crawl4ai is not installed
    - crawl4ai fails on a specific page
    - The page is static and doesn't need JS rendering
    """

    def __init__(
        self,
        output_dir: Path = Path("data/raw"),
        user_agent: str = "LobbyNL-OSINT/2.0 (research pipeline; contact@example.com)",
        request_delay: float = 2.0,
        use_js_rendering: bool = True,
    ) -> None:
        super().__init__(
            output_dir=output_dir,
            user_agent=user_agent,
            request_delay=request_delay,
        )
        self.use_js_rendering = use_js_rendering
        self._web_fallback = WebCollector(
            output_dir=output_dir,
            user_agent=user_agent,
            request_delay=request_delay,
        )

    def _crawl4ai_available(self) -> bool:
        try:
            import crawl4ai  # noqa: F401
            return True
        except ImportError:
            return False

    async def fetch_url_async(self, url: str, stealth: bool = True) -> Optional[dict[str, Any]]:
        """Standalone async fetch with optional stealth mode.

        Returns dict with markdown, html, title keys; None on failure.
        """
        if not self._crawl4ai_available():
            return None
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

            config = CrawlerRunConfig(
                word_count_threshold=10,
                exclude_external_links=False,
                remove_overlay_elements=True,
            )
            if stealth:
                from crawl4ai import CacheMode
                config.cache_mode = CacheMode.BYPASS

            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url, config=config)
                if result and result.success:
                    return {
                        "markdown": result.markdown or "",
                        "html": result.html or "",
                        "title": result.metadata.get("title", "") if result.metadata else "",
                        "url": url,
                        "stealth": stealth,
                    }
                return None
        except Exception as e:
            print(f"[WARN] Crawl4AI fetch_url_async failed for {url}: {e}")
            return None

    async def _crawl_async(self, url: str) -> Optional[dict[str, Any]]:
        """Crawl a single URL using Crawl4AI's AsyncWebCrawler.

        Returns dict with markdown, html, and metadata keys.
        """
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

            config = CrawlerRunConfig(
                word_count_threshold=10,
                exclude_external_links=True,
                remove_overlay_elements=True,
            )

            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url, config=config)
                if not result.success:
                    return None
                return {
                    "markdown": result.markdown or "",
                    "html": result.html or "",
                    "title": result.metadata.get("title", "") if result.metadata else "",
                    "url": url,
                }
        except Exception as e:
            print(f"[WARN] Crawl4AI failed for {url}: {e}")
            return None

    def collect_with_crawl4ai(self, url: str) -> Optional[Source]:
        """Collect a page using Crawl4AI, with sync wrapper.

        Returns Source with content_markdown populated, or None on failure.
        """
        if not self._crawl4ai_available():
            print(f"[INFO] crawl4ai not installed, falling back to WebCollector for {url}")
            sources = self._web_fallback.collect_urls([url])
            return sources[0] if sources else None

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            result = asyncio.run(self._crawl_async(url))
        except RuntimeError:
            result = asyncio.run(self._crawl_async(url))

        if result is None:
            print(f"[INFO] Crawl4AI returned no content, falling back to WebCollector for {url}")
            sources = self._web_fallback.collect_urls([url])
            return sources[0] if sources else None

        content = result["markdown"] or result["html"]
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        return Source(
            url=url,
            title=result.get("title", ""),
            source_type="web_crawl4ai",
            content_text=content[:100000],
            content_markdown=result.get("markdown", ""),
            content_hash=content_hash,
            metadata={
                "collector": self.__class__.__name__,
                "js_rendered": self.use_js_rendering,
            },
        )

    def collect_urls(self, urls: list[str]) -> list[Source]:
        """Collect multiple URLs, preferring Crawl4AI with fallback."""
        sources: list[Source] = []
        for url in urls:
            src = self.collect_with_crawl4ai(url)
            if src:
                sources.append(src)
            else:
                sources.append(
                    Source(
                        url=url,
                        is_dead=True,
                        notes="Failed to fetch with Crawl4AI and WebCollector fallback",
                        metadata={"collector": self.__class__.__name__},
                    )
                )
        return sources

    def collect_linked_pages(
        self, base_url: str, max_depth: Optional[int] = None, same_domain: bool = True
    ) -> list[Source]:
        """Crawls linked pages using Crawl4AI with depth limit.

        For complex crawling, falls back to WebCollector's implementation.
        """
        if not self._crawl4ai_available():
            return self._web_fallback.collect_linked_pages(base_url, max_depth, same_domain)

        sources: list[Source] = []
        visited: set[str] = set()
        to_visit = [(base_url, 0)]
        base_domain = base_url.split("/")[2] if "://" in base_url else base_url

        while to_visit:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)

            src = self.collect_with_crawl4ai(url)
            if src is None or src.is_dead:
                sources.append(Source(url=url, is_dead=True))
                continue
            sources.append(src)

            if depth < max_depth:
                from bs4 import BeautifulSoup
                html = src.content_text
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"]
                        if href.startswith("/"):
                            href = f"https://{base_domain}{href}"
                        if href.startswith("http") and href not in visited:
                            to_visit.append((href, depth + 1))

        return sources

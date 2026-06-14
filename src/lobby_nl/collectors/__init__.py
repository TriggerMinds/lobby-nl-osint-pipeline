"""Data collectors for the OSINT research pipeline.

Collectors cover:
- Web scraping (organization websites, campaign sites, event pages)
- Parliamentary records (Tweede Kamer, Eerste Kamer)
- EU Transparency Register
- Archive collection (Internet Archive, Dutch web archiving)
"""

from __future__ import annotations

import hashlib
import random
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings

from lobby_nl.models import OpacityMechanism, OpacitySignal, Source

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def parse_html_or_xml(content: str, url: str = "") -> BeautifulSoup:
    is_xml = (
        url.endswith((".xml", ".rss", ".atom"))
        or content.strip().startswith("<?xml")
        or "<urlset" in content[:500]
        or "<rss" in content[:500]
        or "<feed" in content[:500]
    )
    return BeautifulSoup(content, "xml" if is_xml else "lxml")


def _get_random_user_agent() -> str:
    try:
        from fake_useragent import UserAgent
        return UserAgent().chrome or _FALLBACK_UA
    except Exception:
        return _FALLBACK_UA


_FALLBACK_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _load_depth_overrides(config_path: Optional[Path] = None) -> dict[str, int]:
    overrides: dict[str, int] = {}
    if config_path is None:
        config_path = Path("config/sources.yaml")
    if not config_path.exists():
        return overrides
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        raw = cfg.get("crawl_depth_overrides", {})
        if isinstance(raw, dict):
            for key, val in raw.items():
                if isinstance(val, int):
                    overrides[key] = val
    except Exception:
        pass
    return overrides


def _get_domain_from_url(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc.lower()


def _get_crawl_depth_for_url(url: str, overrides: Optional[dict[str, int]] = None) -> int:
    if overrides is None:
        overrides = _load_depth_overrides()
    domain = _get_domain_from_url(url)
    return overrides.get(domain, overrides.get("default", 1))

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


class BaseCollector:
    """Base collector with common HTTP and archive functionality."""

    def __init__(
        self,
        output_dir: Path = Path("exports/raw"),
        user_agent: str = "",
        request_delay: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.session.headers.update({"User-Agent": user_agent or _get_random_user_agent()})
        self.request_delay = request_delay
        self.max_retries = max_retries
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        jitter = random.uniform(1.5, 4.0)
        delay_needed = jitter - elapsed
        if delay_needed > 0:
            time.sleep(delay_needed)
        self._last_request_time = time.time()

    def _rotate_user_agent(self) -> None:
        self.session.headers.update({"User-Agent": _get_random_user_agent()})

    def fetch_page(self, url: str, timeout: int = 30) -> Optional[requests.Response]:
        last_exception: Optional[Exception] = None
        for attempt in range(self.max_retries):
            self._rate_limit()
            try:
                resp = self.session.get(url, timeout=timeout)
                if resp.status_code == 403:
                    self._rotate_user_agent()
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    print(f"[RETRY] 403 on {url}, attempt {attempt + 1}/{self.max_retries}, rotating UA, waiting {backoff:.1f}s")
                    time.sleep(backoff)
                    last_exception = requests.HTTPError(f"403 Forbidden: {url}", response=resp)
                    continue
                if resp.status_code == 429:
                    backoff = (2 ** attempt) * 5 + random.uniform(0, 5)
                    print(f"[RETRY] 429 on {url}, attempt {attempt + 1}/{self.max_retries}, waiting {backoff:.1f}s")
                    time.sleep(backoff)
                    continue
                resp.raise_for_status()
                return resp
            except (requests.Timeout, requests.ConnectionError) as e:
                backoff = (2 ** attempt) + random.uniform(0, 1)
                print(f"[RETRY] Network error on {url}: {e}, attempt {attempt + 1}/{self.max_retries}, waiting {backoff:.1f}s")
                time.sleep(backoff)
                last_exception = e
            except requests.HTTPError as e:
                if resp is not None and 500 <= resp.status_code < 600:
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    print(f"[RETRY] {resp.status_code} on {url}, attempt {attempt + 1}/{self.max_retries}, waiting {backoff:.1f}s")
                    time.sleep(backoff)
                    last_exception = e
                    continue
                print(f"[WARN] HTTP error on {url}: {e}")
                return None
            except requests.RequestException as e:
                print(f"[WARN] Failed to fetch {url}: {e}")
                return None
        print(f"[WARN] Failed to fetch {url} after {self.max_retries} retries: {last_exception}")
        return None

    def extract_html_content(self, html: str, url: str) -> tuple[str, str]:
        soup = parse_html_or_xml(html, url=url)
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return title, text

    def create_source(
        self,
        url: str,
        content: str,
        title: str = "",
        source_type: str = "web",
        archive_url: Optional[str] = None,
    ) -> Source:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return Source(
            url=url,
            title=title,
            source_type=source_type,
            content_text=content,
            content_hash=content_hash,
            archive_url=archive_url,
            archive_available=archive_url is not None,
            metadata={"collector": self.__class__.__name__},
        )


class WebCollector(BaseCollector):
    """Collects data from organization websites, campaign sites, event pages, etc.

    Fallback chain: requests -> Playwright -> Crawl4AI (stealth)
    Robots.txt violations generate OpacitySignals, never bypassed.
    """

    def __init__(
        self,
        output_dir: Path = Path("exports/raw"),
        user_agent: str = "",
        request_delay: float = 2.0,
        max_retries: int = 3,
        depth_overrides: Optional[dict[str, int]] = None,
    ) -> None:
        super().__init__(
            output_dir=output_dir,
            user_agent=user_agent,
            request_delay=request_delay,
            max_retries=max_retries,
        )
        self._depth_overrides = depth_overrides or _load_depth_overrides()
        self._opacity_signals: list[OpacitySignal] = []

    @property
    def opacity_signals(self) -> list[OpacitySignal]:
        return self._opacity_signals

    def _fetch_with_crawl4ai(self, url: str) -> Optional[str]:
        try:
            from crawl4ai import CrawlerRunConfig
            from crawl4ai.async_crawler import AsyncWebCrawler
            import asyncio as _asyncio

            config = CrawlerRunConfig(
                word_count_threshold=10,
                exclude_external_links=False,
                remove_overlay_elements=True,
            )

            async def _run():
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url, config=config)
                    if result and result.success:
                        return result.markdown or result.html or ""
                    return None

            try:
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    import nest_asyncio
                    nest_asyncio.apply()
            except RuntimeError:
                pass
            return _asyncio.run(_run())
        except ImportError:
            return None
        except Exception as e:
            print(f"[WARN] Crawl4AI fallback failed for {url}: {e}")
            return None

    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=_get_random_user_agent(),
                    locale="nl-NL",
                    timezone_id="Europe/Amsterdam",
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            print(f"[WARN] Playwright fallback failed for {url}: {e}")
            return None

    def _check_robots_txt(self, url: str) -> Optional[OpacitySignal]:
        from urllib.parse import urlparse
        from urllib.robotparser import RobotFileParser

        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            if not rp.can_fetch("*", url):
                signal = OpacitySignal(
                    signal_type=OpacityMechanism.robots_txt_block,
                    description=f"robots.txt blokkeert crawl van {url}",
                    alternative_explanation="Technische maatregel, niet per definitie opzettelijk",
                    source_ids=[],
                    follow_up_target=True,
                )
                self._opacity_signals.append(signal)
                print(f"[OPACITY] robots.txt blocks {url}")
                return signal
        except Exception as e:
            print(f"[INFO] Could not check robots.txt for {url}: {e}")
        return None

    def _find_alternative_entry(self, url: str) -> list[str]:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        alternatives = [
            f"{base}/sitemap.xml",
            f"{base}/nieuws",
            f"{base}/publicaties",
            f"{base}/over-ons",
            f"{base}/contact",
        ]
        return alternatives

    def _fetch_page_robust(self, url: str, check_robots: bool = True) -> tuple[Optional[requests.Response], Optional[OpacitySignal]]:
        if check_robots:
            block_signal = self._check_robots_txt(url)
            if block_signal:
                return None, block_signal

        resp = self.fetch_page(url)
        if resp is not None:
            return resp, None

        print(f"[INFO] Attempting Playwright fallback for {url}...")
        html = self._fetch_with_playwright(url)
        if html:
            from requests import Response
            fake_resp = Response()
            fake_resp.status_code = 200
            fake_resp._content = html.encode("utf-8")
            fake_resp.url = url
            fake_resp.encoding = "utf-8"
            fake_resp.headers["X-Collector"] = "playwright_fallback"
            return fake_resp, None

        print(f"[INFO] Attempting Crawl4AI stealth fallback for {url}...")
        html = self._fetch_with_crawl4ai(url)
        if html:
            fallback_signal = OpacitySignal(
                signal_type=OpacityMechanism.blocking_403,
                description=f"Blocked by server (403), retrieved via Crawl4AI stealth for {url}",
                alternative_explanation="Server kon bot-detectie hebben; Crawl4AI omzeilt dit op transparante wijze",
                source_ids=[],
                follow_up_target=True,
            )
            self._opacity_signals.append(fallback_signal)

            from requests import Response
            fake_resp = Response()
            fake_resp.status_code = 200
            fake_resp._content = html.encode("utf-8")
            fake_resp.url = url
            fake_resp.encoding = "utf-8"
            fake_resp.headers["X-Collector"] = "crawl4ai_stealth_fallback"
            return fake_resp, fallback_signal

        return None, None

    def collect_urls(self, urls: list[str]) -> list[Source]:
        sources: list[Source] = []
        for url in urls:
            resp, _sig = self._fetch_page_robust(url)
            if resp is None:
                sources.append(
                    Source(
                        url=url,
                        is_dead=True,
                        notes="Failed to fetch page after all fallbacks",
                        metadata={"collector": self.__class__.__name__},
                    )
                )
                continue
            collector_meta = resp.headers.get("X-Collector", self.__class__.__name__)
            title, text = self.extract_html_content(resp.text, url)
            src = self.create_source(url, text, title, "web")
            src.content_markdown = text
            src.metadata["collector"] = collector_meta
            sources.append(src)
            self._save_raw(url, resp.text)
        return sources

    def collect_linked_pages(
        self, base_url: str, max_depth: Optional[int] = None, same_domain: bool = True
    ) -> list[Source]:
        if max_depth is None:
            max_depth = _get_crawl_depth_for_url(base_url, self._depth_overrides)
        sources: list[Source] = []
        visited: set[str] = set()
        to_visit = [(base_url, 0)]
        base_domain = urlparse(base_url).netloc
        while to_visit:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)
            resp, block_signal = self._fetch_page_robust(url)
            if block_signal and not resp:
                sources.append(Source(url=url, is_dead=True,
                    notes=f"Blocked by robots.txt: {block_signal.description}",
                    metadata={"collector": self.__class__.__name__, "opacity_signal": block_signal.signal_id}))
                if not same_domain:
                    continue
                alternatives = self._find_alternative_entry(url)
                for alt_url in alternatives:
                    if alt_url not in visited:
                        to_visit.append((alt_url, depth + 1))
                continue
            if resp is None:
                sources.append(Source(url=url, is_dead=True))
                continue
            collector_meta = resp.headers.get("X-Collector", self.__class__.__name__)
            title, text = self.extract_html_content(resp.text, url)
            src = self.create_source(url, text, title)
            src.metadata["collector"] = collector_meta
            sources.append(src)
            self._save_raw(url, resp.text)
            if depth < max_depth:
                soup = parse_html_or_xml(resp.text, url=url)
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    full_url = urljoin(url, href)
                    if same_domain and urlparse(full_url).netloc != base_domain:
                        continue
                    if full_url.startswith("http") and full_url not in visited:
                        to_visit.append((full_url, depth + 1))
        return sources

    def _save_raw(self, url: str, html: str) -> None:
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", url)[:100]
        raw_path = self.output_dir / f"{safe_name}.html"
        raw_path.write_text(html, encoding="utf-8")


class ParliamentaryCollector(BaseCollector):
    """Collects parliamentary records via official Dutch government search portals.

    Primary: zoek.officielebekendmakingen.nl (verified working 2026-06-14, returns 200)
    OData API: opendata.tweedekamer.nl (attempted, may require specific endpoint auth)
    """

    TK_SEARCH_URL = "https://zoek.officielebekendmakingen.nl/resultaten"
    TK_ODATA_BASE = "https://opendata.tweedekamer.nl/v1"
    EK_API_BASE = "https://www.eerstekamer.nl/"

    def search_tweede_kamer(
        self, query: str, max_results: int = 50
    ) -> list[dict[str, Any]]:
        """Search Tweede Kamer records via zoek.officielebekendmakingen.nl.

        Uses the official search with OData v4 filter fallback.
        Verified working URL (2026-06-14): zoek.officielebekendmakingen.nl/resultaten = 200.
        """
        import urllib.parse

        results: list[dict[str, Any]] = []

        # Primary: official search portal
        params: dict[str, str] = {
            "q": query,
            "prl": "Tweede Kamer der Staten-Generaal",
            "srt": "0",
        }
        search_url = f"{self.TK_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        resp = self.fetch_page(search_url)
        if resp is not None:
            soup = parse_html_or_xml(resp.text, url=resp.url)
            for item in soup.select(
                "[class*='result'], [class*='search-result'], .result-item, article, li"
            )[:max_results]:
                title_el = item.select_one("a, h2, h3, .title")
                if title_el:
                    title = title_el.get_text(strip=True)
                    link_el = item.select_one("a[href]") or title_el
                    href = link_el.get("href", "") if link_el.name == "a" else ""
                    results.append({
                        "title": title,
                        "url": urljoin(self.TK_SEARCH_URL, href) if href else "",
                        "date": "",
                        "type": "kamerstuk",
                        "id": "",
                        "chamber": "Tweede Kamer",
                    })

        # Fallback: try OData API
        if not results:
            endpoint = f"{self.TK_ODATA_BASE}/items"
            odata_params: dict[str, str] = {
                "$filter": f"contains(title, '{query}')",
                "$top": str(max_results),
                "$orderby": "date desc",
                "$format": "json",
            }
            odata_resp = self.fetch_page(
                f"{endpoint}?{urllib.parse.urlencode(odata_params)}"
            )
            if odata_resp is not None:
                try:
                    data = odata_resp.json()
                    items = data.get("value", [])
                    for item in items:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "date": item.get("date", ""),
                            "type": item.get("type", "kamerstuk"),
                            "id": item.get("id", ""),
                            "chamber": "Tweede Kamer",
                        })
                except (ValueError, KeyError):
                    pass

        return results

    def search_eerste_kamer(
        self, query: str, max_results: int = 50
    ) -> list[dict[str, Any]]:
        """Search Eerste Kamer records via the website search."""
        results: list[dict[str, Any]] = []
        import urllib.parse
        search_url = f"{self.EK_API_BASE}zoeken?q={urllib.parse.quote(query)}"
        resp = self.fetch_page(search_url)
        if resp is None:
            return results
        soup = parse_html_or_xml(resp.text, url=resp.url)
        for item in soup.select(".zoekresultaten .result")[:max_results]:
            title_el = item.select_one("a")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": urljoin(self.EK_API_BASE, title_el.get("href", "")),
                    "date": "",
                    "type": "eerstekamer",
                    "chamber": "Eerste Kamer",
                })
        if not results:
            for item in soup.select("a[href*='kamerstuk']")[:max_results]:
                if query.lower() in item.get_text(strip=True).lower():
                    results.append({
                        "title": item.get_text(strip=True),
                        "url": urljoin(self.EK_API_BASE, item.get("href", "")),
                        "date": "",
                        "type": "eerstekamer",
                        "chamber": "Eerste Kamer",
                    })
        return results

    def fetch_document(self, url: str) -> Optional[str]:
        """Fetch a specific parliamentary document as text."""
        resp = self.fetch_page(url)
        if resp is None:
            return None
        _, text = self.extract_html_content(resp.text, url)
        return text


class EURegisterCollector(BaseCollector):
    """Collects data from the EU Transparency Register via transparency-register.europa.eu.

    Verified working URL (2026-06-14): https://transparency-register.europa.eu
    """

    EU_REGISTER_URL = "https://transparency-register.europa.eu"
    EU_FALLBACK_URL = "https://transparency-register.europa.eu"

    def search_organization(self, name: str) -> list[dict[str, Any]]:
        """Search the EU Transparency Register via the lobbying.eu search page.

        Uses the API where available, falls back to web scraping.
        """
        results: list[dict[str, Any]] = []

        import urllib.parse
        search_url = (
            f"{self.EU_FALLBACK_URL}/search?"
            f"q={urllib.parse.quote(name)}"
        )
        resp = self.fetch_page(search_url)
        if resp is None:
            return results

        soup = parse_html_or_xml(resp.text, url=resp.url)
        for card in soup.select("[class*='card'], [class*='result'], [class*='organization']"):
            name_el = card.select_one("h2, h3, .name, .title")
            if name_el:
                name_text = name_el.get_text(strip=True)
                reg_number = ""
                reg_el = card.select_one("[class*='reg'], [class*='id'], .registration")
                if reg_el:
                    reg_number = reg_el.get_text(strip=True)
                country = ""
                country_el = card.select_one("[class*='country'], [class*='location']")
                if country_el:
                    country = country_el.get_text(strip=True)
                results.append({
                    "name": name_text,
                    "reg_number": reg_number,
                    "country": country,
                })

        if not results:
            for row in soup.select("table tr")[1:10]:
                cells = row.select("td")
                if len(cells) >= 2:
                    results.append({
                        "name": cells[0].get_text(strip=True),
                        "reg_number": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        "country": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                    })

        return results


class ArchiveCollector(BaseCollector):
    """Collects archival snapshots via Internet Archive and other sources."""

    WAYBACK_AVAILABLE_URL = "https://archive.org/wayback/available"

    def check_archive(self, url: str) -> Optional[str]:
        resp = self.fetch_page(
            f"{self.WAYBACK_AVAILABLE_URL}?url={url}"
        )
        if resp is None:
            return None
        try:
            data = resp.json()
            if data.get("archived_snapshots"):
                return data["archived_snapshots"].get("closest", {}).get("url")
        except (ValueError, KeyError):
            pass
        return None

    def fetch_archived_page(self, archive_url: str) -> Optional[str]:
        resp = self.fetch_page(archive_url)
        if resp is None:
            return None
        _, text = self.extract_html_content(resp.text, archive_url)
        return text

    def compare_versions(
        self, current_text: str, archived_text: str, url: str
    ) -> dict[str, Any]:
        current_hash = hashlib.sha256(current_text.encode()).hexdigest()
        archived_hash = hashlib.sha256(archived_text.encode()).hexdigest()
        changed = current_hash != archived_hash
        import difflib

        diff = list(
            difflib.unified_diff(
                archived_text.splitlines(),
                current_text.splitlines(),
                lineterm="",
                fromfile="archive",
                tofile="current",
            )
        )
        return {
            "url": url,
            "changed": changed,
            "current_hash": current_hash,
            "archived_hash": archived_hash,
            "diff_lines": diff[:500],
        }

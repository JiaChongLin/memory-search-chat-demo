from __future__ import annotations

import logging
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from backend.app.core.config import Settings


# 第一版先用关键词启发式判断是否需要联网搜索。
REALTIME_KEYWORDS = (
    "今天",
    "今日",
    "最新",
    "当前",
    "现在",
    "最近",
    "新闻",
    "价格",
    "行情",
    "实时",
    "recent",
    "latest",
    "current",
    "today",
    "news",
    "price",
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: Optional[str] = None


logger = logging.getLogger(__name__)


class DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: Optional[str] = None
        self._capturing_title = False
        self._capturing_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_dict = dict(attrs)
        class_names = attrs_dict.get("class", "")

        if tag == "a" and "result__a" in class_names:
            self._flush_current_result()
            self._capturing_title = True
            self._current_title = []
            self._current_snippet = []
            self._current_url = self._normalize_result_url(attrs_dict.get("href"))
            return

        if "result__snippet" in class_names and self._current_url:
            self._capturing_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capturing_title:
            self._capturing_title = False
        if tag in {"a", "div", "span"} and self._capturing_snippet:
            self._capturing_snippet = False

    def handle_data(self, data: str) -> None:
        if self._capturing_title:
            self._current_title.append(data)
        if self._capturing_snippet:
            self._current_snippet.append(data)

    def close(self) -> None:
        super().close()
        self._flush_current_result()

    def _flush_current_result(self) -> None:
        if not self._current_url:
            return

        title = self._clean_text("".join(self._current_title))
        snippet = self._clean_text("".join(self._current_snippet))
        if title:
            self.results.append(
                SearchResult(
                    title=title,
                    url=self._current_url,
                    snippet=snippet or None,
                )
            )

        self._current_title = []
        self._current_snippet = []
        self._current_url = None
        self._capturing_title = False
        self._capturing_snippet = False

    def _clean_text(self, value: str) -> str:
        return " ".join(unescape(value).split())

    def _normalize_result_url(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        parsed = urlparse(value)
        if "duckduckgo.com" in parsed.netloc and parsed.path == "/l/":
            target = parse_qs(parsed.query).get("uddg", [None])[0]
            return unescape(target) if target else value

        if value.startswith("//"):
            return f"https:{value}"

        return value


class SearchService:
    """负责判断是否触发搜索，并提供一个可直接用于 demo 的搜索实现。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def should_search(self, message: str) -> bool:
        if not self._settings.search_enabled:
            return False

        lowered_message = message.lower()
        return any(
            keyword in message or keyword in lowered_message
            for keyword in REALTIME_KEYWORDS
        )

    def search(self, query: str) -> list[SearchResult]:
        if not self._settings.search_enabled:
            return []

        provider = self._settings.search_provider.strip().lower()
        if provider == "duckduckgo":
            return self._search_duckduckgo(query)

        logger.warning("Unsupported search provider: %s", self._settings.search_provider)
        return []

    def _search_duckduckgo(self, query: str) -> list[SearchResult]:
        try:
            response = httpx.get(
                self._build_duckduckgo_url(query),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"
                    )
                },
                timeout=self._settings.search_timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Search request failed: %s", exc)
            return []

        parser = DuckDuckGoHTMLParser()
        parser.feed(response.text)
        parser.close()

        deduplicated_results: list[SearchResult] = []
        seen_urls: set[str] = set()
        for result in parser.results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            deduplicated_results.append(result)
            if len(deduplicated_results) >= self._settings.search_max_results:
                break

        return deduplicated_results

    def _build_duckduckgo_url(self, query: str) -> str:
        params = urlencode({"q": query})
        base_url = self._settings.search_base_url.rstrip("?")
        connector = "&" if "?" in base_url else "?"
        return f"{base_url}{connector}{params}"

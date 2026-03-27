from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.config import Settings


REALTIME_KEYWORDS = (
    "今天",
    "今日",
    "最新",
    "当前",
    "现在",
    "新闻",
    "价格",
    "股价",
    "汇率",
    "最近",
    "实时",
    "recent",
    "latest",
    "current",
    "today",
    "news",
    "price",
)


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str | None = None


class SearchService:
    """Encapsulates search triggering and search provider integration."""

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
        # Placeholder for the real search provider.
        # Keep the method boundary stable so we can add implementation later.
        _ = query
        return []

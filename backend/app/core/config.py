from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


# backend/app/core/config.py -> backend/app -> backend -> 仓库根目录
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"


def _load_dotenv(path: Path) -> None:
    # 保持零额外依赖，方便 demo 直接运行。
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')

        # 外部环境变量优先，便于本地覆盖 .env 配置。
        if key and key not in os.environ:
            os.environ[key] = value


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    api_prefix: str
    database_url: str
    llm_provider: str
    llm_api_key: str
    llm_model: str
    llm_base_url: str
    llm_timeout_seconds: int
    llm_fallback_enabled: bool
    memory_short_window: int
    memory_summary_enabled: bool
    memory_summary_max_chars: int
    search_enabled: bool
    search_provider: str
    search_base_url: str
    search_timeout_seconds: int
    search_max_results: int

    @property
    def llm_chat_url(self) -> str:
        base_url = self.llm_base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # 缓存配置对象，避免重复读取 .env。
    _load_dotenv(ENV_FILE)

    return Settings(
        app_name=os.getenv("APP_NAME", "memory-search-chat-demo"),
        app_env=os.getenv("APP_ENV", "development"),
        api_prefix=os.getenv("API_PREFIX", "/api"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./app.db"),
        llm_provider=os.getenv("LLM_PROVIDER", "dashscope"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "qwen-plus"),
        llm_base_url=os.getenv(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        llm_timeout_seconds=_get_int("LLM_TIMEOUT_SECONDS", 30),
        llm_fallback_enabled=_get_bool("LLM_FALLBACK_ENABLED", True),
        memory_short_window=_get_int("MEMORY_SHORT_WINDOW", 6),
        memory_summary_enabled=_get_bool("MEMORY_SUMMARY_ENABLED", True),
        memory_summary_max_chars=_get_int("MEMORY_SUMMARY_MAX_CHARS", 600),
        search_enabled=_get_bool("SEARCH_ENABLED", True),
        search_provider=os.getenv("SEARCH_PROVIDER", "duckduckgo"),
        search_base_url=os.getenv(
            "SEARCH_BASE_URL",
            "https://html.duckduckgo.com/html/",
        ),
        search_timeout_seconds=_get_int("SEARCH_TIMEOUT_SECONDS", 15),
        search_max_results=_get_int("SEARCH_MAX_RESULTS", 5),
    )

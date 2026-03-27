from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request

from backend.app.core.config import Settings
from backend.app.services.memory_service import MemoryMessage
from backend.app.services.search_service import SearchResult


SYSTEM_PROMPT = (
    "你是一个面向 demo 项目的中文聊天助手。"
    "回答要尽量清晰、简洁、可靠。"
    "如果上下文中包含会话摘要或搜索结果，请优先结合这些信息回答。"
)


@dataclass(slots=True)
class LLMReply:
    content: str
    used_live_model: bool


class LLMService:
    """Handles model invocation while keeping provider-specific details isolated."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate_reply(
        self,
        user_message: str,
        history: list[MemoryMessage],
        session_summary: str | None = None,
        search_results: list[SearchResult] | None = None,
    ) -> LLMReply:
        messages = self._build_messages(
            user_message=user_message,
            history=history,
            session_summary=session_summary,
            search_results=search_results or [],
        )

        if not self._settings.llm_api_key:
            return LLMReply(
                content=self._build_mock_reply(
                    user_message=user_message,
                    history=history,
                    session_summary=session_summary,
                    search_results=search_results or [],
                ),
                used_live_model=False,
            )

        if self._settings.llm_provider != "dashscope":
            raise ValueError(
                f"Unsupported LLM provider: {self._settings.llm_provider}"
            )

        try:
            content = self._call_dashscope(messages)
        except (RuntimeError, ValueError):
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to call LLM provider: {exc}") from exc

        return LLMReply(content=content, used_live_model=True)

    def _build_messages(
        self,
        user_message: str,
        history: list[MemoryMessage],
        session_summary: str | None,
        search_results: list[SearchResult],
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        if session_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"会话摘要：\n{session_summary}",
                }
            )

        if search_results:
            messages.append(
                {
                    "role": "system",
                    "content": self._render_search_context(search_results),
                }
            )

        for item in history:
            messages.append({"role": item.role, "content": item.content})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _render_search_context(self, search_results: list[SearchResult]) -> str:
        lines = ["以下是可供参考的联网搜索结果："]
        for index, result in enumerate(search_results, start=1):
            lines.append(f"{index}. 标题：{result.title}")
            lines.append(f"   链接：{result.url}")
            if result.snippet:
                lines.append(f"   摘要：{result.snippet}")
        return "\n".join(lines)

    def _build_mock_reply(
        self,
        user_message: str,
        history: list[MemoryMessage],
        session_summary: str | None,
        search_results: list[SearchResult],
    ) -> str:
        parts = [
            "后端骨架已就绪，但当前未检测到可用的百炼 API Key，因此先返回本地占位回复。",
            f"当前消息：{user_message}",
        ]

        if history:
            parts.append(f"已读取最近 {len(history)} 条上下文消息。")

        if session_summary:
            parts.append(f"当前会话摘要：{session_summary}")

        if search_results:
            parts.append(f"本轮可用搜索结果数量：{len(search_results)}")

        parts.append("补齐真实模型配置后，这里会返回百炼模型生成的正式回答。")
        return "\n\n".join(parts)

    def _call_dashscope(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self._settings.llm_model,
            "messages": messages,
            "temperature": 0.3,
        }

        http_request = request.Request(
            url=self._settings.llm_chat_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"DashScope request failed with status {exc.code}: {error_body}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"DashScope request failed: {exc.reason}") from exc

        return self._extract_content(response_data)

    def _extract_content(self, response_data: dict) -> str:
        choices = response_data.get("choices") or []
        if not choices:
            raise ValueError("LLM response does not contain choices.")

        message = choices[0].get("message") or {}
        content = message.get("content")

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            joined = "\n".join(part for part in text_parts if part).strip()
            if joined:
                return joined

        raise ValueError("Unable to extract text content from LLM response.")

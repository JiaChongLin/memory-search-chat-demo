from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from urllib import error, request

from backend.app.core.config import Settings
from backend.app.services.memory_service import MemoryMessage
from backend.app.services.search_service import SearchResult


SYSTEM_PROMPT = (
    "你是一个用于 demo 的聊天助手。"
    "请基于用户输入、会话历史、会话摘要和搜索上下文生成简洁回答。"
    "如果搜索结果为空，就不要假装引用了实时信息；如果信息不足，可以明确说明。"
)


@dataclass
class LLMReply:
    content: str
    used_live_model: bool
    fallback_reason: Optional[str] = None


class LLMService:
    """负责整理上下文并调用大语言模型服务。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate_reply(
        self,
        user_message: str,
        history: list[MemoryMessage],
        session_summary: Optional[str] = None,
        search_results: Optional[list[SearchResult]] = None,
    ) -> LLMReply:
        normalized_search_results = search_results or []
        messages = self._build_messages(
            user_message=user_message,
            history=history,
            session_summary=session_summary,
            search_results=normalized_search_results,
        )

        if not self._settings.llm_api_key:
            return self._build_fallback_reply(
                user_message=user_message,
                history=history,
                session_summary=session_summary,
                search_results=normalized_search_results,
                reason="missing_api_key",
            )

        if self._settings.llm_provider != "dashscope":
            if not self._settings.llm_fallback_enabled:
                raise ValueError(
                    f"Unsupported LLM provider: {self._settings.llm_provider}"
                )
            return self._build_fallback_reply(
                user_message=user_message,
                history=history,
                session_summary=session_summary,
                search_results=normalized_search_results,
                reason=f"unsupported_provider:{self._settings.llm_provider}",
            )

        try:
            content = self._call_dashscope(messages)
            return LLMReply(content=content, used_live_model=True)
        except (RuntimeError, ValueError) as exc:
            if not self._settings.llm_fallback_enabled:
                raise
            return self._build_fallback_reply(
                user_message=user_message,
                history=history,
                session_summary=session_summary,
                search_results=normalized_search_results,
                reason=f"provider_request_failed:{exc}",
            )
        except Exception as exc:
            if not self._settings.llm_fallback_enabled:
                raise RuntimeError(f"Failed to call LLM provider: {exc}") from exc
            return self._build_fallback_reply(
                user_message=user_message,
                history=history,
                session_summary=session_summary,
                search_results=normalized_search_results,
                reason=f"unexpected_error:{exc}",
            )

    def _build_messages(
        self,
        user_message: str,
        history: list[MemoryMessage],
        session_summary: Optional[str],
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

    def _build_fallback_reply(
        self,
        user_message: str,
        history: list[MemoryMessage],
        session_summary: Optional[str],
        search_results: list[SearchResult],
        reason: str,
    ) -> LLMReply:
        parts = [
            "当前未能稳定调用在线模型，因此返回本地降级回复，方便继续联调整体链路。",
            f"用户消息：{user_message}",
        ]

        if history:
            parts.append(f"已读取最近上下文条数：{len(history)}")

        if session_summary:
            parts.append(f"当前会话摘要：{session_summary}")

        if search_results:
            parts.append(f"当前搜索结果数量：{len(search_results)}")
            formatted_sources = "；".join(
                f"{result.title} ({result.url})" for result in search_results[:3]
            )
            parts.append(f"可参考来源：{formatted_sources}")

        parts.append("后续修正模型配置或网络环境后，这里会恢复为正式模型生成内容。")
        return LLMReply(
            content="\n\n".join(parts),
            used_live_model=False,
            fallback_reason=reason,
        )

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
            with request.urlopen(
                http_request,
                timeout=self._settings.llm_timeout_seconds,
            ) as response:
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

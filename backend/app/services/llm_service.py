from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from urllib import error, request

from backend.app.core.config import Settings
from backend.app.services.context_resolver import RelatedSessionDigest
from backend.app.services.memory_service import MemoryMessage
from backend.app.services.search_service import SearchResult


SYSTEM_PROMPT = (
    "你是一个用于 demo 的聊天助手。"
    "请基于用户输入、项目级指令、项目 stable facts、会话历史、当前会话工作记忆、相关会话摘要和搜索上下文生成简洁回答。"
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
        stable_facts: Optional[list[str]] = None,
        working_memory: Optional[str] = None,
        related_session_digests: Optional[list[RelatedSessionDigest]] = None,
        project_name: Optional[str] = None,
        project_instruction: Optional[str] = None,
        search_results: Optional[list[SearchResult]] = None,
    ) -> LLMReply:
        normalized_search_results = search_results or []
        normalized_related_digests = related_session_digests or []
        normalized_stable_facts = stable_facts or []
        messages = self._build_messages(
            user_message=user_message,
            history=history,
            stable_facts=normalized_stable_facts,
            working_memory=working_memory,
            related_session_digests=normalized_related_digests,
            project_name=project_name,
            project_instruction=project_instruction,
            search_results=normalized_search_results,
        )

        if not self._settings.llm_api_key:
            return self._build_fallback_reply(
                user_message=user_message,
                history=history,
                stable_facts=normalized_stable_facts,
                working_memory=working_memory,
                related_session_digests=normalized_related_digests,
                project_name=project_name,
                project_instruction=project_instruction,
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
                stable_facts=normalized_stable_facts,
                working_memory=working_memory,
                related_session_digests=normalized_related_digests,
                project_name=project_name,
                project_instruction=project_instruction,
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
                stable_facts=normalized_stable_facts,
                working_memory=working_memory,
                related_session_digests=normalized_related_digests,
                project_name=project_name,
                project_instruction=project_instruction,
                search_results=normalized_search_results,
                reason=f"provider_request_failed:{exc}",
            )
        except Exception as exc:
            if not self._settings.llm_fallback_enabled:
                raise RuntimeError(f"Failed to call LLM provider: {exc}") from exc
            return self._build_fallback_reply(
                user_message=user_message,
                history=history,
                stable_facts=normalized_stable_facts,
                working_memory=working_memory,
                related_session_digests=normalized_related_digests,
                project_name=project_name,
                project_instruction=project_instruction,
                search_results=normalized_search_results,
                reason=f"unexpected_error:{exc}",
            )

    def _build_messages(
        self,
        user_message: str,
        history: list[MemoryMessage],
        stable_facts: list[str],
        working_memory: Optional[str],
        related_session_digests: list[RelatedSessionDigest],
        project_name: Optional[str],
        project_instruction: Optional[str],
        search_results: list[SearchResult],
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        project_context = self._render_project_context(project_name, project_instruction)
        if project_context:
            messages.append({"role": "system", "content": project_context})

        stable_facts_context = self._render_stable_facts_context(stable_facts)
        if stable_facts_context:
            messages.append({"role": "system", "content": stable_facts_context})

        if working_memory:
            messages.append(
                {
                    "role": "system",
                    "content": f"当前会话 working_memory：\n{working_memory}",
                }
            )

        if related_session_digests:
            messages.append(
                {
                    "role": "system",
                    "content": self._render_related_session_digests(related_session_digests),
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

    def _render_project_context(
        self,
        project_name: Optional[str],
        project_instruction: Optional[str],
    ) -> Optional[str]:
        if not project_name and not project_instruction:
            return None

        lines = ["当前会话所属项目信息："]
        if project_name:
            lines.append(f"项目名称：{project_name}")
        if project_instruction:
            lines.append(f"项目级 instruction：{project_instruction}")
        return "\n".join(lines)

    def _render_stable_facts_context(self, stable_facts: list[str]) -> Optional[str]:
        if not stable_facts:
            return None

        lines = ["当前项目 active stable facts / saved memories："]
        for index, item in enumerate(stable_facts, start=1):
            lines.append(f"{index}. {item}")
        return "\n".join(lines)

    def _render_related_session_digests(
        self,
        related_session_digests: list[RelatedSessionDigest],
    ) -> str:
        lines = ["以下是其他可读会话的 session_digest："]
        for index, item in enumerate(related_session_digests, start=1):
            source_label = "同项目" if item.source_scope == "project" else "外部可访问"
            lines.append(
                f"{index}. {source_label}会话《{item.session_title}》({item.session_id[:8]})：{item.content}"
            )
        return "\n".join(lines)

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
        stable_facts: list[str],
        working_memory: Optional[str],
        related_session_digests: list[RelatedSessionDigest],
        project_name: Optional[str],
        project_instruction: Optional[str],
        search_results: list[SearchResult],
        reason: str,
    ) -> LLMReply:
        parts = [
            "当前未能稳定调用在线模型，因此返回本地降级回复，方便继续联调整体链路。",
            f"用户消息：{user_message}",
        ]

        if project_name:
            parts.append(f"当前项目：{project_name}")
        if project_instruction:
            parts.append(f"项目级 instruction：{project_instruction}")
        if stable_facts:
            parts.append(f"项目 stable facts 数量：{len(stable_facts)}")

        if history:
            parts.append(f"已读取最近上下文条数：{len(history)}")

        if working_memory:
            parts.append(f"当前会话 working_memory：{working_memory}")

        if related_session_digests:
            parts.append(f"相关 session_digest 数量：{len(related_session_digests)}")

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

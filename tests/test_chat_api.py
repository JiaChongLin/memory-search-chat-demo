import pytest
from fastapi.testclient import TestClient

from backend.app.db.models import ChatSession
from backend.app.services.llm_service import LLMReply, LLMService
from backend.app.services.search_service import SearchResult, SearchService


def test_chat_first_request_returns_session_and_reply(client: TestClient) -> None:
    response = client.post("/api/chat", json={"message": "hello demo"})

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    assert data["reply"]
    assert data["used_live_model"] is False
    assert data["fallback_reason"] == "missing_api_key"
    assert data["search_used"] is False
    assert isinstance(data["sources"], list)
    assert data["context_scope"] == "open"
    assert data["related_summary_count"] == 0
    assert data["title"] == "hello demo"
    assert data["working_memory"] is None
    assert data["session_digest"]


def test_chat_reuses_existing_session(client: TestClient) -> None:
    first_response = client.post("/api/chat", json={"message": "remember my name is tom"})
    first_data = first_response.json()

    second_response = client.post(
        "/api/chat",
        json={
            "message": "what did I just say",
            "session_id": first_data["session_id"],
        },
    )

    assert second_response.status_code == 200
    second_data = second_response.json()
    assert second_data["session_id"] == first_data["session_id"]
    assert second_data["reply"]
    assert second_data["context_scope"] == "open"
    assert second_data["related_summary_count"] == 0
    assert second_data["title"] == first_data["title"]
    assert second_data["session_digest"]


def test_chat_returns_search_sources_when_search_hits(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_search(_: SearchService, __: str) -> list[SearchResult]:
        return [
            SearchResult(
                title="Example News",
                url="https://example.com/news",
                snippet="Example snippet.",
            )
        ]

    monkeypatch.setattr(SearchService, "search", fake_search)

    response = client.post(
        "/api/chat",
        json={"message": "today latest ai news"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["search_triggered"] is True
    assert data["search_used"] is True
    assert data["sources"][0]["title"] == "Example News"
    assert data["context_scope"] == "open"
    assert data["title"] == "today latest ai news"


def test_chat_injects_project_instruction_and_stable_facts_for_project_session(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_response = client.post(
        "/api/projects",
        json={
            "name": "Roadmap Project",
            "instruction": "Always answer like a product lead and keep bullets crisp.",
            "access_mode": "open",
        },
    )
    project_id = project_response.json()["id"]
    client.post(
        f"/api/projects/{project_id}/stable-facts",
        json={"content": "Budget ceiling remains 2 million CNY for this quarter."},
    )
    client.post(
        f"/api/projects/{project_id}/stable-facts",
        json={"content": "Default deliverables should be written in Chinese."},
    )
    session_id = client.post(
        "/api/sessions",
        json={"title": "Project chat", "project_id": project_id},
    ).json()["id"]

    captured = {}

    def fake_generate_reply(
        self,
        user_message,
        history,
        stable_facts=None,
        working_memory=None,
        related_session_digests=None,
        project_name=None,
        project_instruction=None,
        search_results=None,
    ):
        captured["project_name"] = project_name
        captured["project_instruction"] = project_instruction
        captured["stable_facts"] = stable_facts
        return LLMReply(content="stub reply", used_live_model=False, fallback_reason="captured")

    monkeypatch.setattr(LLMService, "generate_reply", fake_generate_reply)

    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "help me scope the launch"},
    )

    assert response.status_code == 200
    assert captured["project_name"] == "Roadmap Project"
    assert captured["project_instruction"] == "Always answer like a product lead and keep bullets crisp."
    assert set(captured["stable_facts"] or []) == {
        "Budget ceiling remains 2 million CNY for this quarter.",
        "Default deliverables should be written in Chinese.",
    }


def test_chat_passes_related_session_title_with_digest(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = client.post(
        "/api/projects",
        json={"name": "Shared Project", "access_mode": "project_only"},
    ).json()["id"]

    source_session_id = client.post(
        "/api/sessions",
        json={"title": "正确标题", "project_id": project_id},
    ).json()["id"]
    target_session_id = client.post(
        "/api/sessions",
        json={"title": "当前会话", "project_id": project_id},
    ).json()["id"]

    assert client.post(
        "/api/chat",
        json={"session_id": source_session_id, "message": "hello from source"},
    ).status_code == 200

    captured = {}

    def fake_generate_reply(
        self,
        user_message,
        history,
        stable_facts=None,
        working_memory=None,
        related_session_digests=None,
        project_name=None,
        project_instruction=None,
        search_results=None,
    ):
        captured["related_session_digests"] = related_session_digests or []
        return LLMReply(content="stub reply", used_live_model=False, fallback_reason="captured")

    monkeypatch.setattr(LLMService, "generate_reply", fake_generate_reply)

    response = client.post(
        "/api/chat",
        json={"session_id": target_session_id, "message": "同项目另一个会话标题是什么？"},
    )

    assert response.status_code == 200
    assert len(captured["related_session_digests"]) == 1
    related = captured["related_session_digests"][0]
    assert related.session_id == source_session_id
    assert related.session_title == "正确标题"


def test_chat_excludes_inactive_or_deleted_stable_facts_from_context(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = client.post(
        "/api/projects",
        json={"name": "Memory Project", "access_mode": "open"},
    ).json()["id"]

    active_fact = client.post(
        f"/api/projects/{project_id}/stable-facts",
        json={"content": "Always keep references short and actionable."},
    ).json()
    archived_fact = client.post(
        f"/api/projects/{project_id}/stable-facts",
        json={"content": "This fact will be archived."},
    ).json()
    deleted_fact = client.post(
        f"/api/projects/{project_id}/stable-facts",
        json={"content": "This fact will be deleted."},
    ).json()

    client.patch(
        f"/api/projects/{project_id}/stable-facts/{archived_fact['id']}",
        json={"status": "archived"},
    )
    client.delete(f"/api/projects/{project_id}/stable-facts/{deleted_fact['id']}")

    session_id = client.post(
        "/api/sessions",
        json={"title": "Memory chat", "project_id": project_id},
    ).json()["id"]

    captured = {}

    def fake_generate_reply(
        self,
        user_message,
        history,
        stable_facts=None,
        working_memory=None,
        related_session_digests=None,
        project_name=None,
        project_instruction=None,
        search_results=None,
    ):
        captured["stable_facts"] = stable_facts
        return LLMReply(content="stub reply", used_live_model=False, fallback_reason="captured")

    monkeypatch.setattr(LLMService, "generate_reply", fake_generate_reply)

    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "follow the saved rules"},
    )

    assert response.status_code == 200
    assert captured["stable_facts"] == [active_fact["content"]]


def test_chat_does_not_inject_project_prompt_or_stable_facts_for_unassigned_session(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = client.post(
        "/api/sessions",
        json={"title": "Standalone chat"},
    ).json()["id"]

    captured = {}

    def fake_generate_reply(
        self,
        user_message,
        history,
        stable_facts=None,
        working_memory=None,
        related_session_digests=None,
        project_name=None,
        project_instruction=None,
        search_results=None,
    ):
        captured["project_name"] = project_name
        captured["project_instruction"] = project_instruction
        captured["stable_facts"] = stable_facts
        return LLMReply(content="stub reply", used_live_model=False, fallback_reason="captured")

    monkeypatch.setattr(LLMService, "generate_reply", fake_generate_reply)

    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "just answer normally"},
    )

    assert response.status_code == 200
    assert captured == {
        "project_name": None,
        "project_instruction": None,
        "stable_facts": [],
    }


def test_archived_session_cannot_continue_chatting(client: TestClient) -> None:
    create_response = client.post("/api/sessions", json={"title": "Archive me"})
    session_id = create_response.json()["id"]
    assert client.post(f"/api/sessions/{session_id}/archive").status_code == 200

    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "still there?"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Archived sessions cannot continue chatting."


def test_deleted_session_cannot_be_recreated_by_chat(client: TestClient) -> None:
    create_response = client.post("/api/sessions", json={"title": "Delete me"})
    session_id = create_response.json()["id"]
    assert client.delete(f"/api/sessions/{session_id}").status_code == 200

    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "come back"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Session not found."


def test_chat_auto_generates_title_for_untitled_session(
    client: TestClient,
    session_local,
) -> None:
    create_response = client.post("/api/sessions", json={"title": None})
    session_id = create_response.json()["id"]

    response = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "帮我总结一下这个项目的权限边界和跨项目访问规则",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"]
    assert data["title"].startswith("帮我总结一下这个项目的权限边界")

    with session_local() as db:
        session = db.get(ChatSession, session_id)
        assert session is not None
        assert session.title == data["title"]


def test_chat_does_not_override_existing_manual_title(
    client: TestClient,
    session_local,
) -> None:
    create_response = client.post("/api/sessions", json={"title": "Manual title"})
    session_id = create_response.json()["id"]

    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "generate something else"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Manual title"

    with session_local() as db:
        session = db.get(ChatSession, session_id)
        assert session is not None
        assert session.title == "Manual title"


def test_chat_updates_session_message_metadata(client: TestClient, session_local) -> None:
    create_response = client.post("/api/sessions", json={"title": "Metadata"})
    session_id = create_response.json()["id"]

    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "track session metadata"},
    )

    assert response.status_code == 200

    with session_local() as db:
        session = db.get(ChatSession, session_id)
        assert session is not None
        assert session.message_count == 2
        assert session.last_message_at is not None

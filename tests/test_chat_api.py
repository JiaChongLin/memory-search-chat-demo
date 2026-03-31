import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.models import ChatSession
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

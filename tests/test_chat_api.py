import pytest
from fastapi.testclient import TestClient

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

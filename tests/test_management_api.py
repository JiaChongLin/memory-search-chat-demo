import pytest
from typing import Optional
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.services.llm_service import LLMReply, LLMService
from backend.app.services.search_service import SearchResult, SearchService

from backend.app.db.models import (
    ChatMessage,
    ChatSession,
    Project,
    ProjectStableFact,
    SessionSummary,
)


def test_create_project_returns_instruction(client: TestClient) -> None:
    response = client.post(
        "/api/projects",
        json={
            "name": "Demo Project",
            "description": "New access model project",
            "instruction": "Always answer as a product copilot.",
            "access_mode": "project_only",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "Demo Project"
    assert data["instruction"] == "Always answer as a product copilot."
    assert data["access_mode"] == "project_only"
    assert data["status"] == "active"


def test_get_and_list_projects_include_instruction(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Instruction Project",
            "instruction": "Prefer concise implementation plans.",
            "access_mode": "open",
        },
    )
    project_id = create_response.json()["id"]

    get_response = client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 200
    assert get_response.json()["instruction"] == "Prefer concise implementation plans."

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    matching = [item for item in list_response.json() if item["id"] == project_id]
    assert matching
    assert matching[0]["instruction"] == "Prefer concise implementation plans."


def test_patch_project_updates_name(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={"name": "Original Name", "access_mode": "open"},
    )
    project_id = create_response.json()["id"]

    response = client.patch(
        f"/api/projects/{project_id}",
        json={"name": "Renamed Project"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Project"
    assert response.json()["access_mode"] == "open"


def test_patch_project_updates_description(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={"name": "Project A", "description": None, "access_mode": "open"},
    )
    project_id = create_response.json()["id"]

    response = client.patch(
        f"/api/projects/{project_id}",
        json={"description": "Updated description"},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Updated description"


def test_patch_project_updates_instruction(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={"name": "Project A", "instruction": None, "access_mode": "open"},
    )
    project_id = create_response.json()["id"]

    response = client.patch(
        f"/api/projects/{project_id}",
        json={"instruction": "Default to Chinese and keep answers brief."},
    )

    assert response.status_code == 200
    assert response.json()["instruction"] == "Default to Chinese and keep answers brief."


def test_patch_project_does_not_allow_access_mode_update(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={"name": "Locked Mode", "access_mode": "project_only"},
    )
    project_id = create_response.json()["id"]

    response = client.patch(
        f"/api/projects/{project_id}",
        json={"name": "Locked Mode 2", "access_mode": "open"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Locked Mode 2"
    assert data["access_mode"] == "project_only"


def test_patch_project_returns_404_when_missing(client: TestClient) -> None:
    response = client.patch(
        "/api/projects/99999",
        json={"name": "Missing"},
    )

    assert response.status_code == 404


def test_project_stable_facts_crud(client: TestClient) -> None:
    project_id = client.post(
        "/api/projects",
        json={"name": "Stable Facts Project", "access_mode": "open"},
    ).json()["id"]

    empty_response = client.get(f"/api/projects/{project_id}/stable-facts")
    assert empty_response.status_code == 200
    assert empty_response.json() == []

    create_response = client.post(
        f"/api/projects/{project_id}/stable-facts",
        json={"content": "User prefers concise Chinese answers."},
    )
    assert create_response.status_code == 201
    fact = create_response.json()
    assert fact["project_id"] == project_id
    assert fact["status"] == "active"

    list_response = client.get(f"/api/projects/{project_id}/stable-facts")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["content"] == "User prefers concise Chinese answers."

    update_response = client.patch(
        f"/api/projects/{project_id}/stable-facts/{fact['id']}",
        json={"content": "User prefers concise Chinese answers with action items."},
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"] == "User prefers concise Chinese answers with action items."

    archive_response = client.patch(
        f"/api/projects/{project_id}/stable-facts/{fact['id']}",
        json={"status": "archived"},
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    active_only_response = client.get(f"/api/projects/{project_id}/stable-facts")
    assert active_only_response.status_code == 200
    assert active_only_response.json() == []

    include_archived_response = client.get(
        f"/api/projects/{project_id}/stable-facts",
        params={"include_archived": "true"},
    )
    assert include_archived_response.status_code == 200
    assert len(include_archived_response.json()) == 1
    assert include_archived_response.json()[0]["status"] == "archived"

    delete_response = client.delete(f"/api/projects/{project_id}/stable-facts/{fact['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["stable_fact_id"] == fact["id"]

    final_list_response = client.get(
        f"/api/projects/{project_id}/stable-facts",
        params={"include_archived": "true"},
    )
    assert final_list_response.status_code == 200
    assert final_list_response.json() == []


def test_create_session_under_project(client: TestClient) -> None:
    project_response = client.post(
        "/api/projects",
        json={"name": "Project A", "access_mode": "open"},
    )
    project_id = project_response.json()["id"]

    response = client.post(
        "/api/sessions",
        json={
            "title": "Project session",
            "project_id": project_id,
            "is_private": True,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"]
    assert data["title"] == "Project session"
    assert data["project_id"] == project_id
    assert data["is_private"] is True
    assert data["status"] == "active"


def test_patch_session_can_toggle_is_private_bidirectionally(client: TestClient) -> None:
    create_response = client.post(
        "/api/sessions",
        json={"title": "Privacy toggle", "is_private": False},
    )
    session_id = create_response.json()["id"]

    to_private = client.patch(
        f"/api/sessions/{session_id}",
        json={"is_private": True},
    )
    assert to_private.status_code == 200
    assert to_private.json()["is_private"] is True

    to_shared = client.patch(
        f"/api/sessions/{session_id}",
        json={"is_private": False},
    )
    assert to_shared.status_code == 200
    assert to_shared.json()["is_private"] is False


def test_archive_session_hides_it_from_default_list(client: TestClient) -> None:
    create_response = client.post("/api/sessions", json={"title": "Archive me"})
    session_id = create_response.json()["id"]

    archive_response = client.post(f"/api/sessions/{session_id}/archive")

    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    list_response = client.get("/api/sessions")
    assert list_response.status_code == 200
    assert session_id not in {item["id"] for item in list_response.json()}

    archived_list_response = client.get(
        "/api/sessions",
        params={"include_archived": "true"},
    )
    assert archived_list_response.status_code == 200
    assert session_id in {item["id"] for item in archived_list_response.json()}


def test_get_session_messages_returns_messages_in_order(client: TestClient) -> None:
    create_response = client.post("/api/sessions", json={"title": "History"})
    session_id = create_response.json()["id"]

    assert client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "first question"},
    ).status_code == 200
    assert client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "second question"},
    ).status_code == 200

    response = client.get(f"/api/sessions/{session_id}/messages")

    assert response.status_code == 200
    payload = response.json()
    assert [item["role"] for item in payload] == ["user", "assistant", "user", "assistant"]
    assert payload[0]["content"] == "first question"
    assert payload[2]["content"] == "second question"


def test_get_session_messages_returns_persisted_assistant_sources(
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
    session_id = response.json()["session_id"]

    history_response = client.get(f"/api/sessions/{session_id}/messages")

    assert history_response.status_code == 200
    payload = history_response.json()
    assert payload[0]["role"] == "user"
    assert payload[0]["sources"] == []
    assert payload[1]["role"] == "assistant"
    assert payload[1]["sources"] == [
        {
            "title": "Example News",
            "url": "https://example.com/news",
            "snippet": "Example snippet.",
        }
    ]


def test_get_session_messages_defaults_sources_to_empty_list_for_legacy_rows(
    client: TestClient,
    session_local,
) -> None:
    session_id = client.post("/api/sessions", json={"title": "Legacy history"}).json()["id"]

    with session_local() as db:
        db.add(ChatMessage(session_id=session_id, role="assistant", content="legacy", sources_json=None))
        db.commit()

    response = client.get(f"/api/sessions/{session_id}/messages")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["sources"] == []


def test_get_session_summary_returns_working_memory_and_session_digest(client: TestClient) -> None:
    create_response = client.post("/api/sessions", json={"title": "Summary history"})
    session_id = create_response.json()["id"]

    for message in [
        "first summary seed",
        "second summary seed",
        "third summary seed",
        "fourth summary seed",
    ]:
        assert client.post(
            "/api/chat",
            json={"session_id": session_id, "message": message},
        ).status_code == 200

    response = client.get(f"/api/sessions/{session_id}/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert isinstance(payload["working_memory"], str)
    assert payload["working_memory"]
    assert isinstance(payload["session_digest"], str)
    assert payload["session_digest"]
    assert payload["summary_updated_at"] is not None


def test_patch_session_updates_title(client: TestClient) -> None:
    create_response = client.post("/api/sessions", json={"title": "Old title"})
    session_id = create_response.json()["id"]

    response = client.patch(
        f"/api/sessions/{session_id}",
        json={"title": "Renamed session"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Renamed session"

    get_response = client.get(f"/api/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Renamed session"


def test_delete_session_hard_deletes_session_messages_and_summary(
    client: TestClient,
    session_local,
) -> None:
    create_response = client.post("/api/sessions", json={"title": "Delete me"})
    session_id = create_response.json()["id"]
    chat_response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "remember this session"},
    )
    assert chat_response.status_code == 200

    delete_response = client.delete(f"/api/sessions/{session_id}")

    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True
    assert delete_response.json()["session_id"] == session_id

    get_response = client.get(f"/api/sessions/{session_id}")
    assert get_response.status_code == 404

    messages_response = client.get(f"/api/sessions/{session_id}/messages")
    assert messages_response.status_code == 404

    with session_local() as db:
        assert db.get(ChatSession, session_id) is None
        assert db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        ).first() is None
        assert db.scalars(
            select(SessionSummary).where(SessionSummary.session_id == session_id)
        ).first() is None


def test_delete_project_cascades_to_sessions_messages_summaries_and_stable_facts(
    client: TestClient,
    session_local,
) -> None:
    project_response = client.post(
        "/api/projects",
        json={"name": "Cascade Project", "access_mode": "project_only"},
    )
    project_id = project_response.json()["id"]

    stable_fact_id = client.post(
        f"/api/projects/{project_id}/stable-facts",
        json={"content": "Keep answers aligned with roadmap commitments."},
    ).json()["id"]

    session_a = client.post(
        "/api/sessions",
        json={"title": "A", "project_id": project_id},
    ).json()["id"]
    session_b = client.post(
        "/api/sessions",
        json={"title": "B", "project_id": project_id},
    ).json()["id"]

    assert client.post("/api/chat", json={"session_id": session_a, "message": "alpha"}).status_code == 200
    assert client.post("/api/chat", json={"session_id": session_b, "message": "beta"}).status_code == 200

    delete_response = client.delete(f"/api/projects/{project_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True
    assert delete_response.json()["project_id"] == project_id

    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert client.get(f"/api/sessions/{session_a}").status_code == 404
    assert client.get(f"/api/sessions/{session_b}").status_code == 404

    with session_local() as db:
        assert db.get(Project, project_id) is None
        assert db.get(ProjectStableFact, stable_fact_id) is None
        assert db.get(ChatSession, session_a) is None
        assert db.get(ChatSession, session_b) is None
        assert db.scalars(
            select(ChatMessage).where(ChatMessage.session_id.in_([session_a, session_b]))
        ).first() is None
        assert db.scalars(
            select(SessionSummary).where(SessionSummary.session_id.in_([session_a, session_b]))
        ).first() is None


def test_move_session_out_of_project(client: TestClient) -> None:
    project_response = client.post(
        "/api/projects",
        json={"name": "Project A", "access_mode": "project_only"},
    )
    project_id = project_response.json()["id"]
    session_response = client.post(
        "/api/sessions",
        json={"title": "Bound", "project_id": project_id},
    )
    session_id = session_response.json()["id"]

    move_response = client.post(
        f"/api/sessions/{session_id}/move",
        json={"project_id": None},
    )

    assert move_response.status_code == 200
    assert move_response.json()["project_id"] is None


def test_regenerate_latest_turn_replaces_last_assistant_instead_of_appending(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies = [
        LLMReply(content="first reply", used_live_model=False, fallback_reason="captured"),
        LLMReply(content="regenerated reply", used_live_model=False, fallback_reason="captured"),
    ]

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
        return replies.pop(0)

    monkeypatch.setattr(LLMService, "generate_reply", fake_generate_reply)

    session_id = client.post("/api/sessions", json={"title": "Latest turn"}).json()["id"]
    first_response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "original question"},
    )
    assert first_response.status_code == 200

    regenerate_response = client.post(f"/api/sessions/{session_id}/latest-turn/regenerate")

    assert regenerate_response.status_code == 200
    assert regenerate_response.json()["reply"] == "regenerated reply"

    messages = client.get(f"/api/sessions/{session_id}/messages").json()
    assert len(messages) == 2
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "original question"
    assert messages[1]["content"] == "regenerated reply"

    session = client.get(f"/api/sessions/{session_id}").json()
    assert session["message_count"] == 2


def test_edit_latest_turn_replaces_last_user_and_assistant_and_rebuilds_summary(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies = [
        LLMReply(content="original reply", used_live_model=False, fallback_reason="captured"),
        LLMReply(content="edited reply", used_live_model=False, fallback_reason="captured"),
    ]

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
        return replies.pop(0)

    monkeypatch.setattr(LLMService, "generate_reply", fake_generate_reply)

    session_id = client.post("/api/sessions", json={"title": "Editable turn"}).json()["id"]
    first_response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "original latest question"},
    )
    assert first_response.status_code == 200

    edit_response = client.post(
        f"/api/sessions/{session_id}/latest-turn/edit",
        json={"message": "edited latest question"},
    )

    assert edit_response.status_code == 200
    assert edit_response.json()["reply"] == "edited reply"

    messages = client.get(f"/api/sessions/{session_id}/messages").json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "edited latest question"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "edited reply"
    assert all("original latest question" not in item["content"] for item in messages)

    summary = client.get(f"/api/sessions/{session_id}/summary").json()
    assert summary["session_digest"] is not None
    assert "edited latest question" in summary["session_digest"]
    assert "original latest question" not in summary["session_digest"]

    session = client.get(f"/api/sessions/{session_id}").json()
    assert session["message_count"] == 2


@pytest.mark.parametrize(
    ("path_suffix", "payload"),
    [
        ("edit", {"message": "edited latest question"}),
        ("regenerate", None),
    ],
)
def test_latest_turn_action_failure_rolls_back_to_original_history(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path_suffix: str,
    payload: Optional[dict[str, str]],
) -> None:
    call_count = {"value": 0}

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
        call_count["value"] += 1
        if call_count["value"] == 1:
            return LLMReply(
                content="original reply",
                used_live_model=False,
                fallback_reason="captured",
            )
        raise RuntimeError("simulated latest-turn rerun failure")

    monkeypatch.setattr(LLMService, "generate_reply", fake_generate_reply)

    session_id = client.post("/api/sessions", json={"title": "Rollback safety"}).json()["id"]
    first_response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "original latest question"},
    )
    assert first_response.status_code == 200

    summary_before = client.get(f"/api/sessions/{session_id}/summary").json()

    with pytest.raises(RuntimeError, match="simulated latest-turn rerun failure"):
        if payload is None:
            client.post(f"/api/sessions/{session_id}/latest-turn/{path_suffix}")
        else:
            client.post(
                f"/api/sessions/{session_id}/latest-turn/{path_suffix}",
                json=payload,
            )

    messages = client.get(f"/api/sessions/{session_id}/messages").json()
    assert len(messages) == 2
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "original latest question"
    assert messages[1]["content"] == "original reply"

    summary_after = client.get(f"/api/sessions/{session_id}/summary").json()
    assert summary_after["working_memory"] == summary_before["working_memory"]
    assert summary_after["session_digest"] == summary_before["session_digest"]
    assert summary_after["summary_updated_at"] == summary_before["summary_updated_at"]

    session = client.get(f"/api/sessions/{session_id}").json()
    assert session["message_count"] == 2

def test_regenerate_latest_turn_returns_409_when_no_latest_turn(client: TestClient) -> None:
    session_id = client.post("/api/sessions", json={"title": "Empty latest turn"}).json()["id"]

    response = client.post(f"/api/sessions/{session_id}/latest-turn/regenerate")

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "No latest turn is available for regenerate or edit."


def test_edit_latest_turn_returns_409_when_tail_is_not_user_assistant(
    client: TestClient,
    session_local,
) -> None:
    session_id = client.post("/api/sessions", json={"title": "Broken tail"}).json()["id"]

    with session_local() as db:
        db.add(ChatMessage(session_id=session_id, role="user", content="first user", sources_json="[]"))
        db.add(ChatMessage(session_id=session_id, role="user", content="second user", sources_json="[]"))
        db.commit()

    response = client.post(
        f"/api/sessions/{session_id}/latest-turn/edit",
        json={"message": "edited question"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Latest turn must end with a user -> assistant pair."


@pytest.mark.parametrize("session_id_factory", ["missing", "archived"])
def test_latest_turn_actions_require_existing_active_session(
    client: TestClient,
    session_id_factory: str,
) -> None:
    if session_id_factory == "missing":
        session_id = "missing-session"
    else:
        session_id = client.post("/api/sessions", json={"title": "Archive me"}).json()["id"]
        assert client.post(f"/api/sessions/{session_id}/archive").status_code == 200

    response = client.post(f"/api/sessions/{session_id}/latest-turn/regenerate")

    assert response.status_code == 409












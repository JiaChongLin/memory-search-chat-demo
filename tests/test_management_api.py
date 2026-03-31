from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.models import ChatMessage, ChatSession, Project, SessionSummary


def test_create_project(client: TestClient) -> None:
    response = client.post(
        "/api/projects",
        json={
            "name": "Demo Project",
            "description": "New access model project",
            "access_mode": "project_only",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "Demo Project"
    assert data["access_mode"] == "project_only"
    assert data["status"] == "active"


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


def test_delete_project_cascades_to_sessions_messages_and_summaries(
    client: TestClient,
    session_local,
) -> None:
    project_response = client.post(
        "/api/projects",
        json={"name": "Cascade Project", "access_mode": "project_only"},
    )
    project_id = project_response.json()["id"]

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

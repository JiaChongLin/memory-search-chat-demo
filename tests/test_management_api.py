from fastapi.testclient import TestClient


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


def test_soft_delete_session_hides_it_from_default_reads(client: TestClient) -> None:
    create_response = client.post("/api/sessions", json={"title": "Delete me"})
    session_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/sessions/{session_id}")

    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"

    list_response = client.get("/api/sessions")
    assert list_response.status_code == 200
    assert session_id not in {item["id"] for item in list_response.json()}

    get_response = client.get(f"/api/sessions/{session_id}")
    assert get_response.status_code == 404


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

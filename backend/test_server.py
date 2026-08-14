import pytest
from fastapi.testclient import TestClient
from server import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_root(client):
    response = client.get("/api")
    assert response.status_code == 200
    assert "operando" in response.json()["message"]

def test_get_games(client):
    response = client.get("/api/games")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_game_suggestion(client):
    response = client.post("/api/games", json={
        "title": "Hades II",
        "genre": "Roguelike",
        "description": "Jogaço pra testar reflexos",
        "platform": "PC",
        "submitted_by": "TestUser"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Hades II"
    assert data["votes"] == 0

def test_get_clips(client):
    response = client.get("/api/clips")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_admin_login_failure(client):
    response = client.post("/api/admin/login", json={"password": "wrongpassword"})
    assert response.status_code == 401

def test_admin_login_success(client):
    response = client.post("/api/admin/login", json={"password": "nethzzzz2026"})
    assert response.status_code == 200
    assert response.json()["success"] is True

import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

def test_public_collections_and_root():
    s = requests.Session()
    assert s.get(f"{BASE_URL}/api/").json()["message"]
    for resource in ("games", "clips", "polls", "schedule"):
        r = s.get(f"{BASE_URL}/api/{resource}")
        assert r.status_code == 200 and isinstance(r.json(), list) and r.json()

def test_game_create_vote_and_comment():
    s = requests.Session()
    payload = {"title":"TEST_API game", "genre":"Action", "description":"TEST desc", "submitted_by":"TEST_user"}
    game = s.post(f"{BASE_URL}/api/games", json=payload).json()
    assert game["title"] == payload["title"]
    gid, before = game["id"], game["votes"]
    assert s.post(f"{BASE_URL}/api/games/{gid}/vote").json()["votes"] == before + 1
    c = s.post(f"{BASE_URL}/api/comments", json={"target_id":gid,"target_type":"game","author":"TEST_user","content":"TEST comment"})
    assert c.status_code == 200
    assert any(x["content"] == "TEST comment" for x in s.get(f"{BASE_URL}/api/comments/{gid}").json())

def test_clip_like_and_poll_vote():
    s = requests.Session()
    clip = s.post(f"{BASE_URL}/api/clips", json={"title":"TEST clip","url":"https://youtube.com/watch?v=test","submitted_by":"TEST_user"}).json()
    assert s.post(f"{BASE_URL}/api/clips/{clip['id']}/like").json()["likes"] == clip["likes"] + 1
    poll = s.get(f"{BASE_URL}/api/polls").json()[0]
    assert s.post(f"{BASE_URL}/api/polls/{poll['id']}/vote?option_index=0").json()["options"][0]["votes"] == poll["options"][0]["votes"] + 1

def test_auth_and_reports_protection():
    s = requests.Session()
    assert s.get(f"{BASE_URL}/api/reports").status_code == 401
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email":"admin@nethzzzz.gg","password":"NethHQ#2026!"})
    assert r.status_code == 200 and r.cookies.get("access_token")
    assert s.get(f"{BASE_URL}/api/auth/me").status_code == 200
    assert s.get(f"{BASE_URL}/api/reports").status_code == 200

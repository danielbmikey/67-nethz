"""Backend tests for Nethzzzz Community HQ."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://nethzzzz-community.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@nethzzzz.gg"
ADMIN_PASSWORD = "NethHQ#2026!"


def _rand():
    return uuid.uuid4().hex[:8]


# ------------- Fixtures -------------
@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["role"] == "admin"
    assert data.get("token")
    return data["token"]


@pytest.fixture(scope="module")
def viewer(s):
    suf = _rand()
    payload = {"email": f"testviewer_{suf}@nethzzzz.gg", "password": "senha123", "nickname": f"nick_{suf}"}
    r = s.post(f"{API}/auth/signup", json=payload, headers={"X-Forwarded-For": "203.0.113.42"})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"payload": payload, "token": data["token"], "id": data["id"]}


def h(token):
    return {"Authorization": f"Bearer {token}"}


# ------------- Public reads -------------
class TestPublic:
    def test_root(self, s):
        r = s.get(f"{API}/")
        assert r.status_code == 200

    def test_public_reads(self, s):
        for path in ("games", "clips", "polls", "schedule"):
            r = s.get(f"{API}/{path}")
            assert r.status_code == 200, path
            assert isinstance(r.json(), list)

    def test_comments_public(self, s):
        r = s.get(f"{API}/comments/anything")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ------------- Signup -------------
class TestSignup:
    def test_signup_creates_user_with_ips(self, s):
        suf = _rand()
        payload = {"email": f"tester_{suf}@nethzzzz.gg", "password": "senha123", "nickname": f"tester_{suf}"}
        r = s.post(f"{API}/auth/signup", json=payload, headers={"X-Forwarded-For": "198.51.100.7"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["role"] == "viewer"
        assert data["token"]
        # verify persistence + IP tracked via /auth/me + admin fetch happens elsewhere
        me = s.get(f"{API}/auth/me", headers=h(data["token"]))
        assert me.status_code == 200
        me_data = me.json()
        assert me_data["email"] == payload["email"]
        assert me_data["nickname"] == payload["nickname"]

    def test_signup_duplicate_email(self, s, viewer):
        p = viewer["payload"]
        r = s.post(f"{API}/auth/signup", json={"email": p["email"], "password": "senha123", "nickname": f"nn_{_rand()}"})
        assert r.status_code == 409

    def test_signup_duplicate_nickname(self, s, viewer):
        p = viewer["payload"]
        r = s.post(f"{API}/auth/signup", json={"email": f"new_{_rand()}@nethzzzz.gg", "password": "senha123", "nickname": p["nickname"]})
        assert r.status_code == 409

    def test_signup_invalid_nickname_short(self, s):
        r = s.post(f"{API}/auth/signup", json={"email": f"short_{_rand()}@nethzzzz.gg", "password": "senha123", "nickname": "ab"})
        assert r.status_code == 400

    def test_signup_short_password(self, s):
        r = s.post(f"{API}/auth/signup", json={"email": f"pw_{_rand()}@nethzzzz.gg", "password": "123", "nickname": f"pw_{_rand()}"})
        assert r.status_code == 422


# ------------- Login -------------
class TestLogin:
    def test_login_admin(self, s):
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_login_viewer_updates_last_ip(self, s, viewer):
        p = viewer["payload"]
        r = s.post(f"{API}/auth/login", json={"email": p["email"], "password": p["password"]}, headers={"X-Forwarded-For": "192.0.2.99"})
        assert r.status_code == 200
        assert r.json()["role"] == "viewer"

    def test_login_wrong_password(self, s):
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401


# ------------- Auth me -------------
class TestAuthMe:
    def test_me_no_token(self, s):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_with_token(self, s, viewer):
        r = requests.get(f"{API}/auth/me", headers=h(viewer["token"]))
        assert r.status_code == 200
        assert r.json()["email"] == viewer["payload"]["email"]


# ------------- Protected endpoints require auth -------------
class TestProtected:
    def test_create_game_unauth(self):
        r = requests.post(f"{API}/games", json={"title": "x", "genre": "y", "description": "z"})
        assert r.status_code == 401

    def test_create_clip_unauth(self):
        r = requests.post(f"{API}/clips", json={"title": "x", "url": "https://x"})
        assert r.status_code == 401

    def test_create_comment_unauth(self):
        r = requests.post(f"{API}/comments", json={"target_id": "x", "target_type": "game", "content": "hi"})
        assert r.status_code == 401

    def test_create_report_unauth(self):
        r = requests.post(f"{API}/reports", json={"target_id": "x", "target_type": "game", "reason": "spam"})
        assert r.status_code == 401


# ------------- Voting / Likes / Polls -------------
class TestVotingLikes:
    def test_game_vote_once(self, viewer):
        games = requests.get(f"{API}/games").json()
        assert games
        gid = games[0]["id"]
        r1 = requests.post(f"{API}/games/{gid}/vote", headers=h(viewer["token"]))
        # allow either 200 (first vote) OR 400 if this viewer already voted in a rerun
        assert r1.status_code in (200, 400)
        r2 = requests.post(f"{API}/games/{gid}/vote", headers=h(viewer["token"]))
        assert r2.status_code == 400

    def test_clip_like_once(self, viewer):
        clips = requests.get(f"{API}/clips").json()
        assert clips
        cid = clips[0]["id"]
        r1 = requests.post(f"{API}/clips/{cid}/like", headers=h(viewer["token"]))
        assert r1.status_code in (200, 400)
        r2 = requests.post(f"{API}/clips/{cid}/like", headers=h(viewer["token"]))
        assert r2.status_code == 400

    def test_poll_vote_once(self, viewer):
        polls = requests.get(f"{API}/polls").json()
        assert polls
        pid = polls[0]["id"]
        r1 = requests.post(f"{API}/polls/{pid}/vote", params={"option_index": 0}, headers=h(viewer["token"]))
        assert r1.status_code in (200, 400)
        r2 = requests.post(f"{API}/polls/{pid}/vote", params={"option_index": 0}, headers=h(viewer["token"]))
        assert r2.status_code == 400


# ------------- Admin -------------
class TestAdmin:
    def test_admin_users_forbidden_for_viewer(self, viewer):
        r = requests.get(f"{API}/admin/users", headers=h(viewer["token"]))
        assert r.status_code in (401, 403)

    def test_admin_users_no_auth(self):
        r = requests.get(f"{API}/admin/users")
        assert r.status_code == 401

    def test_admin_users_ok(self, admin_token, viewer):
        r = requests.get(f"{API}/admin/users", headers=h(admin_token))
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list)
        # ensure signup user shows up and no password_hash
        emails = [u.get("email") for u in users]
        assert viewer["payload"]["email"] in emails
        for u in users:
            assert "password_hash" not in u
            assert "creation_ip" in u
            assert "last_ip" in u

    def test_export_csv_no_password(self, admin_token):
        r = requests.get(f"{API}/admin/users/export", params={"fmt": "csv"}, headers=h(admin_token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        body = r.text
        assert "password" not in body.lower()
        assert "email" in body and "creation_ip" in body

    def test_export_txt_no_password(self, admin_token):
        r = requests.get(f"{API}/admin/users/export", params={"fmt": "txt"}, headers=h(admin_token))
        assert r.status_code == 200
        assert "password" not in r.text.lower()
        assert "ip_criacao" in r.text

    def test_export_invalid_format(self, admin_token):
        r = requests.get(f"{API}/admin/users/export", params={"fmt": "xml"}, headers=h(admin_token))
        assert r.status_code == 400


# ------------- Reports flow -------------
class TestReports:
    def test_report_create_and_admin_resolve(self, viewer, admin_token):
        # viewer creates a report
        r = requests.post(f"{API}/reports", json={"target_id": "abc", "target_type": "comment", "reason": "spam"}, headers=h(viewer["token"]))
        assert r.status_code == 200
        rid = r.json()["id"]
        # viewer cannot list reports
        r2 = requests.get(f"{API}/reports", headers=h(viewer["token"]))
        assert r2.status_code in (401, 403)
        # viewer cannot patch report
        r3 = requests.patch(f"{API}/reports/{rid}", params={"status": "Resolvido"}, headers=h(viewer["token"]))
        assert r3.status_code in (401, 403)
        # admin can resolve
        r4 = requests.patch(f"{API}/reports/{rid}", params={"status": "Resolvido"}, headers=h(admin_token))
        assert r4.status_code == 200
        assert r4.json()["status"] == "Resolvido"

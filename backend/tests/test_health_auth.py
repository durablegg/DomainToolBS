from app.main import app


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_and_me(client, auth_headers):
    assert auth_headers["Authorization"].startswith("Bearer ")
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "root"
    assert r.json()["is_superuser"] is True


def test_me_without_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401

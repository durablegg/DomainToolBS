"""
密码历史校验回归测试：
- 修改密码必须满足条件（复杂度 + 不与当前/最近 3 次历史相同）
- 复用"上一个"或"前三次内"的密码应被拒绝
"""
from __future__ import annotations


def _bootstrap(client) -> str:
    r = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "root", "password": "P@ss1word", "display_name": "root"},
    )
    assert r.status_code == 200, r.text
    login = client.post(
        "/api/v1/auth/login", json={"username": "root", "password": "P@ss1word"}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _change(client, token, old_pwd, new_pwd):
    return client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": old_pwd, "new_password": new_pwd},
    )


def test_reuse_previous_password_rejected(client):
    token = _bootstrap(client)
    # A -> B
    assert _change(client, token, "P@ss1word", "New@1234").status_code == 200
    # B -> A（复用上一个密码）应被拒绝
    r = _change(client, token, "New@1234", "P@ss1word")
    assert r.status_code == 400, r.text
    assert "前" in r.json()["detail"]


def test_history_window_of_three(client):
    token = _bootstrap(client)
    # 依次改为 4 个新密码：A->B->C->D->E
    seq = ["P@ss1word", "B@ss1234", "C@ss1234", "D@ss1234", "E@ss1234"]
    for i in range(1, len(seq)):
        assert _change(client, token, seq[i - 1], seq[i]).status_code == 200
    # 当前为 E，历史最近 3 次 = [D, C, B]
    # 改回 B（落在最近 3 次内）应被拒绝
    r = _change(client, token, "E@ss1234", "B@ss1234")
    assert r.status_code == 400, r.text
    # 改回 A（已滑出最近 3 次窗口）应允许
    r2 = _change(client, token, "E@ss1234", "P@ss1word")
    assert r2.status_code == 200, r2.text


def test_same_as_current_rejected(client):
    token = _bootstrap(client)
    r = _change(client, token, "P@ss1word", "P@ss1word")
    assert r.status_code == 400
    assert "当前密码" in r.json()["detail"]


def test_weak_password_rejected(client):
    token = _bootstrap(client)
    r = _change(client, token, "P@ss1word", "abc123")
    assert r.status_code == 400

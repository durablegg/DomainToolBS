"""
授权范围仅可分配给「管理员」角色：
普通用户 / 审计员使用系统内置默认权限，前端不展示授权矩阵，后端亦拒绝配置。
"""
from __future__ import annotations

SCOPE_BODY = {
    "scopes": [
        {
            "domain_id": 1,
            "base_dn": "OU=Sales,DC=contoso,DC=com",
            "permissions": ["user:write"],
        }
    ]
}


def _super_headers(client) -> dict:
    r = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "root", "password": "P@ss1word", "display_name": "root"},
    )
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/auth/login", json={"username": "root", "password": "P@ss1word"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create(client, headers, username: str, role: str) -> int:
    r = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "username": username,
            "password": "P@ss1word",
            "display_name": username,
            "role": role,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_scopes_rejected_for_non_admin_roles(client):
    h = _super_headers(client)
    uid = _create(client, h, "u1", "user")
    aid = _create(client, h, "a1", "auditor")

    for target in (uid, aid):
        r = client.put(f"/api/v1/rbac/admins/{target}/scopes", json=SCOPE_BODY, headers=h)
        assert r.status_code == 400, r.text
        assert "默认权限" in r.json()["detail"]
        # 读取应返回空列表，不产生任何授权
        assert client.get(f"/api/v1/rbac/admins/{target}/scopes", headers=h).json() == []

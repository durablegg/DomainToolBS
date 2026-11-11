from app.core.security import hash_password
from app.db import SessionLocal
from app.models import AdminUser


def _ensure_delegate() -> int:
    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter_by(username="delegate").first()
        if admin is None:
            admin = AdminUser(
                username="delegate",
                display_name="Delegate",
                role="admin",
                is_superuser=False,
                is_active=True,
                password_hash=hash_password("Delegate@123"),
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return admin.id
    finally:
        db.close()


def _delegate_headers(client) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": "delegate", "password": "Delegate@123"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_permissions_matrix(auth_headers, client):
    r = client.get("/api/v1/rbac/permissions", headers=auth_headers)
    assert r.status_code == 200
    keys = {x["key"] for x in r.json()["resources"]}
    assert keys == {"user", "group", "computer", "ou"}


def test_list_admins_requires_superuser(auth_headers, client):
    _ensure_delegate()
    r = client.get("/api/v1/rbac/admins", headers=_delegate_headers(client))
    assert r.status_code == 403
    r2 = client.get("/api/v1/rbac/admins", headers=auth_headers)
    assert r2.status_code == 200
    assert any(a["username"] == "delegate" for a in r2.json())


def test_scope_crud(auth_headers, client):
    did = _ensure_delegate()
    # 多域后作用域需绑定域；先建一个域
    dr = client.post(
        "/api/v1/domains",
        json={"name": "d1", "host": "h", "port": 636, "use_ssl": True,
              "base_dn": "DC=contoso,DC=com", "bind_dn": "x", "bind_password": "p", "description": ""},
        headers=auth_headers,
    )
    assert dr.status_code == 200
    dom_id = dr.json()["id"]
    body = {
        "scopes": [
            {"domain_id": dom_id, "base_dn": "OU=Sales,DC=contoso,DC=com", "permissions": ["user:write", "user:reset_password"]}
        ]
    }
    r = client.put(f"/api/v1/rbac/admins/{did}/scopes", json=body, headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r2 = client.get(f"/api/v1/rbac/admins/{did}/scopes", headers=auth_headers)
    assert r2.json()[0]["base_dn"] == "OU=Sales,DC=contoso,DC=com"

    r3 = client.put(
        f"/api/v1/rbac/admins/{did}/scopes",
        json={"scopes": [{"domain_id": dom_id, "base_dn": "x", "permissions": ["bogus:act"]}]},
        headers=auth_headers,
    )
    assert r3.status_code == 400


def test_scope_requires_superuser_and_superuser_blocked(auth_headers, client):
    did = _ensure_delegate()
    # 委派管理员不能查看/修改授权
    r = client.get(f"/api/v1/rbac/admins/{did}/scopes", headers=_delegate_headers(client))
    assert r.status_code == 403
    # 超级管理员不可被配置作用域
    r2 = client.put(
        "/api/v1/rbac/admins/1/scopes",
        json={"scopes": [{"domain_id": 1, "base_dn": "OU=x,DC=contoso,DC=com", "permissions": ["user:write"]}]},
        headers=auth_headers,
    )
    assert r2.status_code == 400

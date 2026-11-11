"""域控 CA 证书导入 + 双通道 + 证书过期拦截的回归测试。

通过 monkeypatch `ldap_conn.test_connection` 避免真实 TLS 连接。
"""
from __future__ import annotations

import base64


def _super_headers(client) -> dict:
    client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "root", "password": "P@ss1word", "display_name": "root"},
    )
    r = client.post("/api/v1/auth/login", json={"username": "root", "password": "P@ss1word"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_account(client, headers, username: str, role: str) -> int:
    r = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"username": username, "password": "P@ss1word", "display_name": username, "role": role},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _login(client, username: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "P@ss1word"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


CA_CERT = "-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----"


def test_ca_column_persisted(client):
    h = _super_headers(client)
    r = client.post(
        "/api/v1/domains",
        headers=h,
        json={
            "name": "d1", "host": "dc1.corp.local", "port": 636, "use_ssl": True,
            "base_dn": "DC=corp,DC=local", "bind_dn": "admin@corp.local",
            "bind_password": "x", "ca_cert": CA_CERT,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["ca_cert"] == CA_CERT


def test_ca_import_roles(client, monkeypatch):
    import app.services.ldap_conn as lc

    def fake(host, port, use_ssl, bind_dn, password, ca_cert=""):
        return {
            "ok": True, "message": "x",
            "cert_trust": "ok" if ca_cert else "none",
            "cert_not_after": None, "cert_issuer": None,
        }

    monkeypatch.setattr(lc, "test_connection", fake)

    h = _super_headers(client)
    # 管理员自建域会自动获得该域管理权限（含 CA 导入所需的作用域）
    _create_account(client, h, "admin1", "admin")
    ah = _login(client, "admin1")
    d = client.post(
        "/api/v1/domains",
        headers=ah,
        json={"name": "d2", "host": "dc2", "port": 636, "use_ssl": True,
              "base_dn": "DC=corp,DC=local", "bind_dn": "a", "bind_password": "x"},
    ).json()

    # 管理员可导入 CA
    r = client.put(f"/api/v1/domains/{d['id']}/ca", headers=ah, json={"ca_cert": CA_CERT})
    assert r.status_code == 200, r.text
    assert r.json()["cert_trust"] == "ok"

    # 普通用户禁止导入
    _create_account(client, h, "user1", "user")
    uh = _login(client, "user1")
    r2 = client.put(f"/api/v1/domains/{d['id']}/ca", headers=uh, json={"ca_cert": CA_CERT})
    assert r2.status_code == 403


def test_expired_cert_blocks_non_super_write(client, monkeypatch):
    import app.services.ldap_conn as lc

    def fake(host, port, use_ssl, bind_dn, password, ca_cert=""):
        return {
            "ok": True, "message": "x",
            "cert_trust": "expired",  # 模拟证书已过期
            "cert_not_after": None, "cert_issuer": None,
        }

    monkeypatch.setattr(lc, "test_connection", fake)

    h = _super_headers(client)
    d = client.post(
        "/api/v1/domains",
        headers=h,
        json={"name": "d3", "host": "dc3", "port": 636, "use_ssl": True,
              "base_dn": "DC=corp,DC=local", "bind_dn": "a", "bind_password": "x",
              "ca_cert": CA_CERT},
    ).json()
    did = d["id"]

    # 通过 CA 导入接口（mock 返回 expired）把该域标记为已过期
    r = client.put(f"/api/v1/domains/{did}/ca", headers=h, json={"ca_cert": CA_CERT})
    assert r.status_code == 200
    assert r.json()["cert_trust"] == "expired"

    # 委派管理员并授权
    aid = _create_account(client, h, "admin2", "admin")
    ah = _login(client, "admin2")
    r = client.put(
        f"/api/v1/rbac/admins/{aid}/scopes", headers=h,
        json={"scopes": [{"domain_id": did, "base_dn": "DC=corp,DC=local", "permissions": ["user:write"]}]},
    )
    assert r.status_code == 200

    # 非超管的写操作被证书拦截（不触及 AD）
    dn_b64 = base64.urlsafe_b64encode(b"CN=foo,DC=corp,DC=local").decode()
    r2 = client.post(f"/api/v1/users/{dn_b64}/enable?domain_id={did}", headers=ah)
    assert r2.status_code == 403
    assert "证书" in r2.json()["detail"]

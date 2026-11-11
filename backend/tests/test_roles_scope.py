"""
P6-6 角色 / 作用域 / 多域 单元测试与集成测试。
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.deps import check_scope
from app.core.roles import ADMIN_FULL_PERMISSIONS, ROLE_SUPER, is_super
from app.models import AdminScope, AdminUser, DomainConfig


# --------------------------------------------------------------------------- #
# 角色常量
# --------------------------------------------------------------------------- #
def test_role_constants():
    assert is_super(ROLE_SUPER) is True
    assert is_super("admin") is False
    # 管理员自建域后默认获得全部写权限
    assert "user:write" in ADMIN_FULL_PERMISSIONS
    assert "ou:write" in ADMIN_FULL_PERMISSIONS
    assert len(ADMIN_FULL_PERMISSIONS) == 8


# --------------------------------------------------------------------------- #
# 作用域校验（核心逻辑，不依赖 LDAP）
# --------------------------------------------------------------------------- #
def test_check_scope_ok_and_denied(db):
    dom = DomainConfig(
        name="d", host="h", port=636, base_dn="DC=a,DC=com",
        bind_dn="x", bind_pwd_enc="", cert_trust="ok",
    )
    db.add(dom)
    db.commit()
    db.refresh(dom)

    admin = AdminUser(username="a", password_hash="", role="admin", is_superuser=False)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.add(AdminScope(admin_id=admin.id, domain_id=dom.id, base_dn="DC=a,DC=com", permissions=["user:write"]))
    db.commit()

    # 域内 + 权限命中
    assert check_scope(admin, "user:write", dom.id, "OU=x,DC=a,DC=com", db) is None
    # 域外 OU（base_dn 不以授权前缀结尾）
    with pytest.raises(HTTPException):
        check_scope(admin, "user:write", dom.id, "DC=other,DC=com", db)
    # 权限缺失
    with pytest.raises(HTTPException):
        check_scope(admin, "user:delete", dom.id, "DC=a,DC=com", db)
    # 非授权域
    with pytest.raises(HTTPException):
        check_scope(admin, "user:write", dom.id + 999, "DC=a,DC=com", db)


def test_check_scope_super_bypass(db):
    dom = DomainConfig(name="d", host="h", port=636, base_dn="DC=a,DC=com", bind_dn="x", bind_pwd_enc="")
    db.add(dom)
    db.commit()
    sup = AdminUser(username="s", password_hash="", role=ROLE_SUPER, is_superuser=True)
    db.add(sup)
    db.commit()
    # 超级管理员绕过全部作用域校验
    assert check_scope(sup, "anything", 12345, "DC=whatever,DC=com", db) is None


# --------------------------------------------------------------------------- #
# CA 认证开关：关闭时即使证书未通过也不限制
# --------------------------------------------------------------------------- #
def test_check_scope_ca_disabled_bypasses(db):
    dom = DomainConfig(
        name="d", host="h", port=636, base_dn="DC=a,DC=com",
        bind_dn="x", bind_pwd_enc="", cert_trust="untrusted", ca_enabled=False,
    )
    db.add(dom)
    db.commit()
    db.refresh(dom)
    admin = AdminUser(username="a", password_hash="", role="admin", is_superuser=False)
    db.add(admin)
    db.commit()
    db.add(AdminScope(admin_id=admin.id, domain_id=dom.id, base_dn="DC=a,DC=com", permissions=["user:write"]))
    db.commit()
    # ca_enabled=False -> 不触发证书拦截，仅按作用域放行
    assert check_scope(admin, "user:write", dom.id, "OU=x,DC=a,DC=com", db) is None


# --------------------------------------------------------------------------- #
# 账户管理：禁止创建/设为超级管理员
# --------------------------------------------------------------------------- #
def test_accounts_reject_super_creation(client, db, super_token):
    token = super_token
    h = {"Authorization": f"Bearer {token}"}
    # 创建管理员成功
    r = client.post("/api/v1/accounts", json={"username": "adm", "password": "P@ss1word", "role": "admin"}, headers=h)
    assert r.status_code == 200
    # 试图把账户设为超级管理员 -> 拒绝
    r2 = client.post("/api/v1/accounts", json={"username": "sup", "password": "P@ss1word", "role": "super_admin"}, headers=h)
    assert r2.status_code == 400


# --------------------------------------------------------------------------- #
# 多域：重复域创建拦截 + 管理员自建域自动授权
# --------------------------------------------------------------------------- #
def test_domain_duplicate_rejected(client, db, super_token):
    token = super_token
    h = {"Authorization": f"Bearer {token}"}
    body = {
        "name": "d1", "host": "h", "port": 636, "use_ssl": True,
        "base_dn": "DC=a,DC=com", "bind_dn": "x", "bind_password": "p", "description": "",
    }
    assert client.post("/api/v1/domains", json=body, headers=h).status_code == 200
    # 同名或同 base_dn 视为重复
    assert client.post("/api/v1/domains", json=body, headers=h).status_code == 400


def test_admin_create_domain_auto_scope(client, db, super_token):
    sup = super_token
    hsup = {"Authorization": f"Bearer {sup}"}
    ra = client.post("/api/v1/accounts", json={"username": "adm", "password": "P@ss1word", "role": "admin"}, headers=hsup)
    assert ra.status_code == 200
    rl = client.post("/api/v1/auth/login", json={"username": "adm", "password": "P@ss1word"})
    assert rl.status_code == 200
    hadm = {"Authorization": f"Bearer {rl.json()['access_token']}"}

    body = {
        "name": "d2", "host": "h2", "port": 636, "use_ssl": True,
        "base_dn": "DC=b,DC=com", "bind_dn": "y", "bind_password": "p", "description": "",
    }
    rc = client.post("/api/v1/domains", json=body, headers=hadm)
    assert rc.status_code == 200, rc.text
    # 管理员自建的域应自动出现在可管理域列表中
    rd = client.get("/api/v1/domains", headers=hadm)
    assert rd.status_code == 200
    assert any(d["name"] == "d2" for d in rd.json())

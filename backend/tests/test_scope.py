import pytest

from app.core.deps import check_scope
from app.core.roles import ROLE_SUPER
from app.core.security import hash_password
from app.models import AdminScope, AdminUser


def _make_delegated(db, username, scopes):
    u = AdminUser(username=username, role="admin", is_superuser=False, is_active=True, password_hash=hash_password("X@123456"))
    db.add(u)
    db.commit()
    db.refresh(u)
    for s in scopes:
        db.add(AdminScope(admin_id=u.id, base_dn=s["base_dn"], permissions=[s["action"]]))
    db.commit()
    db.refresh(u)
    return u


def test_superuser_bypasses_scope(db):
    admin = AdminUser(username="sup", password_hash="", role=ROLE_SUPER, is_superuser=True)
    db.add(admin)
    db.commit()
    # 超管不应抛异常
    check_scope(admin, "ou:write", 1, "OU=Any,DC=corp,DC=local", db)


def test_delegated_denied_without_scope(db):
    u = _make_delegated(db, "del1", [])
    with pytest.raises(Exception):
        check_scope(u, "ou:write", 1, "OU=X,DC=corp,DC=local", db)


def test_delegated_allowed_in_subtree(db):
    u = _make_delegated(db, "del2", [{"action": "ou:write", "base_dn": "OU=Sec,DC=corp,DC=local"}])
    # 在授权子树内允许
    check_scope(u, "ou:write", 1, "OU=Users,OU=Sec,DC=corp,DC=local", db)
    # 子树外拒绝
    with pytest.raises(Exception):
        check_scope(u, "ou:write", 1, "OU=Other,DC=corp,DC=local", db)

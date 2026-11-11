from app.db import SessionLocal
from app.models import AdminUser
from app.core.security import hash_password


def _ensure_delegate_debug():
    db = SessionLocal()
    try:
        if db.query(AdminUser).filter_by(username="delegate").first() is None:
            admin = AdminUser(
                username="delegate",
                password_hash=hash_password("Delegate@123"),
                role="admin",
                is_superuser=False,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return admin.id
    finally:
        db.close()


def test_debug_exact(client, db):
    # 等价于 auth_headers fixture：bootstrap root（测试库 fresh，必成功）
    b = client.post("/api/v1/auth/bootstrap", json={"username": "root", "password": "P@ss1word", "display_name": "root"})
    rr = client.post("/api/v1/auth/login", json={"username": "root", "password": "P@ss1word"})
    h = {"Authorization": f"Bearer {rr.json()['access_token']}"}
    # 等价 test_list_admins_requires_superuser 的前半
    did = _ensure_delegate_debug()
    print("did", did)
    r = client.post("/api/v1/auth/login", json={"username": "delegate", "password": "Delegate@123"})
    print("delegate login", r.status_code, r.text[:120])
    tk = r.json()["access_token"]
    hd = {"Authorization": f"Bearer {tk}"}
    d2 = db.query(AdminUser).filter_by(username="delegate").first()
    print("DELEGATE ROLE", repr(d2.role), "is_superuser", d2.is_superuser)
    r2 = client.get("/api/v1/rbac/admins", headers=hd)
    print("LIST delegate", r2.status_code)
    r3 = client.get("/api/v1/rbac/admins", headers=h)
    print("LIST root", r3.status_code, "contains delegate:", any(a["username"] == "delegate" for a in r3.json()))

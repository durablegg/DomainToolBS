from app.db import SessionLocal
from app.models import AuditLog


def test_audit_list_and_filter(auth_headers, client):
    db = SessionLocal()
    try:
        db.query(AuditLog).delete()
        db.add(AuditLog(operator="admin", action="user:create", object_type="user", target_name="alice", result="ok"))
        db.add(AuditLog(operator="admin", action="user:delete", object_type="user", target_name="bob", result="fail", error_msg="x"))
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/audit/logs", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 2

    r2 = client.get("/api/v1/audit/logs?action=user:delete", headers=auth_headers)
    assert r2.json()["total"] == 1

    r3 = client.get("/api/v1/audit/logs?keyword=alice", headers=auth_headers)
    assert r3.json()["total"] == 1


def test_audit_detail_and_404(auth_headers, client):
    db = SessionLocal()
    try:
        log = AuditLog(operator="admin", action="ou:write", object_type="ou", target_name="ou1", result="ok")
        db.add(log)
        db.commit()
        db.refresh(log)
        lid = log.id
    finally:
        db.close()

    r = client.get(f"/api/v1/audit/logs/{lid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == lid

    r2 = client.get("/api/v1/audit/logs/999999", headers=auth_headers)
    assert r2.status_code == 404

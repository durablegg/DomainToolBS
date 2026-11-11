from app.services import batch as batch_svc


def test_template(auth_headers, client):
    r = client.get("/api/v1/batch/template/users", headers=auth_headers)
    assert r.status_code == 200
    assert "sAMAccountName" in r.text
    assert r.headers["content-type"].startswith("text/csv")


def test_import_validation_and_task(auth_headers, client, monkeypatch):
    # 无真实域控：屏蔽后台导入 worker（本用例只校验 CSV 解析与任务创建）
    monkeypatch.setattr(batch_svc, "run_import", lambda *a, **kw: None)
    # 多域后批量导入需绑定域
    dr = client.post(
        "/api/v1/domains",
        json={"name": "d1", "host": "h", "port": 636, "use_ssl": True,
              "base_dn": "DC=contoso,DC=com", "bind_dn": "x", "bind_password": "p", "description": ""},
        headers=auth_headers,
    )
    assert dr.status_code == 200
    dom_id = dr.json()["id"]
    csv = "sAMAccountName,displayName,password\nuser1,User One,P@ss1\nuser2,User Two,P@ss1\n"
    r = client.post(
        "/api/v1/batch/import-users",
        headers=auth_headers,
        data={"target_ou_dn": "OU=Test,DC=contoso,DC=com", "domain_id": dom_id},
        files={"file": ("u.csv", csv, "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 2
    tid = r.json()["task_id"]

    r2 = client.get("/api/v1/batch/tasks", headers=auth_headers)
    assert any(t["id"] == tid for t in r2.json())

    r3 = client.get(f"/api/v1/batch/tasks/{tid}", headers=auth_headers)
    assert r3.status_code == 200
    assert r3.json()["total"] == 2


def test_import_missing_columns(auth_headers, client):
    dr = client.post(
        "/api/v1/domains",
        json={"name": "d1", "host": "h", "port": 636, "use_ssl": True,
              "base_dn": "DC=contoso,DC=com", "bind_dn": "x", "bind_password": "p", "description": ""},
        headers=auth_headers,
    )
    assert dr.status_code == 200
    dom_id = dr.json()["id"]
    csv = "foo,bar\n1,2\n"
    r = client.post(
        "/api/v1/batch/import-users",
        headers=auth_headers,
        data={"target_ou_dn": "OU=Test,DC=contoso,DC=com", "domain_id": dom_id},
        files={"file": ("u.csv", csv, "text/csv")},
    )
    assert r.status_code == 400


def test_parse_csv_unit():
    rows = batch_svc.parse_users_csv("sAMAccountName,displayName,password\njoe,Joe,P@ss\n")
    assert rows[0]["sAMAccountName"] == "joe"
    assert rows[0]["must_change_next_logon"] is True

    import pytest

    with pytest.raises(ValueError):
        batch_svc.parse_users_csv("a,b\n1,2\n")
    with pytest.raises(ValueError):
        batch_svc.parse_users_csv("sAMAccountName,displayName,password\njoe,Joe,\n")

def test_users_404_without_domain(client, auth_headers):
    assert client.get("/api/v1/users", headers=auth_headers).status_code == 422
    assert client.post("/api/v1/users", json={"ou_dn": "x", "sAMAccountName": "y", "displayName": "z", "password": "P@ss"}, headers=auth_headers).status_code == 422


def test_groups_404_without_domain(client, auth_headers):
    assert client.get("/api/v1/groups", headers=auth_headers).status_code == 422
    assert client.post("/api/v1/groups", json={"ou_dn": "x", "sAMAccountName": "y", "displayName": "z"}, headers=auth_headers).status_code == 422


def test_computers_404_without_domain(client, auth_headers):
    from app.core.dn import encode_dn

    assert client.get("/api/v1/computers", headers=auth_headers).status_code == 422
    enc = encode_dn("CN=pc,OU=x,DC=corp,DC=local")
    assert client.get(f"/api/v1/computers/{enc}", headers=auth_headers).status_code == 422
    assert client.post(f"/api/v1/computers/{enc}/disable", headers=auth_headers).status_code == 422

from app.db import init_db
init_db()
from fastapi.testclient import TestClient
from app.main import app
import jwt
from app.core.config import get_settings

s = get_settings()
c = TestClient(app)
b = c.post("/api/v1/auth/bootstrap", json={"username": "root", "password": "P@ss1word", "display_name": "root"})
print("bootstrap", b.status_code, b.text[:150])
rr = c.post("/api/v1/auth/login", json={"username": "root", "password": "P@ss1word"})
print("root login", rr.status_code, rr.text[:150])
h = {"Authorization": f"Bearer {rr.json()['access_token']}"}
a = c.post("/api/v1/accounts", json={"username": "delegate", "password": "Delegate@123", "role": "admin"}, headers=h)
print("create delegate", a.status_code, a.text[:150])

r = c.post("/api/v1/auth/login", json={"username": "delegate", "password": "Delegate@123"})
print("delegate login", r.status_code, r.text[:150])
token = r.json().get("access_token")
print("payload", jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM]))
hd = {"Authorization": f"Bearer {token}"}
r2 = c.get("/api/v1/rbac/admins", headers=hd)
print("list_admins", r2.status_code, r2.text[:200])

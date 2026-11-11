"""
P6-6 测试脚手架：使用共享内存 SQLite 替代应用默认数据库，
通过 dependency override 让路由使用同一会话，规避内存库多连接隔离问题。
运行：在 backend 目录下 `pip install pytest httpx` 后执行 `pytest -q`。
"""
from __future__ import annotations

import os

# 必须在导入 app 之前固定数据库 URL（虽然下方会强制替换 engine，这里保持一致）
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (注册模型)
from app.db import Base
from app.main import app

# 强制使用共享内存库的 engine（所有连接复用同一内存库）
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=test_engine)
import app.db as _dbmod  # noqa: E402

_dbmod.engine = test_engine  # type: ignore[attr-defined]
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
_dbmod.SessionLocal = TestSession  # type: ignore[attr-defined]

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def db():
    session = TestSession()
    # 清空所有表，保证用例隔离
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[_dbmod.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def bootstrap_super(client) -> str:
    # bootstrap 仅创建超管（返回 AdminOut，不含 token）；需再登录取得 token
    client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "root", "password": "P@ss1word", "display_name": "root"},
    )
    r = client.post("/api/v1/auth/login", json={"username": "root", "password": "P@ss1word"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def auth_headers(client) -> dict:
    """超级管理员(root)登录后的鉴权头，供需要登录的接口测试使用。"""
    return {"Authorization": f"Bearer {bootstrap_super(client)}"}


@pytest.fixture
def super_token(client) -> str:
    """超级管理员(root)的 JWT，供测试内构造请求头使用。"""
    return bootstrap_super(client)

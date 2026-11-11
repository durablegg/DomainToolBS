from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(128))
    # 四角色之一：super_admin / admin / user / auditor
    role: Mapped[str] = mapped_column(String(16), default="super_admin")
    # 兼容字段，恒等于 (role == "super_admin")
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 兼容/冗余字段，正式范围化授权以 admin_scope 表为准
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    scope_rows: Mapped[list["AdminScope"]] = relationship(
        "AdminScope", back_populates="admin", cascade="all, delete-orphan"
    )
    password_histories: Mapped[list["AdminPasswordHistory"]] = relationship(
        "AdminPasswordHistory",
        back_populates="admin",
        cascade="all, delete-orphan",
        order_by="AdminPasswordHistory.id.desc()",
    )


class AdminPasswordHistory(Base):
    """平台账号历史密码哈希（仅存旧密码，最新在前），用于"不得与前三次相同"校验。

    独立成表以规避 JSON 列在 PostgreSQL 下的序列化/反序列化隐患。
    """

    __tablename__ = "admin_password_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admin_user.id", ondelete="CASCADE"), index=True
    )
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    admin: Mapped["AdminUser"] = relationship("AdminUser", back_populates="password_histories")


class AdminScope(Base):
    """范围化委派授权（P5 启用界面，P0 已建表）。"""

    __tablename__ = "admin_scope"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_user.id"), index=True)
    # 所属域配置 id（P6 多域）；NULL 表示兼容旧数据（视为覆盖任意域）
    domain_id: Mapped[int | None] = mapped_column(
        ForeignKey("domain_config.id"), index=True, nullable=True
    )
    base_dn: Mapped[str] = mapped_column(String(512))
    # resource:action 列表，如 ["user:write", "group:read"]
    permissions: Mapped[list] = mapped_column(JSON, default=list)

    admin: Mapped["AdminUser"] = relationship("AdminUser", back_populates="scope_rows")


class DomainConfig(Base):
    """域连接配置 + 域服务账号凭据（加密存储）。"""

    __tablename__ = "domain_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="default")
    host: Mapped[str] = mapped_column(String(256))
    port: Mapped[int] = mapped_column(Integer, default=636)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    base_dn: Mapped[str] = mapped_column(String(512), default="")
    bind_dn: Mapped[str] = mapped_column(String(512), default="")
    bind_pwd_enc: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(String(512), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    # 域控自签名证书（公钥 PEM，非机密）；导入后启用更安全的 CERT_REQUIRED 通道
    ca_cert: Mapped[str] = mapped_column(Text, default="")
    # 对端证书到期时间（UTC）；用于到期提醒
    cert_not_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 通道信任状态：none(未导入) / ok / expiring_soon / expired / untrusted
    cert_trust: Mapped[str] = mapped_column(String(16), default="none")
    # CA 认证总开关：True=启用（按 cert_trust 校验并限制非超管写操作）；False=关闭（不限制）
    ca_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operator: Mapped[str] = mapped_column(String(128), default="")
    operator_ip: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64), default="")
    object_type: Mapped[str] = mapped_column(String(32), default="")
    object_dn: Mapped[str] = mapped_column(String(512), default="")
    target_name: Mapped[str] = mapped_column(String(256), default="")
    params: Mapped[str] = mapped_column(Text, default="")
    before: Mapped[str] = mapped_column(Text, default="")
    after: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(String(16), default="ok")
    error_msg: Mapped[str] = mapped_column(Text, default="")
    # 目标对象所属域配置 id（多域审计追溯）
    domain_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BatchTask(Base):
    __tablename__ = "batch_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    total: Mapped[int] = mapped_column(Integer, default=0)
    ok_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BatchTaskItem(Base):
    __tablename__ = "batch_task_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("batch_task.id"), index=True)
    target_dn: Mapped[str] = mapped_column(String(512), default="")
    target_name: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    message: Mapped[str] = mapped_column(Text, default="")

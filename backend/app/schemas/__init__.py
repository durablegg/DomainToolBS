from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# --------------------------------------------------------------------------- #
# 认证
# --------------------------------------------------------------------------- #
class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str = "super_admin"
    is_superuser: bool
    is_active: bool
    scopes: list = []


class LoginRequest(BaseModel):
    username: str
    password: str


class AdminCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""


class ChangePasswordIn(BaseModel):
    """当前登录用户修改自身密码（所有角色通用，含超级管理员）。"""

    old_password: str
    new_password: str


# --------------------------------------------------------------------------- #
# 账户管理（P6：四角色，仅超管可操作；超级管理员自身只能通过 DB 维护）
# --------------------------------------------------------------------------- #
class AccountCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    # 仅可为 admin / user / auditor；不允许设为 super_admin
    role: str = "user"


class AccountUpdate(BaseModel):
    display_name: str | None = None
    # 仅可为 admin / user / auditor；不允许改为 super_admin
    role: str | None = None
    password: str | None = None
    is_active: bool | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_superuser: bool
    is_active: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AdminOut


# --------------------------------------------------------------------------- #
# 域配置
# --------------------------------------------------------------------------- #
class DomainConfigIn(BaseModel):
    name: str = "default"
    host: str
    port: int = 636
    use_ssl: bool = True
    base_dn: str = ""
    bind_dn: str
    bind_password: str = ""
    description: str = ""
    ca_cert: str = ""
    ca_enabled: bool = True


class DomainConfigOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    use_ssl: bool
    base_dn: str
    bind_dn: str
    is_default: bool
    has_password: bool
    description: str = ""
    ca_cert: str = ""
    cert_not_after: Optional[datetime] = None
    cert_trust: str = "none"
    ca_enabled: bool = True
    updated_at: Optional[datetime] = None


class DomainCaUpdate(BaseModel):
    """导入/更新域控 CA 证书（超管 + 管理员）。"""
    ca_cert: str = ""


class DomainCaMode(BaseModel):
    """超级管理员专用：开启/关闭域的 CA 认证总开关。关闭后不启用任何 CA 相关限制。"""
    enabled: bool


class DomainBriefOut(BaseModel):
    """脱敏的域信息：不含连接凭据，供普通用户只读查看。"""

    id: int
    name: str
    description: str = ""
    base_dn: str = ""


class DomainTestResult(BaseModel):
    ok: bool
    message: str
    base_dn: Optional[str] = None
    domain_name: Optional[str] = None
    domain_controllers: list = []
    cert_not_after: Optional[datetime] = None
    cert_issuer: Optional[str] = None
    cert_trust: str = "none"


class DomainInfo(BaseModel):
    domain_name: Optional[str] = None
    base_dn: Optional[str] = None
    configuration_naming_context: Optional[str] = None
    domain_functional_level: Optional[str] = None
    domain_controllers: list = []


# --------------------------------------------------------------------------- #
# 组织单元
# --------------------------------------------------------------------------- #
class OUOut(BaseModel):
    dn: str
    name: str
    ou: Optional[str] = None
    description: Optional[str] = None
    parent_dn: Optional[str] = None
    sub_ous: list = []
    user_count: Optional[int] = None


class OUCreate(BaseModel):
    parent_dn: str
    name: str
    description: str = ""


class OUUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class OUMove(BaseModel):
    target_ou_dn: str


# --------------------------------------------------------------------------- #
# 通用分页
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# 域用户
# --------------------------------------------------------------------------- #
class UserOut(BaseModel):
    dn: str
    ou_dn: Optional[str] = None
    sAMAccountName: Optional[str] = None
    cn: Optional[str] = None
    displayName: Optional[str] = None
    name: Optional[str] = None
    mail: Optional[str] = None
    userPrincipalName: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    telephoneNumber: Optional[str] = None
    memberOf: list = []
    enabled: bool = True
    locked: bool = False
    lockout_remaining: Optional[int] = None
    pwd_never_expires: bool = False
    pwd_not_required: bool = False
    must_change_password: bool = False
    pwd_last_set: Optional[datetime] = None
    last_logon: Optional[datetime] = None
    account_expires: Optional[datetime] = None
    when_created: Optional[datetime] = None


class UserCreate(BaseModel):
    ou_dn: str
    sAMAccountName: str
    displayName: str
    name: Optional[str] = None
    password: str
    userPrincipalName: str = ""
    mail: str = ""
    department: str = ""
    title: str = ""
    telephoneNumber: str = ""
    description: str = ""
    password_never_expires: bool = False
    must_change_next_logon: bool = True


class UserUpdate(BaseModel):
    displayName: Optional[str] = None
    userPrincipalName: Optional[str] = None
    mail: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    telephoneNumber: Optional[str] = None
    description: Optional[str] = None


class ResetPasswordIn(BaseModel):
    new_password: str
    must_change_next_logon: bool = True


class UserMove(BaseModel):
    target_ou_dn: str


class UserPage(BaseModel):
    total: int
    page: int
    size: int
    items: list = []


# --------------------------------------------------------------------------- #
# 用户组
# --------------------------------------------------------------------------- #
class GroupOut(BaseModel):
    dn: str
    sAMAccountName: Optional[str] = None
    cn: Optional[str] = None
    displayName: Optional[str] = None
    name: Optional[str] = None
    mail: Optional[str] = None
    description: Optional[str] = None
    managedBy: Optional[str] = None
    group_type: Optional[int] = None
    is_security: bool = False
    member_count: int = 0
    when_created: Optional[datetime] = None


class GroupCreate(BaseModel):
    ou_dn: str
    sAMAccountName: str
    displayName: str
    name: Optional[str] = None
    mail: str = ""
    description: str = ""
    managedBy: str = ""
    scope: str = "global"  # global / domainlocal / universal
    security: bool = True


class GroupUpdate(BaseModel):
    displayName: Optional[str] = None
    mail: Optional[str] = None
    description: Optional[str] = None
    managedBy: Optional[str] = None
    info: Optional[str] = None


class GroupMemberIn(BaseModel):
    members: list  # 支持 DN 或 sAMAccountName


class GroupMemberItem(BaseModel):
    dn: str
    sAMAccountName: Optional[str] = None
    displayName: Optional[str] = None
    kind: str = "unknown"


class GroupMemberPage(BaseModel):
    total: int
    page: int
    size: int
    items: list = []


class GroupPage(BaseModel):
    total: int
    page: int
    size: int
    items: list = []


# --------------------------------------------------------------------------- #
# 计算机账号
# --------------------------------------------------------------------------- #
class ComputerOut(BaseModel):
    dn: str
    ou_dn: Optional[str] = None
    sAMAccountName: Optional[str] = None
    cn: Optional[str] = None
    displayName: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    operatingSystem: Optional[str] = None
    operatingSystemVersion: Optional[str] = None
    dnsHostname: Optional[str] = None
    enabled: bool = True
    when_created: Optional[datetime] = None
    last_logon: Optional[datetime] = None


class ComputerPage(BaseModel):
    total: int
    page: int
    size: int
    items: list = []


class ComputerMove(BaseModel):
    target_ou_dn: str


class PageResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list = []


# --------------------------------------------------------------------------- #
# 审计日志（P4）
# --------------------------------------------------------------------------- #
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    operator: str
    operator_ip: str
    action: str
    object_type: str
    object_dn: str
    target_name: str
    params: str
    before: str
    after: str
    result: str
    error_msg: str
    domain_id: Optional[int] = None
    created_at: Optional[datetime] = None


class AuditPage(BaseModel):
    total: int
    page: int
    size: int
    items: list = []


# --------------------------------------------------------------------------- #
# 批量任务（P3）
# --------------------------------------------------------------------------- #
class BatchTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    total: int
    ok_count: int
    fail_count: int
    created_by: str
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class BatchTaskItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    target_dn: str
    target_name: str
    status: str
    message: str


class BatchTaskDetail(BatchTaskOut):
    items: list = []


# --------------------------------------------------------------------------- #
# 委派授权矩阵（P5）
# --------------------------------------------------------------------------- #
class AdminBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_superuser: bool
    is_active: bool


class AdminScopeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int
    domain_id: int | None = None
    base_dn: str
    permissions: list = []


class ScopeRowIn(BaseModel):
    domain_id: int  # 所属域配置 id
    base_dn: str
    permissions: list = []  # list[str]，如 ["user:write", "group:read"]


class AdminScopesIn(BaseModel):
    scopes: list[ScopeRowIn] = []


class PermissionDef(BaseModel):
    key: str
    label: str


class ResourceDef(BaseModel):
    key: str
    label: str
    actions: list = []  # list[PermissionDef]


class PermissionsMatrix(BaseModel):
    resources: list = []  # list[ResourceDef]

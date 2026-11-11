from __future__ import annotations

# 平台登录角色（四角色）
ROLE_SUPER = "super_admin"      # 超级管理员：全部权限，管理其他角色；自身增删仅限 DB
ROLE_ADMIN = "admin"            # 管理员：超管授权的一个或多个域控范围内写操作
ROLE_USER = "user"              # 普通用户：全部域只读，无写/授权/审计
ROLE_AUDITOR = "auditor"        # 审计员：仅审计查看/导出

ALL_ROLES = [ROLE_SUPER, ROLE_ADMIN, ROLE_USER, ROLE_AUDITOR]

# 可通过界面由超管创建/分配的角色（超级管理员自身只能 DB 操作）
ASSIGNABLE_ROLES = [ROLE_ADMIN, ROLE_USER, ROLE_AUDITOR]

ROLE_LABELS = {
    ROLE_SUPER: "超级管理员",
    ROLE_ADMIN: "管理员",
    ROLE_USER: "普通用户",
    ROLE_AUDITOR: "审计员",
}

# 管理员自行新建域后，自动获得该域的完整写权限（覆盖全部资源）
ADMIN_FULL_PERMISSIONS = [
    "user:write",
    "user:delete",
    "user:reset_password",
    "group:write",
    "group:delete",
    "computer:write",
    "computer:delete",
    "ou:write",
]


def is_super(role: str | None) -> bool:
    return role == ROLE_SUPER

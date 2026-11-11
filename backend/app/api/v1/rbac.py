from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_superuser
from app.db import get_db
from app.models import AdminScope, AdminUser, DomainConfig
from app.schemas import (
    AdminBrief,
    AdminScopeOut,
    AdminScopesIn,
    PermissionsMatrix,
    PermissionDef,
    ResourceDef,
)

router = APIRouter(prefix="/rbac", tags=["rbac"])

# 权限矩阵定义（与 check_scope 实际使用的 action 字符串保持一致）
PERMISSIONS = PermissionsMatrix(
    resources=[
        ResourceDef(
            key="user",
            label="用户",
            actions=[
                PermissionDef(key="write", label="写入(创建/编辑/启停/移动)"),
                PermissionDef(key="delete", label="删除"),
                PermissionDef(key="reset_password", label="重置密码"),
            ],
        ),
        ResourceDef(
            key="group",
            label="用户组",
            actions=[
                PermissionDef(key="write", label="写入(创建/编辑/成员)"),
                PermissionDef(key="delete", label="删除"),
            ],
        ),
        ResourceDef(
            key="computer",
            label="计算机",
            actions=[
                PermissionDef(key="write", label="写入(启停/移动)"),
                PermissionDef(key="delete", label="删除"),
            ],
        ),
        ResourceDef(
            key="ou",
            label="组织单位",
            actions=[PermissionDef(key="write", label="写入(创建/移动/删除)")],
        ),
    ]
)

VALID_PERMISSIONS = {
    f"{r.key}:{a.key}" for r in PERMISSIONS.resources for a in r.actions
}


@router.get("/permissions", response_model=PermissionsMatrix)
def permissions_matrix() -> PermissionsMatrix:
    return PERMISSIONS


@router.get("/admins", response_model=list[AdminBrief])
def list_admins(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_superuser),
) -> list[AdminBrief]:
    # 仅列出可通过界面管理的非超管账户（超级管理员自身只能经 DB 维护）
    return (
        db.query(AdminUser)
        .filter(AdminUser.role != "super_admin")
        .order_by(AdminUser.id)
        .all()
    )


@router.get("/admins/{admin_id}/scopes", response_model=list[AdminScopeOut])
def get_scopes(
    admin_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_superuser),
) -> list[AdminScopeOut]:
    admin = db.get(AdminUser, admin_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="管理员不存在")
    if admin.is_superuser:
        raise HTTPException(status_code=400, detail="超级管理员拥有全部权限，无需配置作用域")
    # 普通用户/审计员使用内置默认权限，不涉及域 + OU 授权
    if admin.role != "admin":
        return []
    return [AdminScopeOut.model_validate(s) for s in admin.scope_rows]


@router.put("/admins/{admin_id}/scopes", response_model=list[AdminScopeOut])
def put_scopes(
    admin_id: int,
    payload: AdminScopesIn,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_superuser),
) -> list[AdminScopeOut]:
    admin = db.get(AdminUser, admin_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="管理员不存在")
    if admin.is_superuser:
        raise HTTPException(status_code=400, detail="超级管理员拥有全部权限，无需配置作用域")
    # 仅「管理员」角色可被授予域 + OU 权限；普通用户/审计员固定为内置默认权限
    if admin.role != "admin":
        raise HTTPException(
            status_code=400, detail="该角色使用系统内置默认权限，无需配置作用域"
        )

    for row in payload.scopes:
        for perm in row.permissions:
            if perm not in VALID_PERMISSIONS:
                raise HTTPException(status_code=400, detail=f"未知权限: {perm}")
        if db.get(DomainConfig, row.domain_id) is None:
            raise HTTPException(status_code=400, detail=f"域不存在: {row.domain_id}")

    db.query(AdminScope).filter(AdminScope.admin_id == admin_id).delete()
    for row in payload.scopes:
        db.add(
            AdminScope(
                admin_id=admin_id,
                domain_id=row.domain_id,
                base_dn=row.base_dn,
                permissions=list(row.permissions),
            )
        )
    db.commit()
    return [
        AdminScopeOut.model_validate(s)
        for s in db.query(AdminScope).filter(AdminScope.admin_id == admin_id).all()
    ]

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.roles import ROLE_ADMIN, ROLE_AUDITOR, ROLE_USER, is_super
from app.core.security import decode_access_token
from app.db import get_db
from app.models import AdminScope, AdminUser, DomainConfig

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_admin(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> AdminUser:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效或过期的凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
    except Exception:
        raise credentials_exc
    if not username:
        raise credentials_exc
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin is None or not admin.is_active:
        raise credentials_exc
    return admin


def require_role(*roles: str):
    """依赖工厂：仅允许指定角色通过。"""

    def checker(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if admin.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
        return admin

    return checker


def require_superuser(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    if not is_super(admin.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要超级管理员权限")
    return admin


def _scope_match(admin: AdminUser, domain_id: int, db: Session) -> bool:
    """该管理员在 domain_id 上是否存在任意作用域行（用于判断"能否管该域"）。"""
    return (
        db.query(AdminScope)
        .filter(
            AdminScope.admin_id == admin.id,
            or_(AdminScope.domain_id == domain_id, AdminScope.domain_id.is_(None)),
        )
        .first()
        is not None
    )


def get_domain_config(domain_id: int, admin: AdminUser, db: Session) -> DomainConfig:
    """解析目标域配置，并按角色做可见性/管辖性校验。

    - 超级管理员：任意域
    - 管理员：仅"被授权域"（存在该域的作用域行）
    - 普通用户：全部域（只读）
    - 审计员：无目录访问权限
    """
    cfg = db.get(DomainConfig, domain_id)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域不存在")
    if is_super(admin.role):
        return cfg
    if admin.role == ROLE_ADMIN:
        if not _scope_match(admin, domain_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无该域的管理权限"
            )
        return cfg
    if admin.role == ROLE_USER:
        return cfg
    # 审计员
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="审计员无目录访问权限")


def check_scope(
    admin: AdminUser, action: str, domain_id: int, target_dn: str, db: Session
) -> None:
    """范围化授权校验（P6 多域版）：超管放行；管理员需在授权域的 base_dn 子树内且含 action。

    子树判定采用 DN 后缀匹配（目标 DN 等于 base 或以 ",base" 结尾），无需额外 LDAP 查询。
    普通用户/审计员不在此走写路径（写接口会先被角色拦截）。
    """
    if is_super(admin.role):
        return
    if admin.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限"
        )
    # 已启用 CA 认证，且证书缺导入/已过期/未通过校验：暂停非超管的写操作
    # （关闭 CA 认证时完全不限制；读操作不受影响）
    _cfg = db.get(DomainConfig, domain_id)
    if _cfg and _cfg.ca_enabled and _cfg.cert_trust in ("none", "expired", "untrusted"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该域已启用 CA 认证但证书未通过校验（缺CA/过期/校验失败），写操作已暂停；"
            "可由超级管理员关闭 CA 认证或重新导入有效 CA",
        )
    rows = (
        db.query(AdminScope)
        .filter(
            AdminScope.admin_id == admin.id,
            or_(AdminScope.domain_id == domain_id, AdminScope.domain_id.is_(None)),
        )
        .all()
    )
    for scope in rows:
        if action not in (scope.permissions or []):
            continue
        if not scope.base_dn or target_dn.lower().endswith(scope.base_dn.lower()):
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"无权限对 {target_dn} 执行 {action}",
    )

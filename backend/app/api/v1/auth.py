from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.core.roles import is_super
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.core.config import get_settings
from app.db import get_db
from app.models import AdminUser
from app.schemas import AdminCreate, AdminOut, ChangePasswordIn, LoginRequest, TokenResponse
from app.services import password_policy

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    admin = db.query(AdminUser).filter(AdminUser.username == req.username).first()
    if (
        admin is None
        or not admin.is_active
        or not verify_password(req.password, admin.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    admin.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(
        admin.username,
        {"uid": admin.id, "su": is_super(admin.role), "role": admin.role},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=AdminOut.model_validate(admin),
    )


@router.post("/bootstrap", response_model=AdminOut)
def bootstrap(req: AdminCreate, db: Session = Depends(get_db)) -> AdminOut:
    """首次初始化：平台无管理员时创建超级管理员。已存在则拒绝。"""
    if db.query(AdminUser).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="平台已初始化，不能重复创建超管"
        )
    try:
        password_policy.validate_complexity(req.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    admin = AdminUser(
        username=req.username,
        display_name=req.display_name,
        password_hash=hash_password(req.password),
        role="super_admin",
        is_superuser=True,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return AdminOut.model_validate(admin)


@router.get("/me", response_model=AdminOut)
def me(admin: AdminUser = Depends(get_current_admin)) -> AdminOut:
    return AdminOut.model_validate(admin)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    """当前登录用户修改自身密码（所有角色通用，含超级管理员）。

    校验：原密码正确 + 复杂度达标 + 不得与当前密码及最近 3 次历史密码相同。
    """
    if not verify_password(payload.old_password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    old_hash = admin.password_hash
    try:
        password_policy.validate_new_password(
            payload.new_password, old_hash, password_policy.get_recent_hashes(db, admin.id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    admin.password_hash = hash_password(payload.new_password)
    # 记录旧密码到历史（仅存旧密码），新密码保持为当前 admin.password_hash
    password_policy.record_history(db, admin.id, old_hash)
    db.commit()
    return {"ok": True}

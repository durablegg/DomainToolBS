from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_superuser
from app.core.roles import ASSIGNABLE_ROLES, is_super
from app.core.security import hash_password
from app.db import get_db
from app.models import AdminUser
from app.schemas import AccountCreate, AccountOut, AccountUpdate
from app.services import password_policy

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _check_role(role: str | None) -> None:
    if role is not None and role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不允许通过界面创建/分配超级管理员（只能操作服务器用户数据库）",
        )


@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_superuser),
) -> list[AccountOut]:
    # 仅列出可通过界面管理的非超管账户
    return (
        db.query(AdminUser)
        .filter(AdminUser.role != "super_admin")
        .order_by(AdminUser.id)
        .all()
    )


@router.post("", response_model=AccountOut)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_superuser),
) -> AccountOut:
    _check_role(payload.role)
    try:
        password_policy.validate_complexity(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if db.query(AdminUser).filter(AdminUser.username == payload.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    admin = AdminUser(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_superuser=is_super(payload.role),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return AccountOut.model_validate(admin)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_superuser),
) -> AccountOut:
    admin = db.get(AdminUser, account_id)
    if admin is None or is_super(admin.role):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账户不存在")
    return AccountOut.model_validate(admin)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_superuser),
) -> AccountOut:
    admin = db.get(AdminUser, account_id)
    if admin is None or is_super(admin.role):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账户不存在")
    _check_role(payload.role)
    if payload.display_name is not None:
        admin.display_name = payload.display_name
    if payload.role is not None:
        admin.role = payload.role
        admin.is_superuser = is_super(payload.role)
    if payload.password:
        old_hash = admin.password_hash
        try:
            password_policy.validate_new_password(
                payload.password, old_hash, password_policy.get_recent_hashes(db, admin.id)
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        admin.password_hash = hash_password(payload.password)
        password_policy.record_history(db, admin.id, old_hash)
    if payload.is_active is not None:
        admin.is_active = payload.is_active
    db.commit()
    db.refresh(admin)
    return AccountOut.model_validate(admin)


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    operator: AdminUser = Depends(require_superuser),
) -> dict:
    admin = db.get(AdminUser, account_id)
    if admin is None or is_super(admin.role):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除超级管理员账户")
    if admin.id == operator.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录账户")
    db.delete(admin)
    db.commit()
    return {"ok": True, "id": account_id}

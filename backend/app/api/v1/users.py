from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import check_scope, get_current_admin, get_domain_config
from app.core.dn import decode_dn
from app.db import get_db
from app.models import AdminUser
from app.schemas import (
    ResetPasswordIn,
    UserCreate,
    UserMove,
    UserOut,
    UserPage,
    UserUpdate,
)
from app.services import ad_user, audit, ldap_conn

router = APIRouter(prefix="/users", tags=["users"])


def _ip(req: Request) -> str:
    return req.client.host if req.client else ""


def _sam_of(conn, dn: str) -> str:
    """从 AD 取 sAMAccountName 用于审计 target_name（取不到则退回 DN）。"""
    try:
        return ad_user.get_user(conn, dn).get("sAMAccountName") or dn
    except Exception:
        return dn


@router.get("", response_model=UserPage)
def list_users(
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    ou: str | None = None,
    keyword: str | None = None,
    enabled: str | None = None,
    locked: str | None = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> UserPage:
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    base = ou or cfg.base_dn
    try:
        total, users = ad_user.search_users(conn, base, keyword, enabled, locked, page, size)
        return UserPage(
            total=total, page=page, size=size, items=[UserOut(**u) for u in users]
        )
    finally:
        conn.unbind()


@router.post("", response_model=UserOut)
def create_user_api(
    payload: UserCreate,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> UserOut:
    check_scope(admin, "user:write", domain_id, payload.ou_dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        dn = ad_user.create_user(conn, payload.model_dump())
        audit.write_log(
            db, admin.username, "user:create", "user", dn, payload.sAMAccountName,
            operator_ip=_ip(req), result="ok", domain_id=domain_id,
        )
        return UserOut(**ad_user.get_user(conn, dn))
    except Exception as exc:
        audit.write_log(
            db, admin.username, "user:create", "user", target_name=payload.sAMAccountName,
            operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.get("/{dn_b64}", response_model=UserOut)
def get_user_api(
    dn_b64: str,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> UserOut:
    dn = decode_dn(dn_b64)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        return UserOut(**ad_user.get_user(conn, dn))
    finally:
        conn.unbind()


@router.patch("/{dn_b64}", response_model=UserOut)
def update_user_api(
    payload: UserUpdate,
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> UserOut:
    dn = decode_dn(dn_b64)
    check_scope(admin, "user:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of(conn, dn)
    try:
        ad_user.update_user(conn, dn, payload.model_dump(exclude_unset=True))
        audit.write_log(db, admin.username, "user:update", "user", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return UserOut(**ad_user.get_user(conn, dn))
    except Exception as exc:
        audit.write_log(
            db, admin.username, "user:update", "user", dn, sam, operator_ip=_ip(req),
            result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.delete("/{dn_b64}")
def delete_user_api(
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "user:delete", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of(conn, dn)
    try:
        ad_user.delete_user(conn, dn)
        audit.write_log(db, admin.username, "user:delete", "user", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(
            db, admin.username, "user:delete", "user", dn, sam, operator_ip=_ip(req),
            result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.post("/{dn_b64}/enable")
def enable_user_api(
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "user:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of(conn, dn)
    try:
        ad_user.set_enabled(conn, dn, True)
        audit.write_log(db, admin.username, "user:enable", "user", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(
            db, admin.username, "user:enable", "user", dn, sam, operator_ip=_ip(req),
            result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.post("/{dn_b64}/disable")
def disable_user_api(
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "user:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of(conn, dn)
    try:
        ad_user.set_enabled(conn, dn, False)
        audit.write_log(db, admin.username, "user:disable", "user", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(
            db, admin.username, "user:disable", "user", dn, sam, operator_ip=_ip(req),
            result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.post("/{dn_b64}/unlock")
def unlock_user_api(
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "user:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of(conn, dn)
    try:
        ad_user.unlock_user(conn, dn)
        audit.write_log(db, admin.username, "user:unlock", "user", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(
            db, admin.username, "user:unlock", "user", dn, sam, operator_ip=_ip(req),
            result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.post("/{dn_b64}/reset-password")
def reset_password_api(
    payload: ResetPasswordIn,
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "user:reset_password", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of(conn, dn)
    try:
        ad_user.reset_password(conn, dn, payload.new_password, payload.must_change_next_logon)
        audit.write_log(
            db, admin.username, "user:reset_password", "user", dn, sam, operator_ip=_ip(req), domain_id=domain_id
        )
        return {"ok": True}
    except Exception as exc:
        audit.write_log(
            db, admin.username, "user:reset_password", "user", dn, sam, operator_ip=_ip(req),
            result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.post("/{dn_b64}/move")
def move_user_api(
    payload: UserMove,
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "user:write", domain_id, dn, db)
    check_scope(admin, "user:write", domain_id, payload.target_ou_dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of(conn, dn)
    try:
        ad_user.move_user(conn, dn, payload.target_ou_dn)
        audit.write_log(
            db, admin.username, "user:move", "user", dn, sam,
            params=payload.target_ou_dn, operator_ip=_ip(req), domain_id=domain_id,
        )
        return {"ok": True}
    except Exception as exc:
        audit.write_log(
            db, admin.username, "user:move", "user", dn, sam,
            params=payload.target_ou_dn, operator_ip=_ip(req),
            result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()

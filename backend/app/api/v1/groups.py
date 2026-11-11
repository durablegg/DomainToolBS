from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import check_scope, get_current_admin, get_domain_config
from app.core.dn import decode_dn
from app.db import get_db
from app.models import AdminUser
from app.schemas import (
    GroupCreate,
    GroupMemberIn,
    GroupMemberItem,
    GroupMemberPage,
    GroupOut,
    GroupPage,
    GroupUpdate,
)
from app.services import ad_group, audit, ldap_conn

router = APIRouter(prefix="/groups", tags=["groups"])


def _ip(req: Request) -> str:
    return req.client.host if req.client else ""


def _sam_of_group(conn, dn: str) -> str:
    """从 AD 取组的 sAMAccountName 用于审计 target_name（取不到则退回 DN）。"""
    try:
        return ad_group.get_group(conn, dn).get("sAMAccountName") or dn
    except Exception:
        return dn


@router.get("", response_model=GroupPage)
def list_groups(
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    keyword: str | None = None,
    security: str | None = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> GroupPage:
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        total, groups = ad_group.search_groups(conn, cfg.base_dn, keyword, security, page, size)
        return GroupPage(total=total, page=page, size=size, items=[GroupOut(**g) for g in groups])
    finally:
        conn.unbind()


@router.post("", response_model=GroupOut)
def create_group_api(
    payload: GroupCreate,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> GroupOut:
    check_scope(admin, "group:write", domain_id, payload.ou_dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        dn = ad_group.create_group(conn, payload.model_dump())
        audit.write_log(db, admin.username, "group:create", "group", dn, payload.sAMAccountName, operator_ip=_ip(req), domain_id=domain_id)
        return GroupOut(**ad_group.get_group(conn, dn))
    except Exception as exc:
        audit.write_log(db, admin.username, "group:create", "group", target_name=payload.sAMAccountName, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.get("/{dn_b64}", response_model=GroupOut)
def get_group_api(
    dn_b64: str,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> GroupOut:
    dn = decode_dn(dn_b64)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        return GroupOut(**ad_group.get_group(conn, dn))
    finally:
        conn.unbind()


@router.patch("/{dn_b64}", response_model=GroupOut)
def update_group_api(
    payload: GroupUpdate,
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> GroupOut:
    dn = decode_dn(dn_b64)
    check_scope(admin, "group:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of_group(conn, dn)
    try:
        ad_group.update_group(conn, dn, payload.model_dump(exclude_unset=True))
        audit.write_log(db, admin.username, "group:update", "group", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return GroupOut(**ad_group.get_group(conn, dn))
    except Exception as exc:
        audit.write_log(db, admin.username, "group:update", "group", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.delete("/{dn_b64}")
def delete_group_api(
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "group:delete", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of_group(conn, dn)
    try:
        ad_group.delete_group(conn, dn)
        audit.write_log(db, admin.username, "group:delete", "group", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(db, admin.username, "group:delete", "group", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.get("/{dn_b64}/members", response_model=GroupMemberPage)
def list_members_api(
    dn_b64: str,
    domain_id: int = Query(..., description="域配置 ID"),
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> GroupMemberPage:
    dn = decode_dn(dn_b64)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        total, items = ad_group.list_members(conn, dn, cfg.base_dn, page, size)
        return GroupMemberPage(total=total, page=page, size=size, items=[GroupMemberItem(**i) for i in items])
    finally:
        conn.unbind()


@router.post("/{dn_b64}/members")
def add_members_api(
    payload: GroupMemberIn,
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "group:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of_group(conn, dn)
    try:
        n = ad_group.add_members(conn, cfg.base_dn, dn, payload.members)
        audit.write_log(db, admin.username, "group:add_members", "group", dn, sam, params=str(payload.members), operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True, "added": n}
    except Exception as exc:
        audit.write_log(db, admin.username, "group:add_members", "group", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.delete("/{dn_b64}/members")
def remove_members_api(
    payload: GroupMemberIn,
    dn_b64: str,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "group:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of_group(conn, dn)
    try:
        ad_group.remove_members(conn, dn, payload.members)
        audit.write_log(db, admin.username, "group:remove_members", "group", dn, sam, params=str(payload.members), operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(db, admin.username, "group:remove_members", "group", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()

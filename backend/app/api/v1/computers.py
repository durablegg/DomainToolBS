from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import check_scope, get_current_admin, get_domain_config
from app.core.dn import decode_dn
from app.db import get_db
from app.models import AdminUser
from app.schemas import ComputerMove, ComputerOut, ComputerPage
from app.services import ad_computer, audit, ldap_conn

router = APIRouter(prefix="/computers", tags=["computers"])


def _ip(req: Request) -> str:
    return req.client.host if req.client else ""


def _sam_of_computer(conn, dn: str) -> str:
    """从 AD 取计算机的 sAMAccountName（含 $ 后缀）用于审计 target_name（取不到则退回 DN）。"""
    try:
        return ad_computer.get_computer(conn, dn).get("sAMAccountName") or dn
    except Exception:
        return dn


@router.get("", response_model=ComputerPage)
def list_computers(
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    ou: str | None = None,
    keyword: str | None = None,
    enabled: str | None = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> ComputerPage:
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        base = ou or cfg.base_dn
        total, items = ad_computer.search_computers(conn, base, keyword, enabled, page, size)
        return ComputerPage(total=total, page=page, size=size, items=[ComputerOut(**c) for c in items])
    finally:
        conn.unbind()


@router.get("/{dn_b64}", response_model=ComputerOut)
def get_computer_api(
    dn_b64: str,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> ComputerOut:
    dn = decode_dn(dn_b64)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        return ComputerOut(**ad_computer.get_computer(conn, dn))
    finally:
        conn.unbind()


@router.post("/{dn_b64}/enable")
def enable_computer_api(
    dn_b64: str, req: Request, domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "computer:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of_computer(conn, dn)
    try:
        ad_computer.set_enabled(conn, dn, True)
        audit.write_log(db, admin.username, "computer:enable", "computer", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(db, admin.username, "computer:enable", "computer", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.post("/{dn_b64}/disable")
def disable_computer_api(
    dn_b64: str, req: Request, domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "computer:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of_computer(conn, dn)
    try:
        ad_computer.set_enabled(conn, dn, False)
        audit.write_log(db, admin.username, "computer:disable", "computer", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(db, admin.username, "computer:disable", "computer", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.post("/{dn_b64}/move")
def move_computer_api(
    payload: ComputerMove, dn_b64: str, req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "computer:write", domain_id, dn, db)
    check_scope(admin, "computer:write", domain_id, payload.target_ou_dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of_computer(conn, dn)
    try:
        ad_computer.move_computer(conn, dn, payload.target_ou_dn)
        audit.write_log(db, admin.username, "computer:move", "computer", dn, sam, params=payload.target_ou_dn, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(db, admin.username, "computer:move", "computer", dn, sam, params=payload.target_ou_dn, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()


@router.delete("/{dn_b64}")
def delete_computer_api(
    dn_b64: str, req: Request, domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "computer:delete", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _sam_of_computer(conn, dn)
    try:
        ad_computer.delete_computer(conn, dn)
        audit.write_log(db, admin.username, "computer:delete", "computer", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True}
    except Exception as exc:
        audit.write_log(db, admin.username, "computer:delete", "computer", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.unbind()

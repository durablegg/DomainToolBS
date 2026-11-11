from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import check_scope, get_current_admin, get_domain_config
from app.core.dn import decode_dn
from app.db import get_db
from app.models import AdminUser
from app.schemas import OUCreate, OUMove, OUOut, OUUpdate
from app.services import ad_ou, audit, ldap_conn

router = APIRouter(prefix="/ous", tags=["ous"])


def _ou_name(dn: str) -> str:
    """从 DN 取 OU/CN 的 RDN 值，用于审计 target_name（OU 无 sAMAccountName）。"""
    m = re.search(r"(?i)(?:OU|CN)=([^,]+)", dn)
    return m.group(1) if m else dn


def _ip(req: Request) -> str:
    return req.client.host if req.client else ""


@router.get("", response_model=list[OUOut])
def list_ous(
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> list[OUOut]:
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        tree = ad_ou.get_ou_tree(conn, cfg.base_dn)
        return [OUOut(**node) for node in tree]
    finally:
        conn.unbind()


@router.post("", response_model=OUOut)
def create_ou(
    payload: OUCreate,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> OUOut:
    check_scope(admin, "ou:write", domain_id, payload.parent_dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        dn = ad_ou.create_ou(conn, payload.parent_dn, payload.name, payload.description)
        audit.write_log(db, admin.username, "ou:create", "ou", dn, payload.name, operator_ip=_ip(req), domain_id=domain_id)
        return OUOut(
            dn=dn,
            name=payload.name,
            ou=payload.name,
            description=payload.description or None,
            parent_dn=payload.parent_dn,
            sub_ous=[],
        )
    except Exception as exc:
        audit.write_log(db, admin.username, "ou:create", "ou", "", payload.name, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise
    finally:
        conn.unbind()


@router.patch("/{dn_b64}", response_model=OUOut)
def update_ou(
    payload: OUUpdate,
    req: Request,
    dn_b64: str = Path(...),
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> OUOut:
    dn = decode_dn(dn_b64)
    check_scope(admin, "ou:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = payload.name or _ou_name(dn)
    try:
        if payload.name is not None:
            ad_ou.rename_ou(conn, dn, payload.name)
        audit.write_log(db, admin.username, "ou:update", "ou", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return OUOut(dn=dn, name=payload.name or dn, description=payload.description)
    except Exception as exc:
        audit.write_log(db, admin.username, "ou:update", "ou", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise
    finally:
        conn.unbind()


@router.delete("/{dn_b64}")
def delete_ou(
    req: Request,
    dn_b64: str = Path(...),
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    dn = decode_dn(dn_b64)
    check_scope(admin, "ou:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _ou_name(dn)
    try:
        ad_ou.delete_ou(conn, dn)
        audit.write_log(db, admin.username, "ou:delete", "ou", dn, sam, operator_ip=_ip(req), domain_id=domain_id)
        return {"ok": True, "dn": dn}
    except Exception as exc:
        audit.write_log(db, admin.username, "ou:delete", "ou", dn, sam, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise
    finally:
        conn.unbind()


@router.post("/{dn_b64}/move", response_model=OUOut)
def move_ou(
    payload: OUMove,
    req: Request,
    dn_b64: str = Path(...),
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> OUOut:
    dn = decode_dn(dn_b64)
    check_scope(admin, "ou:write", domain_id, dn, db)
    check_scope(admin, "ou:write", domain_id, payload.target_ou_dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    sam = _ou_name(dn)
    try:
        ad_ou.move_ou(conn, dn, payload.target_ou_dn)
        audit.write_log(db, admin.username, "ou:move", "ou", dn, sam, params=payload.target_ou_dn, operator_ip=_ip(req), domain_id=domain_id)
        return OUOut(dn=dn, name=dn)
    except Exception as exc:
        audit.write_log(db, admin.username, "ou:move", "ou", dn, sam, params=payload.target_ou_dn, operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id)
        raise
    finally:
        conn.unbind()

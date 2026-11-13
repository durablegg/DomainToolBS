from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import check_scope, get_current_admin, get_domain_config
from app.core.dn import decode_dn
from app.db import get_db
from app.models import AdminUser
from app.services import ad_gpo, audit, ldap_conn

router = APIRouter(prefix="/gpo", tags=["gpo"])


class GpoLinkIn(BaseModel):
    guid: str
    disabled: bool = False
    enforced: bool = False


class SetGplinksIn(BaseModel):
    links: list[GpoLinkIn] = []
    block_inheritance: bool = False


def _ip(req: Request) -> str:
    return req.client.host if req.client else ""


@router.get("/domains/{domain_id}/gpos")
def list_gpos_api(
    domain_id: int = Path(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        return ad_gpo.list_gpos(conn, cfg.base_dn)
    finally:
        conn.unbind()


@router.get("/ous/{dn_b64}/gplinks")
def get_ou_gplinks_api(
    dn_b64: str = Path(...),
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    dn = decode_dn(dn_b64)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        return ad_gpo.get_ou_gplinks(conn, dn)
    finally:
        conn.unbind()


@router.post("/ous/{dn_b64}/gplinks")
def set_ou_gplinks_api(
    payload: SetGplinksIn,
    dn_b64: str = Path(...),
    req: Request = None,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    dn = decode_dn(dn_b64)
    check_scope(admin, "ou:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    links = [l.model_dump() for l in payload.links]
    try:
        result = ad_gpo.set_ou_gplinks(conn, dn, cfg.base_dn, links, payload.block_inheritance)
        audit.write_log(
            db, admin.username, "gpo:set_links", "ou", dn, dn,
            params=str({"links": links, "block_inheritance": payload.block_inheritance}),
            operator_ip=_ip(req), domain_id=domain_id,
        )
        return result
    except Exception as exc:
        audit.write_log(
            db, admin.username, "gpo:set_links", "ou", dn, dn,
            params=str({"links": links, "block_inheritance": payload.block_inheritance}),
            operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise
    finally:
        conn.unbind()

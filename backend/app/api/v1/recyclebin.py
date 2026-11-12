from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import check_scope, get_current_admin, get_domain_config
from app.core.dn import decode_dn
from app.db import get_db
from app.models import AdminUser
from app.services import ad_recyclebin, audit, ldap_conn

router = APIRouter(prefix="/recyclebin", tags=["recyclebin"])


class RestoreIn(BaseModel):
    dn: str  # base64 编码的已删除对象 DN


def _ip(req: Request) -> str:
    return req.client.host if req.client else ""


@router.get("/status")
def status_api(
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        return ad_recyclebin.status(conn, cfg.base_dn)
    finally:
        conn.unbind()


@router.get("/deleted")
def list_deleted_api(
    domain_id: int = Query(..., description="域配置 ID"),
    object_type: str = Query("", description="过滤类型：user/group/ou/computer/other"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        return ad_recyclebin.list_deleted(conn, cfg.base_dn, object_type)
    finally:
        conn.unbind()


@router.post("/restore")
def restore_api(
    payload: RestoreIn,
    req: Request,
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    dn = decode_dn(payload.dn)
    check_scope(admin, "ou:write", domain_id, dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        result = ad_recyclebin.restore_object(conn, dn)
        audit.write_log(
            db, admin.username, "recycle:restore", "object", dn, dn,
            operator_ip=_ip(req), domain_id=domain_id,
        )
        return result
    except Exception as exc:
        audit.write_log(
            db, admin.username, "recycle:restore", "object", dn, dn,
            operator_ip=_ip(req), result="fail", error_msg=str(exc), domain_id=domain_id,
        )
        raise
    finally:
        conn.unbind()

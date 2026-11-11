from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.roles import ROLE_ADMIN, ROLE_AUDITOR, ROLE_SUPER
from app.db import get_db
from app.models import AdminUser, AuditLog
from app.schemas import AuditLogOut, AuditPage

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=AuditPage)
def list_logs(
    action: str | None = None,
    object_type: str | None = None,
    operator: str | None = None,
    domain_id: int | None = None,
    keyword: str | None = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN, ROLE_AUDITOR)),
) -> AuditPage:
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if object_type:
        q = q.filter(AuditLog.object_type == object_type)
    if operator:
        q = q.filter(AuditLog.operator == operator)
    if domain_id is not None:
        q = q.filter(AuditLog.domain_id == domain_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                AuditLog.target_name.ilike(like),
                AuditLog.object_dn.ilike(like),
                AuditLog.params.ilike(like),
                AuditLog.operator.ilike(like),
            )
        )
    total = q.count()
    logs = (
        q.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size).all()
    )
    return AuditPage(
        total=total,
        page=page,
        size=size,
        items=[AuditLogOut.model_validate(l) for l in logs],
    )


@router.get("/logs/{log_id}", response_model=AuditLogOut)
def log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN, ROLE_AUDITOR)),
) -> AuditLogOut:
    log = db.get(AuditLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="日志不存在")
    return AuditLogOut.model_validate(log)

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.roles import ROLE_ADMIN, ROLE_AUDITOR, ROLE_SUPER
from app.db import get_db
from app.models import AdminUser, AuditLog
from app.schemas import AuditLogOut, AuditPage

router = APIRouter(prefix="/audit", tags=["audit"])

# (模型字段, CSV 表头中文名)
EXPORT_COLUMNS = [
    ("id", "ID"),
    ("operator", "操作人"),
    ("operator_ip", "操作IP"),
    ("action", "操作"),
    ("object_type", "对象类型"),
    ("target_name", "目标名称"),
    ("object_dn", "对象DN"),
    ("params", "参数"),
    ("result", "结果"),
    ("error_msg", "错误信息"),
    ("created_at", "时间"),
]


def _apply_filters(
    q,
    action: str | None,
    object_type: str | None,
    operator: str | None,
    domain_id: int | None,
    keyword: str | None,
    start: datetime | None,
    end: datetime | None,
):
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
    if start:
        q = q.filter(AuditLog.created_at >= start)
    if end:
        q = q.filter(AuditLog.created_at <= end)
    return q


@router.get("/logs", response_model=AuditPage)
def list_logs(
    action: str | None = None,
    object_type: str | None = None,
    operator: str | None = None,
    domain_id: int | None = None,
    keyword: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN, ROLE_AUDITOR)),
) -> AuditPage:
    q = _apply_filters(db.query(AuditLog), action, object_type, operator, domain_id, keyword, start, end)
    total = q.count()
    logs = q.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size).all()
    return AuditPage(
        total=total,
        page=page,
        size=size,
        items=[AuditLogOut.model_validate(l) for l in logs],
    )


@router.get("/logs/export")
def export_logs(
    action: str | None = None,
    object_type: str | None = None,
    operator: str | None = None,
    domain_id: int | None = None,
    keyword: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN, ROLE_AUDITOR)),
) -> StreamingResponse:
    q = _apply_filters(db.query(AuditLog), action, object_type, operator, domain_id, keyword, start, end)
    logs = q.order_by(AuditLog.id.desc()).all()
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([header for _, header in EXPORT_COLUMNS])
    for l in logs:
        row = []
        for key, _ in EXPORT_COLUMNS:
            v = getattr(l, key)
            if v is None:
                row.append("")
            elif key == "created_at":
                row.append(v.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                row.append(str(v))
        writer.writerow(row)
    # 前置 UTF-8 BOM，确保 Excel 正确识别中文
    data = ("\ufeff" + buf.getvalue()).encode("utf-8")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=audit_logs_{ts}.csv"},
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

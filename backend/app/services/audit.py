from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger(__name__)


def write_log(
    db: Session,
    operator: str,
    action: str,
    object_type: str,
    object_dn: str = "",
    target_name: str = "",
    params: str = "",
    before: str = "",
    after: str = "",
    result: str = "ok",
    error_msg: str = "",
    operator_ip: str = "",
    domain_id: int | None = None,
) -> None:
    log = AuditLog(
        operator=operator,
        operator_ip=operator_ip,
        action=action,
        object_type=object_type,
        object_dn=object_dn,
        target_name=target_name,
        params=params,
        before=before,
        after=after,
        result=result,
        error_msg=error_msg,
        domain_id=domain_id,
        created_at=datetime.now(timezone.utc),
    )
    # 审计写入失败不得掩盖业务本身的错误（否则真实原因会被 500 顶掉）
    try:
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("写入审计日志失败")

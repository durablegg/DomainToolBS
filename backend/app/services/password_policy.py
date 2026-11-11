from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import AdminPasswordHistory

MIN_LENGTH = 8
HISTORY_SIZE = 3

_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def validate_complexity(password: str) -> None:
    """校验密码复杂度：至少 8 位，且同时包含大写字母、小写字母、数字、符号。"""
    if len(password or "") < MIN_LENGTH:
        raise ValueError(f"密码长度至少 {MIN_LENGTH} 位")
    if not re.search(r"[a-z]", password):
        raise ValueError("密码必须包含小写字母")
    if not re.search(r"[A-Z]", password):
        raise ValueError("密码必须包含大写字母")
    if not re.search(r"[0-9]", password):
        raise ValueError("密码必须包含数字")
    if not _SPECIAL_RE.search(password):
        raise ValueError("密码必须包含符号（如 !@#$%^&*）")


def validate_new_password(
    new_password: str,
    current_hash: str | None = None,
    history: list[str] | None = None,
) -> None:
    """修改/重置密码校验：复杂度 + 不得与当前密码相同 + 不得与最近 3 次历史密码相同。"""
    validate_complexity(new_password)
    if current_hash and verify_password(new_password, current_hash):
        raise ValueError("新密码不能与当前密码相同")
    for old_hash in (history or [])[:HISTORY_SIZE]:
        if verify_password(new_password, old_hash):
            raise ValueError(f"新密码不能与前 {HISTORY_SIZE} 次使用过的密码相同")


def get_recent_hashes(db: Session, admin_id: int) -> list[str]:
    """取最近使用过的（旧）密码哈希，最新在前，最多 HISTORY_SIZE 条。"""
    rows = (
        db.query(AdminPasswordHistory.password_hash)
        .filter_by(admin_id=admin_id)
        .order_by(AdminPasswordHistory.id.desc())
        .limit(HISTORY_SIZE)
        .all()
    )
    return [r[0] for r in rows]


def record_history(db: Session, admin_id: int, password_hash: str) -> None:
    """记录一条历史密码（仅存旧密码），并仅保留最近 HISTORY_SIZE 条。"""
    db.add(AdminPasswordHistory(admin_id=admin_id, password_hash=password_hash))
    keep = (
        db.query(AdminPasswordHistory.id)
        .filter_by(admin_id=admin_id)
        .order_by(AdminPasswordHistory.id.desc())
        .limit(HISTORY_SIZE)
        .all()
    )
    keep_ids = {r[0] for r in keep}
    stale = (
        db.query(AdminPasswordHistory)
        .filter(
            AdminPasswordHistory.admin_id == admin_id,
            ~AdminPasswordHistory.id.in_(keep_ids),
        )
        .all()
    )
    for row in stale:
        db.delete(row)

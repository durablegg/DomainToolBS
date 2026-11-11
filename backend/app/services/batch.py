from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from app.core.deps import check_scope
from app.models import AdminUser, BatchTask, BatchTaskItem, DomainConfig
from app.services import ad_user, ldap_conn

# CSV 列顺序（导入/导出一致，便于二次编辑）
CSV_COLUMNS = [
    "sAMAccountName",
    "displayName",
    "name",
    "password",
    "userPrincipalName",
    "mail",
    "department",
    "title",
    "telephoneNumber",
    "description",
    "password_never_expires",
    "must_change_next_logon",
]

REQUIRED = ("sAMAccountName", "displayName", "password")


def _to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "是")


def _read_rows(text: str):
    """读 CSV 并把表头归一化（去掉必填标记 * 与首尾空格），返回 (行列表, 归一化列名集合)。

    空行自动跳过，便于模板里附带说明/示例行而不会污染数据。
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV 为空或无表头")
    mapping = {f: f.replace("*", "").strip() for f in reader.fieldnames}
    rows: list[dict] = []
    for raw in reader:
        if all((v or "").strip() == "" for v in raw.values()):
            continue
        rows.append({mapping.get(k, k): (v or "").strip() for k, v in raw.items()})
    return rows, set(mapping.values())


def parse_users_csv(text: str) -> list[dict]:
    """解析用户导入 CSV，返回数据行列表；格式错误抛 ValueError。"""
    rows, fields = _read_rows(text)
    missing = [c for c in REQUIRED if c not in fields]
    if missing:
        raise ValueError(f"CSV 缺少必需列: {', '.join(missing)}")
    if not rows:
        raise ValueError("CSV 没有任何数据行")

    out: list[dict] = []
    for lineno, row in enumerate(rows, start=2):  # 表头为第 1 行
        sam = row.get("sAMAccountName", "")
        disp = row.get("displayName", "")
        pwd = row.get("password", "")
        if not sam or not disp or not pwd:
            raise ValueError(f"第 {lineno} 行：sAMAccountName / displayName / password 不能为空")
        out.append(
            {
                "sAMAccountName": sam,
                "displayName": disp,
                "name": row.get("name") or disp,
                "password": pwd,
                "userPrincipalName": row.get("userPrincipalName", ""),
                "mail": row.get("mail", ""),
                "department": row.get("department", ""),
                "title": row.get("title", ""),
                "telephoneNumber": row.get("telephoneNumber", ""),
                "description": row.get("description", ""),
                "password_never_expires": _to_bool(row.get("password_never_expires")),
                "must_change_next_logon": _to_bool(row.get("must_change_next_logon"), default=True),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# 批量删除
# --------------------------------------------------------------------------- #
DELETE_COLUMNS = ["sAMAccountName"]


def parse_delete_csv(text: str) -> list[dict]:
    rows, fields = _read_rows(text)
    if "sAMAccountName" not in fields:
        raise ValueError("CSV 缺少必需列: sAMAccountName")
    out: list[dict] = []
    for lineno, row in enumerate(rows, start=2):
        sam = row.get("sAMAccountName", "")
        if not sam:
            raise ValueError(f"第 {lineno} 行：sAMAccountName 不能为空")
        out.append({"sAMAccountName": sam})
    if not out:
        raise ValueError("CSV 没有任何数据行")
    return out


def render_delete_template() -> str:
    return render_users_csv([{"sAMAccountName": "zhangsan"}], ["sAMAccountName"], ("sAMAccountName",))


# --------------------------------------------------------------------------- #
# 批量修改
# --------------------------------------------------------------------------- #
UPDATE_COLUMNS = [
    "sAMAccountName",
    "displayName",
    "userPrincipalName",
    "mail",
    "department",
    "title",
    "telephoneNumber",
    "description",
    "password",
    "must_change_next_logon",
    "enabled",
]


def parse_update_csv(text: str) -> list[dict]:
    rows, fields = _read_rows(text)
    if "sAMAccountName" not in fields:
        raise ValueError("CSV 缺少必需列: sAMAccountName")
    out: list[dict] = []
    for lineno, row in enumerate(rows, start=2):
        sam = row.get("sAMAccountName", "")
        if not sam:
            raise ValueError(f"第 {lineno} 行：sAMAccountName 不能为空")
        item = {"sAMAccountName": sam}
        for col in UPDATE_COLUMNS[1:]:
            item[col] = row.get(col, "")
        out.append(item)
    if not out:
        raise ValueError("CSV 没有任何数据行")
    return out


def render_update_template() -> str:
    sample = {
        "sAMAccountName": "zhangsan",
        "displayName": "张三(改)",
        "userPrincipalName": "zhangsan@contoso.com",
        "mail": "zhangsan@contoso.com",
        "department": "IT",
        "title": "高级工程师",
        "telephoneNumber": "8002",
        "description": "批量修改示例",
        "password": "NewP@ssw0rd123",
        "must_change_next_logon": "true",
        "enabled": "true",
    }
    return render_users_csv([sample], UPDATE_COLUMNS, ("sAMAccountName",))


def render_users_csv(rows: list[dict], columns: list[str] | None = None, required: tuple = ()) -> str:
    columns = columns or CSV_COLUMNS
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM：让 Excel 以 UTF-8 正确识别中文
    # 必填列在表头加「 *」标记；解析端会忽略该标记（见 _read_rows）
    header = {c: f"{c} *" if c in required else c for c in columns}
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def render_users_template() -> str:
    sample = {
        "sAMAccountName": "zhangsan",
        "displayName": "张三",
        "name": "张三",
        "password": "P@ssw0rd123",
        "userPrincipalName": "zhangsan@contoso.com",
        "mail": "zhangsan@contoso.com",
        "department": "IT",
        "title": "工程师",
        "telephoneNumber": "8001",
        "description": "批量导入示例",
        "password_never_expires": "false",
        "must_change_next_logon": "true",
    }
    return render_users_csv([sample], CSV_COLUMNS, REQUIRED)


def run_import(task_id: int, rows: list[dict], target_ou_dn: str, created_by: str, domain_id: int) -> None:
    """后台导入 worker：独立会话 + 独立 LDAP 连接，逐行创建用户并更新任务明细。"""
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        task = db.get(BatchTask, task_id)
        if task is None:
            return
        cfg = db.get(DomainConfig, domain_id)
        if cfg is None:
            task.status = "failed"
            db.commit()
            return
        conn = ldap_conn.get_connection_from_config(cfg)
        try:
            ok = 0
            fail = 0
            for row in rows:
                item = (
                    db.query(BatchTaskItem)
                    .filter_by(task_id=task_id, target_name=row["sAMAccountName"])
                    .first()
                )
                data = dict(row)
                data["ou_dn"] = target_ou_dn
                try:
                    dn = ad_user.create_user(conn, data)
                    if item:
                        item.target_dn = dn
                        item.status = "ok"
                        item.message = "已创建"
                    ok += 1
                except Exception as exc:  # noqa: BLE001 - 单行失败不应中断整体任务
                    if item:
                        item.status = "fail"
                        item.message = str(exc)
                    fail += 1
                db.commit()
            task.ok_count = ok
            task.fail_count = fail
            task.status = "done"
            task.finished_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            conn.unbind()
    finally:
        db.close()


def _load_admin(db: SessionLocal, created_by: str) -> AdminUser | None:
    return db.query(AdminUser).filter_by(username=created_by).first()


def run_delete(task_id: int, rows: list[dict], created_by: str, domain_id: int) -> None:
    """后台批量删除 worker。"""
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        task = db.get(BatchTask, task_id)
        if task is None:
            return
        cfg = db.get(DomainConfig, domain_id)
        if cfg is None:
            task.status = "failed"
            db.commit()
            return
        admin = _load_admin(db, created_by)
        conn = ldap_conn.get_connection_from_config(cfg)
        try:
            ok = 0
            fail = 0
            for row in rows:
                sam = row["sAMAccountName"]
                item = (
                    db.query(BatchTaskItem)
                    .filter_by(task_id=task_id, target_name=sam)
                    .first()
                )
                try:
                    dn = ad_user.find_user_dn_by_sam(conn, sam, cfg.base_dn)
                    if not dn:
                        raise RuntimeError(f"用户不存在: {sam}")
                    if admin is not None:
                        check_scope(admin, "user:delete", domain_id, dn, db)
                    ad_user.delete_user(conn, dn)
                    if item:
                        item.target_dn = dn
                        item.status = "ok"
                        item.message = "已删除"
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    if item:
                        item.status = "fail"
                        item.message = str(exc)
                    fail += 1
                db.commit()
            task.ok_count = ok
            task.fail_count = fail
            task.status = "done"
            task.finished_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            conn.unbind()
    finally:
        db.close()


def run_update(task_id: int, rows: list[dict], created_by: str, domain_id: int) -> None:
    """后台批量修改 worker：支持修改属性、密码、启用状态。"""
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        task = db.get(BatchTask, task_id)
        if task is None:
            return
        cfg = db.get(DomainConfig, domain_id)
        if cfg is None:
            task.status = "failed"
            db.commit()
            return
        admin = _load_admin(db, created_by)
        conn = ldap_conn.get_connection_from_config(cfg)
        try:
            ok = 0
            fail = 0
            for row in rows:
                sam = row["sAMAccountName"]
                item = (
                    db.query(BatchTaskItem)
                    .filter_by(task_id=task_id, target_name=sam)
                    .first()
                )
                try:
                    dn = ad_user.find_user_dn_by_sam(conn, sam, cfg.base_dn)
                    if not dn:
                        raise RuntimeError(f"用户不存在: {sam}")
                    if admin is not None:
                        check_scope(admin, "user:write", domain_id, dn, db)
                    password = (row.get("password") or "").strip()
                    if password:
                        if admin is not None:
                            check_scope(admin, "user:reset_password", domain_id, dn, db)
                        ad_user.reset_password(
                            conn, dn, password,
                            _to_bool(row.get("must_change_next_logon"), default=True),
                        )
                    enabled = (row.get("enabled") or "").strip().lower()
                    if enabled in ("true", "false"):
                        ad_user.set_enabled(conn, dn, enabled == "true")
                    attr_data = {}
                    for key in ("displayName", "userPrincipalName", "mail", "department", "title", "telephoneNumber", "description"):
                        val = (row.get(key) or "").strip()
                        if val:
                            attr_data[key] = val
                    if attr_data:
                        ad_user.update_user(conn, dn, attr_data)
                    if item:
                        item.target_dn = dn
                        item.status = "ok"
                        item.message = "已更新"
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    if item:
                        item.status = "fail"
                        item.message = str(exc)
                    fail += 1
                db.commit()
            task.ok_count = ok
            task.fail_count = fail
            task.status = "done"
            task.finished_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            conn.unbind()
    finally:
        db.close()

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import check_scope, get_current_admin, get_domain_config
from app.db import get_db
from app.models import AdminUser, BatchTask, BatchTaskItem
from app.schemas import BatchTaskDetail, BatchTaskItemOut, BatchTaskOut
from app.services import ad_user, audit, batch as batch_svc, ldap_conn

router = APIRouter(prefix="/batch", tags=["batch"])


def _decode_csv(raw: bytes) -> str:
    """兼容 UTF-8(含 BOM) 与 Excel 默认保存的 GBK/GB18030（中文 Windows ANSI）。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(
        status_code=400,
        detail="CSV 编码无法识别，请用 UTF-8 或 GBK(GB18030) 编码保存",
    )


@router.get("/template/users")
def download_template() -> Response:
    return Response(
        batch_svc.render_users_template(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_template.csv"},
    )


@router.get("/template/delete-users")
def download_delete_template() -> Response:
    return Response(
        batch_svc.render_delete_template(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=delete_users_template.csv"},
    )


@router.get("/template/update-users")
def download_update_template() -> Response:
    return Response(
        batch_svc.render_update_template(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=update_users_template.csv"},
    )


@router.post("/import-users")
async def import_users(
    req: Request,
    file: UploadFile = File(...),
    target_ou_dn: str = Form(...),
    domain_id: int = Form(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    bg: BackgroundTasks = BackgroundTasks(),
) -> dict:
    check_scope(admin, "user:write", domain_id, target_ou_dn, db)
    cfg = get_domain_config(domain_id, admin, db)
    raw = await file.read()
    text = _decode_csv(raw)
    try:
        rows = batch_svc.parse_users_csv(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task = BatchTask(type="import_users", status="pending", total=len(rows), created_by=admin.username)
    db.add(task)
    db.flush()
    for row in rows:
        db.add(BatchTaskItem(task_id=task.id, target_name=row["sAMAccountName"], status="pending"))
    db.commit()

    bg.add_task(batch_svc.run_import, task.id, rows, target_ou_dn, admin.username, domain_id)
    audit.write_log(
        db, admin.username, "batch:import_users", "user",
        params=target_ou_dn, operator_ip=req.client.host if req.client else "", domain_id=domain_id,
    )
    return {"task_id": task.id, "total": task.total}


@router.post("/delete-users")
async def delete_users(
    req: Request,
    file: UploadFile = File(...),
    domain_id: int = Form(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    bg: BackgroundTasks = BackgroundTasks(),
) -> dict:
    cfg = get_domain_config(domain_id, admin, db)
    check_scope(admin, "user:delete", domain_id, cfg.base_dn, db)
    raw = await file.read()
    text = _decode_csv(raw)
    try:
        rows = batch_svc.parse_delete_csv(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task = BatchTask(type="delete_users", status="pending", total=len(rows), created_by=admin.username)
    db.add(task)
    db.flush()
    for row in rows:
        db.add(BatchTaskItem(task_id=task.id, target_name=row["sAMAccountName"], status="pending"))
    db.commit()

    bg.add_task(batch_svc.run_delete, task.id, rows, admin.username, domain_id)
    audit.write_log(
        db, admin.username, "batch:delete_users", "user",
        operator_ip=req.client.host if req.client else "", domain_id=domain_id,
    )
    return {"task_id": task.id, "total": task.total}


@router.post("/update-users")
async def update_users(
    req: Request,
    file: UploadFile = File(...),
    domain_id: int = Form(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    bg: BackgroundTasks = BackgroundTasks(),
) -> dict:
    cfg = get_domain_config(domain_id, admin, db)
    check_scope(admin, "user:write", domain_id, cfg.base_dn, db)
    raw = await file.read()
    text = _decode_csv(raw)
    try:
        rows = batch_svc.parse_update_csv(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task = BatchTask(type="update_users", status="pending", total=len(rows), created_by=admin.username)
    db.add(task)
    db.flush()
    for row in rows:
        db.add(BatchTaskItem(task_id=task.id, target_name=row["sAMAccountName"], status="pending"))
    db.commit()

    bg.add_task(batch_svc.run_update, task.id, rows, admin.username, domain_id)
    audit.write_log(
        db, admin.username, "batch:update_users", "user",
        operator_ip=req.client.host if req.client else "", domain_id=domain_id,
    )
    return {"task_id": task.id, "total": task.total}


@router.get("/export-users")
def export_users(
    ou: str | None = Query(None),
    domain_id: int = Query(..., description="域配置 ID"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> Response:
    cfg = get_domain_config(domain_id, admin, db)
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        base = ou or cfg.base_dn
        rows: list[dict] = []
        page, size = 1, 500
        while True:
            total, users = ad_user.search_users(conn, base, None, None, None, page, size)
            for u in users:
                rows.append(
                    {
                        "sAMAccountName": u.get("sAMAccountName") or "",
                        "displayName": u.get("displayName") or "",
                        "name": u.get("cn") or "",
                        "password": "",
                        "userPrincipalName": u.get("userPrincipalName") or "",
                        "mail": u.get("mail") or "",
                        "department": u.get("department") or "",
                        "title": u.get("title") or "",
                        "telephoneNumber": u.get("telephoneNumber") or "",
                        "description": u.get("description") or "",
                        "password_never_expires": str(u.get("pwd_never_expires", False)).lower(),
                        "must_change_next_logon": "false",
                    }
                )
            if page * size >= total:
                break
            page += 1
        csv_text = batch_svc.render_users_csv(rows)
    finally:
        conn.unbind()
    return Response(
        csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_export.csv"},
    )


@router.get("/tasks", response_model=list[BatchTaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> list[BatchTaskOut]:
    tasks = db.query(BatchTask).order_by(BatchTask.id.desc()).limit(50).all()
    return [BatchTaskOut.model_validate(t) for t in tasks]


@router.get("/tasks/{task_id}", response_model=BatchTaskDetail)
def task_detail(
    task_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> BatchTaskDetail:
    task = db.get(BatchTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    items = (
        db.query(BatchTaskItem).filter_by(task_id=task_id).order_by(BatchTaskItem.id).all()
    )
    detail = BatchTaskDetail.model_validate(task)
    detail.items = [BatchTaskItemOut.model_validate(i) for i in items]
    return detail

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_domain_config, require_role, require_superuser
from app.core.roles import ADMIN_FULL_PERMISSIONS, ROLE_ADMIN, ROLE_AUDITOR, ROLE_SUPER, ROLE_USER
from app.core.security import decrypt_secret, encrypt_secret
from app.db import get_db
from app.models import AdminScope, AdminUser, DomainConfig
from app.schemas import (
    DomainBriefOut,
    DomainCaUpdate,
    DomainCaMode,
    DomainConfigIn,
    DomainConfigOut,
    DomainInfo,
    DomainTestResult,
)
from app.services import ldap_conn

router = APIRouter(prefix="/domains", tags=["domains"])


def _full_out(cfg: DomainConfig) -> DomainConfigOut:
    return DomainConfigOut(
        id=cfg.id,
        name=cfg.name,
        host=cfg.host,
        port=cfg.port,
        use_ssl=cfg.use_ssl,
        base_dn=cfg.base_dn,
        bind_dn=cfg.bind_dn,
        is_default=cfg.is_default,
        has_password=bool(cfg.bind_pwd_enc),
        description=cfg.description or "",
        ca_cert=cfg.ca_cert or "",
        cert_not_after=cfg.cert_not_after,
        cert_trust=cfg.cert_trust or "none",
        ca_enabled=cfg.ca_enabled,
        updated_at=cfg.updated_at,
    )


def _brief_out(cfg: DomainConfig) -> DomainBriefOut:
    return DomainBriefOut(
        id=cfg.id,
        name=cfg.name,
        description=cfg.description or "",
        base_dn=cfg.base_dn,
    )


@router.get("", response_model=list)
def list_domains(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> list:
    cfgs = db.query(DomainConfig).order_by(DomainConfig.id).all()
    if admin.role == ROLE_USER:
        return [_brief_out(c) for c in cfgs]
    if admin.role == ROLE_ADMIN:
        # 仅返回被授权管辖的域（完整配置，便于编辑连接）
        allowed = {
            s.domain_id
            for s in admin.scope_rows
            if s.domain_id is not None
        }
        return [_full_out(c) for c in cfgs if c.id in allowed]
    if admin.role == ROLE_SUPER:
        return [_full_out(c) for c in cfgs]
    raise HTTPException(status_code=403, detail="审计员无域访问权限")


@router.post("", response_model=DomainConfigOut)
def create_domain(
    payload: DomainConfigIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN)),
) -> DomainConfigOut:
    # 若同名（name）或同 Base DN 的域已存在，则视为重复，禁止新建，需由超级管理员分配
    dup = (
        db.query(DomainConfig)
        .filter(
            or_(
                DomainConfig.name == payload.name,
                DomainConfig.base_dn == payload.base_dn,
            )
        )
        .first()
    )
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该域已存在（相同名称或 Base DN），不能重复新建，请由超级管理员分配",
        )

    is_first = db.query(DomainConfig).first() is None
    cfg = DomainConfig(
        name=payload.name,
        host=payload.host,
        port=payload.port,
        use_ssl=payload.use_ssl,
        base_dn=payload.base_dn,
        bind_dn=payload.bind_dn,
        bind_pwd_enc=encrypt_secret(payload.bind_password) if payload.bind_password else "",
        description=payload.description or "",
        ca_cert=payload.ca_cert or "",
        is_default=is_first,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)

    # 管理员新建的域，默认授权给该管理员（整个域 + 全部写权限）
    if admin.role == ROLE_ADMIN:
        db.add(
            AdminScope(
                admin_id=admin.id,
                domain_id=cfg.id,
                base_dn=cfg.base_dn,
                permissions=list(ADMIN_FULL_PERMISSIONS),
            )
        )
        db.commit()
    return _full_out(cfg)


@router.get("/{domain_id}", response_model=DomainConfigOut)
def get_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> DomainConfigOut:
    cfg = get_domain_config(domain_id, admin, db)
    if admin.role == ROLE_USER:
        # 普通用户只读，脱敏：隐藏连接主机与绑定账号
        return DomainConfigOut(
            id=cfg.id,
            name=cfg.name,
            host="",
            port=cfg.port,
            use_ssl=cfg.use_ssl,
            base_dn=cfg.base_dn,
            bind_dn="",
            is_default=cfg.is_default,
            has_password=bool(cfg.bind_pwd_enc),
            description=cfg.description or "",
            ca_cert="",
            cert_not_after=cfg.cert_not_after,
            cert_trust=cfg.cert_trust or "none",
            ca_enabled=cfg.ca_enabled,
            updated_at=cfg.updated_at,
        )
    return _full_out(cfg)


@router.put("/{domain_id}", response_model=DomainConfigOut)
def update_domain(
    domain_id: int,
    payload: DomainConfigIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN)),
) -> DomainConfigOut:
    cfg = get_domain_config(domain_id, admin, db)
    cfg.name = payload.name
    cfg.host = payload.host
    cfg.port = payload.port
    cfg.use_ssl = payload.use_ssl
    cfg.base_dn = payload.base_dn
    cfg.bind_dn = payload.bind_dn
    cfg.description = payload.description or ""
    cfg.ca_cert = payload.ca_cert or ""
    # CA 认证开关仅超级管理员可改；其余角色保存时忽略该字段
    if admin.role == ROLE_SUPER:
        cfg.ca_enabled = payload.ca_enabled
    if payload.bind_password:
        cfg.bind_pwd_enc = encrypt_secret(payload.bind_password)
    db.commit()
    db.refresh(cfg)
    return _full_out(cfg)


@router.delete("/{domain_id}")
def delete_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN)),
) -> dict:
    cfg = get_domain_config(domain_id, _, db)
    db.delete(cfg)
    db.commit()
    return {"ok": True, "id": domain_id}


@router.post("/{domain_id}/test", response_model=DomainTestResult)
def test_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN)),
) -> DomainTestResult:
    cfg = get_domain_config(domain_id, _, db)
    res = ldap_conn.test_connection(
        cfg.host, cfg.port, cfg.use_ssl, cfg.bind_dn,
        decrypt_secret(cfg.bind_pwd_enc) if cfg.bind_pwd_enc else "",
        cfg.ca_cert or "",
    )
    # 连通性测试顺带刷新证书信任状态与到期时间
    cfg.cert_trust = res.get("cert_trust", "none")
    cfg.cert_not_after = res.get("cert_not_after")
    db.commit()
    return DomainTestResult(**res)


@router.post("/test", response_model=DomainTestResult)
def test_payload(
    payload: DomainConfigIn,
    _: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN)),
) -> DomainTestResult:
    res = ldap_conn.test_connection(
        payload.host, payload.port, payload.use_ssl, payload.bind_dn, payload.bind_password,
        payload.ca_cert or "",
    )
    return DomainTestResult(**res)


@router.put("/{domain_id}/ca", response_model=DomainConfigOut)
def update_domain_ca(
    domain_id: int,
    payload: DomainCaUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role(ROLE_SUPER, ROLE_ADMIN)),
) -> DomainConfigOut:
    """导入/更新域控 CA 证书（超管 + 管理员）。导入后即时验证，成功走更安全的 CERT_REQUIRED 通道。"""
    cfg = get_domain_config(domain_id, _, db)
    cfg.ca_cert = payload.ca_cert or ""
    res = ldap_conn.test_connection(
        cfg.host, cfg.port, cfg.use_ssl, cfg.bind_dn,
        decrypt_secret(cfg.bind_pwd_enc) if cfg.bind_pwd_enc else "",
        cfg.ca_cert or "",
    )
    cfg.cert_trust = res.get("cert_trust", "none")
    cfg.cert_not_after = res.get("cert_not_after")
    db.commit()
    db.refresh(cfg)
    return _full_out(cfg)


@router.put("/{domain_id}/ca-mode", response_model=DomainConfigOut)
def update_domain_ca_mode(
    domain_id: int,
    payload: DomainCaMode,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_superuser),
) -> DomainConfigOut:
    """超级管理员专用：开启/关闭域的 CA 认证总开关。

    - 开启：按 cert_trust 校验，证书未通过时暂停非超管写操作（与现状一致）；
    - 关闭：不启用任何 CA 相关限制，管理员可自由操作。
    """
    cfg = get_domain_config(domain_id, _, db)
    cfg.ca_enabled = payload.enabled
    db.commit()
    db.refresh(cfg)
    return _full_out(cfg)


@router.get("/{domain_id}/info", response_model=DomainInfo)
def domain_info(
    domain_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> DomainInfo:
    cfg = get_domain_config(domain_id, admin, db)
    if admin.role == ROLE_AUDITOR:
        raise HTTPException(status_code=403, detail="审计员无目录访问权限")
    conn = ldap_conn.get_connection_from_config(cfg)
    try:
        data = ldap_conn._domain_info(conn)
        return DomainInfo(**data)
    finally:
        conn.unbind()

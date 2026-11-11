"""证书到期巡检调度（后台线程，每日一次）。

遍历已导入 CA 的域，重新校验对端证书并更新信任状态；对「即将到期 / 已过期」
的域写入一条 audit_log 告警（result=warn），便于超管在不手动测试时也能看到提醒。
不引入第三方调度依赖，使用守护线程 + 可打断休眠实现。
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import DomainConfig
from app.services import audit, ldap_conn

logger = logging.getLogger(__name__)

_CHECK_INTERVAL = 24 * 3600  # 每日巡检一次
_STOP = False
_THREAD: "threading.Thread | None" = None


def _days_left(not_after) -> int | None:
    if not not_after:
        return None
    na = not_after
    if na.tzinfo is None:
        na = na.replace(tzinfo=timezone.utc)
    return (na - datetime.now(timezone.utc)).days


def _check_once() -> None:
    db = SessionLocal()
    try:
        cfgs = (
            db.query(DomainConfig)
            .filter(
                DomainConfig.ca_cert != None,
                DomainConfig.ca_cert != "",
                DomainConfig.ca_enabled == True,
            )
            .all()
        )
        for cfg in cfgs:
            try:
                res = ldap_conn.test_connection(
                    cfg.host, cfg.port, cfg.use_ssl, cfg.bind_dn, "", cfg.ca_cert or ""
                )
            except Exception as exc:
                logger.warning("证书巡检失败 域[%s]: %s", cfg.name, exc)
                continue
            trust = res.get("cert_trust")
            not_after = res.get("cert_not_after")
            changed = False
            if trust != cfg.cert_trust:
                cfg.cert_trust = trust
                changed = True
            if not_after != cfg.cert_not_after:
                cfg.cert_not_after = not_after
                changed = True
            if changed:
                db.commit()
            if trust in ("expired", "expiring_soon"):
                days = _days_left(not_after)
                if trust == "expired":
                    msg = f"域[{cfg.name}]的 CA 证书已过期，写操作已暂停，请重新导入有效证书"
                else:
                    msg = f"域[{cfg.name}]的 CA 证书将在 {days} 天后到期，请及时更新"
                audit.write_log(
                    db, "system", "domain:cert_check", "domain", "", target_name=cfg.name,
                    result="warn", error_msg=msg, domain_id=cfg.id,
                )
                db.commit()
    finally:
        db.close()


def _loop() -> None:
    while not _STOP:
        try:
            _check_once()
        except Exception:
            logger.exception("证书到期巡检异常")
        for _ in range(_CHECK_INTERVAL // 5):
            if _STOP:
                return
            time.sleep(5)


def start_scheduler() -> None:
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _THREAD = threading.Thread(target=_loop, name="cert-scheduler", daemon=True)
    _THREAD.start()
    logger.info("证书到期巡检调度已启动")


def stop_scheduler() -> None:
    global _STOP
    _STOP = True

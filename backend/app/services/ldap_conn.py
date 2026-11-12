from __future__ import annotations

import logging
import os
import ssl
import tempfile
from datetime import datetime, timezone

import ldap3
from cryptography import x509
from ldap3 import ALL, Connection, SIMPLE, Server, Tls

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models import DomainConfig
from sqlalchemy.orm import Session

settings = get_settings()
logger = logging.getLogger(__name__)

# 证书进入"即将到期"提醒的剩余天数阈值
CERT_EXPIRING_SOON_DAYS = 30


def _build_server(host: str, port: int, use_ssl: bool, ca_cert: str | None = None):
    """构建 ldap3 Server。

    - 未配置 ca_cert：CERT_NONE（基础通道，不校验，兼容老环境/自签名）；
    - 配置了 ca_cert：CERT_REQUIRED + 该 CA（更安全的通道）。
    返回 (server, ca_path)，ca_path 为临时 CA 文件，调用方连接后负责删除。
    """
    ca_path = None
    if use_ssl:
        if ca_cert:
            with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
                f.write(ca_cert)
                ca_path = f.name
            tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs=ca_path)
        else:
            tls = Tls(validate=ssl.CERT_NONE)
    else:
        tls = None
    return Server(host, port=port, use_ssl=use_ssl, get_info=ALL, tls=tls), ca_path


def _cleanup_ca(ca_path: str | None) -> None:
    if ca_path:
        try:
            os.unlink(ca_path)
        except OSError:
            pass


def get_connection(
    host: str, port: int, use_ssl: bool, bind_dn: str, password: str, ca_cert: str | None = None
) -> Connection:
    server, ca_path = _build_server(host, port, use_ssl, ca_cert)
    try:
        # check_names=False：关闭 ldap3 客户端属性名校验。
        # 旧 schema 域控缺少部分属性（如 msDS-EnabledFeatureFlags）时，客户端校验会直接抛
        # LDAPInvalidAttributeError/LDAPKeyError；服务端本身能优雅忽略缺失属性，关掉后
        # 请求什么返回什么，由各服务自行兜底。
        return Connection(
            server, user=bind_dn, password=password, authentication=SIMPLE, auto_bind=True,
            check_names=False,
        )
    finally:
        _cleanup_ca(ca_path)


def get_connection_from_config(cfg: DomainConfig) -> Connection:
    """连接域控：有 CA 则优先走 CERT_REQUIRED；若 TLS 校验失败，回退基础通道（CERT_NONE），保证不中断业务。"""
    pwd = decrypt_secret(cfg.bind_pwd_enc) if cfg.bind_pwd_enc else ""
    try:
        return get_connection(cfg.host, cfg.port, cfg.use_ssl, cfg.bind_dn, pwd, cfg.ca_cert or None)
    except ldap3.core.exceptions.LDAPSocketOpenError:
        logger.warning("域[%s] CA 校验未通过，回退至不校验证书的基础通道", cfg.name)
        return get_connection(cfg.host, cfg.port, cfg.use_ssl, cfg.bind_dn, pwd, None)


def get_default_config(db: Session) -> DomainConfig | None:
    return (
        db.query(DomainConfig)
        .filter(DomainConfig.is_default == True)  # noqa: E712
        .order_by(DomainConfig.id)
        .first()
    )


def _domain_info(conn: Connection) -> dict:
    info = conn.server.info
    other = info.other or {}

    def first(key: str) -> str | None:
        vals = other.get(key)
        return vals[0] if vals else None

    return {
        "base_dn": first("defaultNamingContext"),
        "domain_name": first("rootDomainNamingContext"),
        "configuration_naming_context": first("configurationNamingContext"),
        "domain_functional_level": first("domainFunctionality"),
        "domain_controllers": list(other.get("dnsHostName") or []),
    }


def _probe_peer_cert(host: str, port: int):
    """用 CERT_NONE 抓取对端证书（不校验），返回 (pem, not_after_utc, subject) 或 None。"""
    try:
        pem = ssl.get_server_certificate((host, port), timeout=10)
        cert = x509.load_pem_x509_certificate(pem.encode())
    except Exception:
        return None
    not_after = cert.not_valid_after_utc
    subject = cert.subject.rfc4514_string()
    return pem, not_after, subject


def _verify_chain(host: str, port: int, ca_cert: str) -> bool:
    """用给定 CA 做 CERT_REQUIRED 握手，成功返回 True（代表对端证书可被该 CA 信任）。"""
    if not ca_cert:
        return False
    ca_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
            f.write(ca_cert)
            ca_path = f.name
        ctx = ssl.create_default_context()
        # 仅校验证书链（是否由导入的 CA 签发）与有效期，不校验主机名；
        # 域控常以 IP 或不同 FQDN 访问，主机名匹配放在链校验之外更稳。
        ctx.check_hostname = False
        ctx.load_verify_locations(cafile=ca_path)
        import socket

        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                ssock.getpeercert()  # 触发链校验
        return True
    except Exception:
        return False
    finally:
        _cleanup_ca(ca_path)


def test_connection(
    host: str, port: int, use_ssl: bool, bind_dn: str, password: str, ca_cert: str = ""
) -> dict:
    # 1) 抓取对端证书 + 2) 用导入 CA 做链校验，二者均走基础通道，不影响凭据可用性
    peer = _probe_peer_cert(host, port) if use_ssl else None
    cert_not_after = peer[1].astimezone(timezone.utc).replace(tzinfo=None) if peer else None
    cert_issuer = peer[2] if peer else None
    if use_ssl and ca_cert:
        chain_ok = _verify_chain(host, port, ca_cert)
        if not chain_ok:
            cert_trust = "untrusted"
        elif cert_not_after and cert_not_after < datetime.now(timezone.utc).replace(tzinfo=None):
            cert_trust = "expired"
        elif cert_not_after and (cert_not_after - datetime.now(timezone.utc).replace(tzinfo=None)).days < CERT_EXPIRING_SOON_DAYS:
            cert_trust = "expiring_soon"
        else:
            cert_trust = "ok"
    else:
        cert_trust = "none"

    # 3) 凭据绑定测试（始终走基础通道，确保功能不被证书校验阻断）
    try:
        conn = get_connection(host, port, use_ssl, bind_dn, password, None)
        info = _domain_info(conn)
        conn.unbind()
        ok = True
        message = "连接并绑定成功"
    except Exception as exc:  # ldap3 抛各种具体异常，统一兜底
        ok = False
        message = f"{type(exc).__name__}: {exc}"
        info = {}

    return {
        "ok": ok,
        "message": message,
        "base_dn": info.get("base_dn"),
        "domain_name": info.get("domain_name"),
        "domain_controllers": info.get("domain_controllers", []),
        "cert_not_after": cert_not_after,
        "cert_issuer": cert_issuer,
        "cert_trust": cert_trust,
    }

from __future__ import annotations

from ldap3 import BASE, SUBTREE
from ldap3.core.exceptions import LDAPException

# 显示已删除对象（含回收站对象）所需的 LDAP 控制位
SHOW_DELETED = ("1.2.840.113556.1.4.417", True, None)


def deleted_objects_dn(base_dn: str) -> str:
    return f"CN=Deleted Objects,{base_dn}"


def _safe_search(conn, *args, **kwargs) -> bool:
    """ldap3 check_names=True 时会在客户端校验属性名，schema 缺属性直接抛异常；
    统一捕获让上层降级逻辑有机会执行。"""
    try:
        return bool(conn.search(*args, **kwargs))
    except LDAPException:
        return False


def _attr(entry, name: str) -> str:
    """安全读取单值属性：服务器未返回该属性时返回空串，绝不抛异常。"""
    vals = entry.raw_attributes.get(name) or []
    v = vals[0] if vals else ""
    if isinstance(v, bytes):
        return v.decode("utf-8", "ignore")
    return str(v) if v else ""


def _attr_list(entry, name: str) -> list[str]:
    vals = entry.raw_attributes.get(name) or []
    return [v.decode("utf-8", "ignore") if isinstance(v, bytes) else str(v) for v in vals]


def _object_type(classes: list[str]) -> str:
    s = {c.lower() for c in classes}
    if "organizationalunit" in s:
        return "ou"
    if "computer" in s:
        return "computer"
    if "group" in s:
        return "group"
    if "user" in s:
        return "user"
    return "other"


def status(conn, base_dn: str) -> dict:
    """检测域是否启用 AD 回收站与功能级别；任何属性读不到都降级而不是报错。"""
    ok = _safe_search(
        conn,
        base_dn,
        "(objectClass=*)",
        BASE,
        attributes=["msDS-EnabledFeatureFlags", "msDS-Behavior-Version"],
    )
    entry = conn.entries[0] if (ok and conn.entries) else None
    if entry is None:
        ok = _safe_search(
            conn, base_dn, "(objectClass=*)", BASE, attributes=["msDS-Behavior-Version"]
        )
        entry = conn.entries[0] if (ok and conn.entries) else None

    flags_raw = _attr(entry, "msds-enabledfeatureflags") if entry else ""
    flags_known = flags_raw != ""
    try:
        enabled = bool(int(flags_raw) & 1) if flags_known else False
    except ValueError:
        enabled = False

    behavior_raw = _attr(entry, "msds-behavior-version") if entry else ""
    behavior_known = behavior_raw != ""
    try:
        level_ok = int(behavior_raw) >= 4 if behavior_known else True
    except ValueError:
        level_ok = True

    if enabled:
        message = ""
    elif not flags_known:
        message = (
            "无法确认回收站启用状态：当前域控未返回相关属性（功能级别可能低于 Windows Server 2008 R2，"
            "或 schema 较旧/非标准 AD）。请先在域控上确认功能级别并启用回收站后再使用恢复功能"
        )
    elif not level_ok:
        message = "域功能级别低于 Windows Server 2008 R2，无法启用回收站；请先提升林/域功能级别"
    else:
        message = (
            "域尚未启用回收站（一次性、不可逆）。请先在 AD 管理中心或 PowerShell 启用后再使用恢复功能："
            "Enable-ADOptionalFeature 'Recycle Bin Feature' -Scope ForestOrConfigurationSet -Target <林FQDN>"
        )
    return {"enabled": enabled, "functional_level_sufficient": level_ok, "message": message}


def list_deleted(conn, base_dn: str, object_type: str = "") -> list[dict]:
    """列出已删除对象；属性缺失时逐级降级属性集，字段全部用 raw_attributes 安全读取。"""
    base = deleted_objects_dn(base_dn)
    attempts = [
        ["msDS-LastKnownRDN", "lastKnownParent", "whenDeleted", "objectClass"],
        ["msDS-LastKnownRDN", "lastKnownParent", "objectClass"],
        ["objectClass"],
    ]
    entries = None
    for attrs in attempts:
        if _safe_search(conn, base, "(isDeleted=TRUE)", SUBTREE, attributes=attrs, controls=[SHOW_DELETED]):
            entries = conn.entries
            break
    if entries is None:
        raise RuntimeError(f"读取已删除对象失败: {conn.result}")

    items: list[dict] = []
    for e in entries:
        rdn = _attr(e, "msds-lastknownrdn")
        if not rdn:
            # 兜底：已删除对象的 cn 形如 "名称\nDEL:GUID"，取第一段
            rdn = _attr(e, "cn").split("\n")[0]
        name = rdn.split("=", 1)[-1] if "=" in rdn else rdn
        otype = _object_type(_attr_list(e, "objectclass"))
        if object_type and otype != object_type:
            continue
        items.append(
            {
                "dn": e.entry_dn,
                "name": name,
                "last_known_rdn": rdn,
                "parent": _attr(e, "lastknownparent"),
                "when_deleted": _attr(e, "whendeleted"),
                "object_type": otype,
            }
        )
    return items


def restore_object(conn, deleted_dn: str) -> dict:
    """将回收站中的对象还原回其原父容器（OU 的子对象不会一起还原，需逐个恢复）。"""
    ok = _safe_search(
        conn,
        deleted_dn,
        "(objectClass=*)",
        BASE,
        attributes=["msDS-LastKnownRDN", "lastKnownParent"],
        controls=[SHOW_DELETED],
    )
    entry = conn.entries[0] if (ok and conn.entries) else None
    if entry is None:
        raise RuntimeError("未找到该已删除对象，可能已被物理清除，或当前域控不支持读取其还原属性")
    rdn = _attr(entry, "msds-lastknownrdn")
    parent = _attr(entry, "lastknownparent")
    if not rdn or not parent:
        raise RuntimeError("缺少原 RDN 或原父容器，无法还原（可能已超期被物理删除）")
    if not conn.modify_dn(deleted_dn, rdn, new_superior=parent, controls=[SHOW_DELETED]):
        raise RuntimeError(f"还原失败: {conn.result}")
    return {"ok": True, "dn": deleted_dn}

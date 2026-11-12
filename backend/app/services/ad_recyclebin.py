from __future__ import annotations

from ldap3 import BASE, SUBTREE

# 显示已删除对象（含回收站对象）所需的 LDAP 控制位
SHOW_DELETED = ("1.2.840.113556.1.4.417", True, None)


def deleted_objects_dn(base_dn: str) -> str:
    return f"CN=Deleted Objects,{base_dn}"


def _object_type(classes) -> str:
    s = {str(c).lower() for c in classes}
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
    """检测域是否启用 AD 回收站（msDS-EnabledFeatureFlags 置位）与功能级别是否达标。"""
    conn.search(
        base_dn,
        "(objectClass=*)",
        SUBTREE,
        attributes=["msDS-EnabledFeatureFlags", "msDS-Behavior-Version"],
    )
    entry = conn.entries[0] if conn.entries else None
    flags = 0
    behavior = 0
    if entry:
        if entry.msDS_EnabledFeatureFlags:
            try:
                flags = int(entry.msDS_EnabledFeatureFlags.value)
            except (TypeError, ValueError):
                flags = 0
        if entry.msDS_Behavior_Version:
            try:
                behavior = int(entry.msDS_Behavior_Version.value)
            except (TypeError, ValueError):
                behavior = 0
    enabled = bool(flags & 1)
    level_ok = behavior >= 4  # Windows Server 2008 R2 及以上
    if enabled and level_ok:
        message = ""
    elif not level_ok:
        message = "域功能级别低于 Windows Server 2008 R2，无法启用回收站；请先提升林/域功能级别"
    else:
        message = "域尚未启用回收站（一次性、不可逆）。请先在 AD 管理中心或 PowerShell 启用后再使用恢复功能"
    return {"enabled": enabled, "functional_level_sufficient": level_ok, "message": message}


def list_deleted(conn, base_dn: str, object_type: str = "") -> list[dict]:
    conn.search(
        deleted_objects_dn(base_dn),
        "(isDeleted=TRUE)",
        SUBTREE,
        attributes=["msDS-LastKnownRDN", "lastKnownParent", "whenDeleted", "objectClass"],
        controls=[SHOW_DELETED],
    )
    items: list[dict] = []
    for e in conn.entries:
        rdn = str(e.msDS_LastKnownRDN.value) if e.msDS_LastKnownRDN else ""
        name = rdn.split("=", 1)[-1] if "=" in rdn else rdn
        otype = _object_type(e.objectClass.value if e.objectClass else [])
        if object_type and otype != object_type:
            continue
        items.append(
            {
                "dn": e.entry_dn,
                "name": name,
                "last_known_rdn": rdn,
                "parent": str(e.lastKnownParent.value) if e.lastKnownParent else "",
                "when_deleted": str(e.whenDeleted.value) if e.whenDeleted else "",
                "object_type": otype,
            }
        )
    return items


def restore_object(conn, deleted_dn: str) -> dict:
    """将回收站中的对象还原回其原父容器（OU 的子对象不会一起还原，需逐个恢复）。"""
    conn.search(
        deleted_dn,
        "(objectClass=*)",
        BASE,
        attributes=["msDS-LastKnownRDN", "lastKnownParent"],
        controls=[SHOW_DELETED],
    )
    entry = conn.entries[0] if conn.entries else None
    if not entry:
        raise RuntimeError("未找到该已删除对象，可能已被物理清除")
    rdn = str(entry.msDS_LastKnownRDN.value) if entry.msDS_LastKnownRDN else ""
    parent = str(entry.lastKnownParent.value) if entry.lastKnownParent else ""
    if not rdn or not parent:
        raise RuntimeError("缺少原 RDN 或原父容器，无法还原（可能已超期被物理删除）")
    if not conn.modify_dn(deleted_dn, rdn, new_superior=parent, controls=[SHOW_DELETED]):
        raise RuntimeError(f"还原失败: {conn.result}")
    return {"ok": True, "dn": deleted_dn}

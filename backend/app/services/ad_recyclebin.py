from __future__ import annotations

import logging
import re

from ldap3 import BASE, SUBTREE
from ldap3.core.exceptions import LDAPException

logger = logging.getLogger(__name__)

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
    """安全读取单值属性：服务器未返回该属性时返回空串，绝不抛异常。
    ldap3 Entry 的原始属性字典叫 entry_raw_attributes（键为小写）。"""
    vals = (entry.entry_raw_attributes or {}).get(name.lower()) or []
    v = vals[0] if vals else ""
    if isinstance(v, bytes):
        return v.decode("utf-8", "ignore")
    return str(v) if v else ""


def _attr_list(entry, name: str) -> list[str]:
    vals = (entry.entry_raw_attributes or {}).get(name.lower()) or []
    return [v.decode("utf-8", "ignore") if isinstance(v, bytes) else str(v) for v in vals]


def _fmt_time(raw: str) -> str:
    """LDAP 时间 20260615110914.0Z -> 2026-06-15 11:09；无法解析时原样返回。"""
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", raw or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}"
    return raw or ""


def _name_from_dn(dn: str) -> str:
    """从对象自身的 DN 解析原名：tombstone 的 RDN 形如 "原名\\n0ADEL:GUID"，
    取第一段；OU 没有 cn 属性时靠这个兜底。"""
    if not dn:
        return ""
    first = dn.split(",")[0]
    if "=" in first:
        first = first.split("=", 1)[1]
    # 去掉 tombstone 标记（\n0ADEL:guid / 0ADEL:guid / \nDEL:guid）
    first = re.split(r"[\n\\{}]*(?:0)?DEL:", first)[0]
    return first.strip()


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
    ok = _safe_search(conn, base_dn, "(objectClass=*)", BASE, attributes=["*"])
    entry = conn.entries[0] if (ok and conn.entries) else None
    if entry is None or "msds-enabledfeatureflags" not in (entry.entry_raw_attributes or {}):
        # 部分 DC 不随 '*' 返回该属性，显式指名请求（check_names 已关闭，可安全指名）
        ok2 = _safe_search(
            conn,
            base_dn,
            "(objectClass=*)",
            BASE,
            attributes=["msDS-EnabledFeatureFlags", "msDS-Behavior-Version"],
        )
        e2 = conn.entries[0] if (ok2 and conn.entries) else None
        if e2 is not None:
            entry = e2
    if entry is None:
        ok = _safe_search(
            conn, base_dn, "(objectClass=*)", BASE, attributes=["msDS-Behavior-Version"]
        )
        entry = conn.entries[0] if (ok and conn.entries) else None
    if entry is not None:
        logger.info(
            "recyclebin status: base=%s attrs=%s",
            base_dn,
            sorted(entry.entry_raw_attributes.keys()),
        )
    else:
        logger.warning("recyclebin status: 域头查询失败 ok=%s result=%s", ok, conn.result)

    flags_raw = _attr(entry, "msds-enabledfeatureflags") if entry else ""
    flags_known = flags_raw != ""
    enabled = False
    if flags_known:
        try:
            enabled = bool(int(flags_raw) & 1)
        except ValueError:
            enabled = False
    if not flags_known:
        # 终极兜底：查 Configuration 分区的可选功能对象（林级复制，任何 DC 都能查到），
        # Get-ADOptionalFeature 的 EnabledScopes 读的就是它的 msDS-EnabledFeatureBL
        feature_dn = (
            "CN=Recycle Bin Feature,CN=Optional Features,CN=Directory Service,"
            f"CN=Windows NT,CN=Services,CN=Configuration,{base_dn}"
        )
        ok3 = _safe_search(conn, feature_dn, "(objectClass=*)", BASE, attributes=["msDS-EnabledFeatureBL"])
        e3 = conn.entries[0] if (ok3 and conn.entries) else None
        if e3 and _attr_list(e3, "msds-enabledfeaturebl"):
            enabled = True
            flags_known = True

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
        ["*"],
        ["msDS-LastKnownRDN", "lastKnownParent", "whenDeleted", "whenChanged", "objectClass", "cn"],
        ["objectClass", "cn", "whenChanged"],
    ]
    entries = None
    for i, attrs in enumerate(attempts):
        ok = _safe_search(conn, base, "(isDeleted=TRUE)", SUBTREE, attributes=attrs, controls=[SHOW_DELETED])
        logger.info("recyclebin list_deleted: attempt=%s attrs=%s ok=%s n=%s", i, attrs, ok, len(conn.entries) if ok else "-")
        if ok:
            entries = conn.entries
            break
    if entries is None:
        raise RuntimeError(f"读取已删除对象失败: {conn.result}")

    items: list[dict] = []
    for e in entries:
        dn = e.entry_dn or ""
        if dn.lower() == base.lower():
            continue  # 跳过 Deleted Objects 容器自身
        rdn = _attr(e, "msds-lastknownrdn")
        if not rdn:
            # 兜底 1：已删除对象的 cn 形如 "名称\nDEL:GUID"，取第一段
            rdn = _attr(e, "cn").split("\n")[0]
        if not rdn:
            # 兜底 2：OU 没有 cn，从对象自身 DN 解析原名
            rdn = _name_from_dn(dn)
        name = rdn.split("=", 1)[-1] if "=" in rdn else rdn
        otype = _object_type(_attr_list(e, "objectclass"))
        if object_type and otype != object_type:
            continue
        items.append(
            {
                "dn": dn,
                "name": name,
                "last_known_rdn": rdn,
                "parent": _attr(e, "lastknownparent"),
                # 域控不返回 whenDeleted 时用 whenChanged 兜底（tombstone 的修改时间≈删除时间）
                "when_deleted": _fmt_time(_attr(e, "whendeleted") or _attr(e, "whenchanged")),
                "object_type": otype,
            }
        )
    # 最新删除的排在最前面
    items.sort(key=lambda x: x["when_deleted"], reverse=True)
    return items


def restore_object(conn, deleted_dn: str) -> dict:
    """将回收站中的对象还原回其原父容器（OU 的子对象不会一起还原，需逐个恢复）。"""
    ok = _safe_search(
        conn, deleted_dn, "(objectClass=*)", BASE, attributes=["*"], controls=[SHOW_DELETED]
    )
    if not ok or not conn.entries:
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
    if _attr(entry, "isrecycled").upper() == "TRUE":
        raise RuntimeError("该对象已进入 Recycled 状态（超过可恢复保留期），无法再恢复，只能等 AD 物理清除")
    if "=" not in rdn:
        # msDS-LastKnownRDN 只含 RDN 值（如 test66），modify_dn 需要完整 RDN（如 CN=test66）；
        # 属性类型从对象自身 DN 的第一段取（CN/OU）
        first_seg = (deleted_dn or "").split(",")[0]
        rdn_type = first_seg.split("=", 1)[0] if "=" in first_seg else "CN"
        rdn = f"{rdn_type}={rdn}"
    logger.info("recyclebin restore: dn=%s rdn=%s parent=%s", deleted_dn, rdn, parent)
    if not conn.modify_dn(deleted_dn, rdn, new_superior=parent, controls=[SHOW_DELETED]):
        logger.warning("recyclebin restore failed: %s", conn.result)
        # 定位 WILL_NOT_PERFORM 的常见原因，给出可操作的提示
        ok_p = _safe_search(conn, parent, "(objectClass=*)", BASE, attributes=["objectClass"])
        if not (ok_p and conn.entries):
            raise RuntimeError(
                f"原父容器 {parent} 当前不存在（可能也已被删除），请先在回收站恢复父容器，再还原该对象"
            )
        atype, _, aval = rdn.partition("=")
        ok_c = _safe_search(conn, parent, f"({atype}={aval})", BASE, attributes=["cn"])
        if ok_c and conn.entries:
            raise RuntimeError(
                f"父容器 {parent} 下已存在同名对象 {rdn}，请先重命名或移除同名对象后再恢复"
            )
        raise RuntimeError(f"还原失败: {conn.result}")
    return {"ok": True, "dn": deleted_dn}

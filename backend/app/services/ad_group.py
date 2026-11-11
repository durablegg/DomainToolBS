from __future__ import annotations

from ldap3 import BASE, MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, SUBTREE

from app.services import ad_utils

GROUP_ATTRS = [
    "sAMAccountName",
    "cn",
    "displayName",
    "name",
    "mail",
    "description",
    "managedBy",
    "groupType",
    "member",
    "distinguishedName",
    "whenCreated",
    "info",
]

SECURITY_FLAG = 0x80000000
GLOBAL = 0x00000002
DOMAIN_LOCAL = 0x00000004
UNIVERSAL = 0x00000008


def scope_to_grouptype(scope: str, security: bool) -> int:
    t = {"global": GLOBAL, "domainlocal": DOMAIN_LOCAL, "universal": UNIVERSAL}.get(scope, GLOBAL)
    return t | SECURITY_FLAG if security else t


def is_security(grouptype) -> bool:
    return bool(int(grouptype or 0) & SECURITY_FLAG)


def _build_filter(keyword=None, security=None) -> str:
    flt = "(&(objectClass=group)"
    if keyword:
        kw = ad_utils.escape_filter(keyword)
        flt += f"(|(sAMAccountName=*{kw}*)(cn=*{kw}*)(displayName=*{kw}*))"
    if security == "true":
        flt += "(groupType:1.2.840.113556.1.4.803:=2147483648)"
    elif security == "false":
        flt += "(!(groupType:1.2.840.113556.1.4.803:=2147483648))"
    flt += ")"
    return flt


def search_groups(conn, base_dn, keyword=None, security=None, page=1, size=20):
    flt = _build_filter(keyword, security)
    entries = ad_utils.paged_search_entries(conn, base_dn, flt, GROUP_ATTRS)
    total = len(entries)
    start = (page - 1) * size
    return total, [group_to_dict(e) for e in entries[start : start + size]]


def group_to_dict(entry) -> dict:
    gt = ad_utils.get_single(entry, "groupType")
    return {
        "dn": ad_utils.get_single(entry, "distinguishedName"),
        "sAMAccountName": ad_utils.get_single(entry, "sAMAccountName"),
        "cn": ad_utils.get_single(entry, "cn"),
        "displayName": ad_utils.get_single(entry, "displayName"),
        "name": ad_utils.get_single(entry, "name"),
        "mail": ad_utils.get_single(entry, "mail"),
        "description": ad_utils.get_single(entry, "description"),
        "managedBy": ad_utils.get_single(entry, "managedBy"),
        "group_type": int(gt) if gt else None,
        "is_security": is_security(gt),
        "member_count": len(ad_utils.get_list(entry, "member")),
        "when_created": ad_utils.parse_generalized(ad_utils.get_single(entry, "whenCreated")),
    }


def get_group(conn, dn) -> dict:
    conn.search(dn, "(objectClass=group)", BASE, attributes=GROUP_ATTRS)
    if not conn.entries:
        raise RuntimeError(f"组不存在: {dn}")
    return group_to_dict(conn.entries[0])


def create_group(conn, data: dict) -> str:
    ou_dn = data["ou_dn"]
    sam = data["sAMAccountName"]
    cn = data.get("name") or data["displayName"] or sam
    dn = f"CN={ad_utils.escape_cn(cn)},{ou_dn}"
    gt = scope_to_grouptype(data.get("scope", "global"), data.get("security", True))
    attrs = {
        "objectClass": ["top", "group"],
        "sAMAccountName": sam,
        "cn": cn,
        "groupType": gt,
    }
    for k in ("displayName", "mail", "description", "managedBy", "info"):
        if data.get(k):
            attrs[k] = data[k]
    if not conn.add(dn, attributes=attrs):
        raise RuntimeError(f"创建组失败: {conn.result}")
    return dn


def update_group(conn, dn: str, data: dict) -> None:
    mapping = {
        "displayName": "displayName",
        "mail": "mail",
        "description": "description",
        "managedBy": "managedBy",
        "info": "info",
    }
    # 先读当前值：避免对“本就不存在”的属性做删除，否则 AD 返回 1005 (IN_ATTRIBUTE_OR_VAL)
    conn.search(dn, "(objectClass=*)", BASE, attributes=list(set(mapping.values())))
    current = conn.entries[0] if conn.entries else None
    changes = {}
    for key, attr in mapping.items():
        if key not in data:
            continue
        val = data.get(key)
        if val is None:
            continue
        old = ad_utils.get_single(current, attr) if current is not None else None
        old = old if old is not None else ""
        if val == old:
            continue  # 未变化，跳过
        if val == "":
            changes[attr] = [(MODIFY_DELETE, [])]  # 原本有值 -> 清空
        else:
            changes[attr] = [(MODIFY_REPLACE, [val])]
    if not changes:
        return
    if not conn.modify(dn, changes):
        raise RuntimeError(f"更新组失败: {conn.result}")


def delete_group(conn, dn: str) -> None:
    if not conn.delete(dn):
        raise RuntimeError(f"删除组失败: {conn.result}")


def resolve_member_dn(conn, base_dn: str, identifier: str) -> str:
    """标识符可以是 DN，也可以是 sAMAccountName（自动解析）。"""
    if "=" in identifier:
        return identifier
    flt = f"(sAMAccountName={ad_utils.escape_filter(identifier)})"
    conn.search(base_dn, flt, SUBTREE, attributes=["distinguishedName"])
    if not conn.entries:
        raise RuntimeError(f"找不到对象: {identifier}")
    return ad_utils.get_single(conn.entries[0], "distinguishedName")


def add_members(conn, base_dn: str, group_dn: str, identifiers: list) -> int:
    dns = [resolve_member_dn(conn, base_dn, i) for i in identifiers]
    for d in dns:
        if not conn.modify(group_dn, {"member": [(MODIFY_ADD, [d])]}):
            # 19 = constraintViolation，通常表示该成员已存在，可忽略
            if conn.result.get("result") != 19:
                raise RuntimeError(f"添加成员失败 {d}: {conn.result}")
    return len(dns)


def remove_members(conn, group_dn: str, dns: list) -> None:
    for d in dns:
        if not conn.modify(group_dn, {"member": [(MODIFY_DELETE, [d])]}):
            raise RuntimeError(f"移除成员失败 {d}: {conn.result}")


def list_members(conn, group_dn: str, base_dn: str, page=1, size=20):
    conn.search(group_dn, "(objectClass=group)", BASE, attributes=["member"])
    members = ad_utils.get_list(conn.entries[0], "member") if conn.entries else []
    total = len(members)
    start = (page - 1) * size
    page_dns = members[start : start + size]
    resolved = []
    for md in page_dns:
        conn.search(
            md, "(objectClass=*)", BASE,
            attributes=["sAMAccountName", "cn", "displayName", "objectClass"],
        )
        if conn.entries:
            e = conn.entries[0]
            oc = ad_utils.get_list(e, "objectClass")
            kind = (
                "user" if "user" in oc
                else "computer" if "computer" in oc
                else "group" if "group" in oc
                else "unknown"
            )
            resolved.append({
                "dn": md,
                "sAMAccountName": ad_utils.get_single(e, "sAMAccountName"),
                "displayName": ad_utils.get_single(e, "displayName") or ad_utils.get_single(e, "cn"),
                "kind": kind,
            })
        else:
            resolved.append({"dn": md, "sAMAccountName": None, "displayName": None, "kind": "unknown"})
    return total, resolved

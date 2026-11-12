from __future__ import annotations

from ldap3 import LEVEL, SUBTREE

from app.core.dn import parent_dn


def _escape_rdn(value: str) -> str:
    """转义 RDN 中需转义的字符（, + " \\ < > ; 等）。"""
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace("+", "\\+")
        .replace('"', '\\"')
        .replace("<", "\\<")
        .replace(">", "\\>")
        .replace(";", "\\;")
    )


def _to_str(value) -> str | None:
    if value is None:
        return None
    try:
        return value.value if hasattr(value, "value") else value
    except Exception:
        return None


def get_ou_tree(conn, base_dn: str) -> list[dict]:
    conn.search(
        base_dn,
        "(objectClass=organizationalUnit)",
        SUBTREE,
        attributes=["ou", "name", "distinguishedName", "description"],
    )
    nodes: dict[str, dict] = {}
    for entry in conn.entries:
        dn = _to_str(entry.distinguishedName)
        name = _to_str(entry.name) or _to_str(entry.ou) or dn or ""
        nodes[dn] = {
            "dn": dn,
            "name": name,
            "ou": _to_str(entry.ou),
            "description": _to_str(entry.description),
            "parent_dn": parent_dn(dn),
            "sub_ous": [],
        }
    tree: list[dict] = []
    for node in nodes.values():
        parent = node["parent_dn"]
        if parent and parent in nodes:
            nodes[parent]["sub_ous"].append(node)
        else:
            tree.append(node)
    return tree


def count_users(conn, ou_dn: str) -> int:
    conn.search(
        ou_dn,
        "(&(objectCategory=person)(objectClass=user))",
        SUBTREE,
        attributes=["sAMAccountName"],
    )
    return len(conn.entries)


def create_ou(conn, parent_dn: str, name: str, description: str = "") -> str:
    dn = f"OU={_escape_rdn(name)},{parent_dn}"
    attrs = {"objectClass": ["top", "organizationalUnit"], "ou": name}
    if description:
        attrs["description"] = description
    if not conn.add(dn, attributes=attrs):
        raise RuntimeError(f"创建 OU 失败: {conn.result}")
    return dn


def rename_ou(conn, dn: str, new_name: str) -> None:
    if not conn.modify_dn(dn, f"OU={_escape_rdn(new_name)}"):
        raise RuntimeError(f"重命名 OU 失败: {conn.result}")


def _count_children(conn, dn: str) -> dict:
    """统计 OU 直接子对象的分类数量（OU/用户/组/计算机/其他）。"""
    conn.search(dn, "(objectClass=*)", LEVEL, attributes=["objectClass"])
    counts = {"ou": 0, "user": 0, "group": 0, "computer": 0, "other": 0}
    for entry in conn.entries:
        ocs = {str(v).lower() for v in entry.objectClass}
        if "organizationalunit" in ocs:
            counts["ou"] += 1
        elif "computer" in ocs:
            counts["computer"] += 1
        elif "group" in ocs:
            counts["group"] += 1
        elif "user" in ocs:
            counts["user"] += 1
        else:
            counts["other"] += 1
    return counts


def delete_ou(conn, dn: str) -> None:
    # 非空 OU 不允许直接删除（对齐 AD 安全策略），先给出友好提示而非裸报错
    counts = _count_children(conn, dn)
    total = sum(counts.values())
    if total > 0:
        label_map = {"ou": "OU", "user": "用户", "group": "组", "computer": "计算机", "other": "其他"}
        parts = [f"{label_map[k]} {v}" for k, v in counts.items() if v]
        raise RuntimeError(
            f"该 OU 非空，包含 {total} 个子对象（{', '.join(parts)}），请先清空后再删除"
        )
    if not conn.delete(dn):
        res = conn.result or {}
        desc = str(res.get("description") or "").lower()
        msg = str(res.get("message") or "")
        if "protected" in desc or "protected" in msg.lower():
            raise RuntimeError(
                "删除失败：该 OU 可能设置了「防止对象被意外删除」，请先在域控取消该保护后再删除"
            )
        raise RuntimeError(f"删除 OU 失败：{res.get('description')} {msg}".strip())


def move_ou(conn, dn: str, target_ou_dn: str) -> None:
    if not conn.modify_dn(dn, dn.split(",", 1)[0], new_superior=target_ou_dn):
        raise RuntimeError(f"移动 OU 失败: {conn.result}")

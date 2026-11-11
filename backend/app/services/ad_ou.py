from __future__ import annotations

from ldap3 import SUBTREE

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


def delete_ou(conn, dn: str) -> None:
    if not conn.delete(dn):
        raise RuntimeError(f"删除 OU 失败: {conn.result}")


def move_ou(conn, dn: str, target_ou_dn: str) -> None:
    if not conn.modify_dn(dn, dn.split(",", 1)[0], new_superior=target_ou_dn):
        raise RuntimeError(f"移动 OU 失败: {conn.result}")

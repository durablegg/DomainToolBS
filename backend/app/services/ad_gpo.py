from __future__ import annotations

from ldap3 import MODIFY_REPLACE, SUBTREE


def policies_dn(base_dn: str) -> str:
    return f"CN=Policies,CN=System,{base_dn}"


def list_gpos(conn, base_dn: str) -> list[dict]:
    """列出域内所有 GPO（AD 元数据：GUID + 显示名 + 修改时间）。"""
    conn.search(
        policies_dn(base_dn),
        "(objectClass=groupPolicyContainer)",
        SUBTREE,
        attributes=["cn", "displayName", "whenChanged", "description"],
    )
    items: list[dict] = []
    for e in conn.entries:
        items.append(
            {
                "guid": str(e.cn.value) if e.cn else "",
                "display_name": str(e.displayName.value) if e.displayName else (str(e.cn.value) if e.cn else ""),
                "when_changed": str(e.whenChanged.value) if e.whenChanged else "",
                "description": str(e.description.value) if e.description else "",
            }
        )
    return items


def _parse_gplink(gplink: str) -> list[dict]:
    """解析 OU 的 gPLink 为结构化列表。

    gPLink 格式：[LDAP://CN={GUID},CN=Policies,CN=System,DC=x;0]
    末尾标志：0=已启用, 1=已禁用, 2=强制(不覆盖)。
    """
    out: list[dict] = []
    if not gplink:
        return out
    for raw in gplink.split("]["):
        raw = raw.strip().strip("[]")
        if "LDAP://" not in raw:
            continue
        dn, _, flag = raw.rpartition(";")
        guid = dn.rstrip("/").split("=")[-1].strip("{}")
        flag = (flag or "0").strip()
        enforced = flag == "2"
        disabled = flag == "1"
        out.append(
            {
                "guid": guid,
                "dn": dn.replace("LDAP://", ""),
                "disabled": disabled,
                "enforced": enforced,
            }
        )
    return out


def get_ou_gplinks(conn, ou_dn: str) -> dict:
    conn.search(ou_dn, "(objectClass=*)", SUBTREE, attributes=["gPLink", "gPOptions"])
    entry = conn.entries[0] if conn.entries else None
    gplink = str(entry.gPLink.value) if (entry and entry.gPLink) else ""
    raw_opts = entry.gPOptions.value if (entry and entry.gPOptions and entry.gPOptions.value not in (None, "")) else 0
    try:
        gpoptions = int(raw_opts)
    except (TypeError, ValueError):
        gpoptions = 0
    return {
        "gplink": gplink,
        "gpoptions": gpoptions,
        "block_inheritance": gpoptions == 1,
        "links": _parse_gplink(gplink),
    }


def _build_gplink(base_dn: str, links: list[dict]) -> str:
    parts: list[str] = []
    for link in links:
        guid = link["guid"]
        if link.get("enforced"):
            flag = "2"
        elif link.get("disabled"):
            flag = "1"
        else:
            flag = "0"
        dn = f"CN={{{guid}}},{policies_dn(base_dn)}"
        parts.append(f"[LDAP://{dn};{flag}]")
    return "".join(parts)


def set_ou_gplinks(conn, ou_dn: str, base_dn: str, links: list[dict], block_inheritance: bool) -> dict:
    """按给定的链接集合与阻止继承开关，重建并写回 OU 的 gPLink / gPOptions。"""
    gplink = _build_gplink(base_dn, links)
    gpoptions = 1 if block_inheritance else 0
    changes = {
        "gPLink": [(MODIFY_REPLACE, [gplink] if gplink else [])],
        "gPOptions": [(MODIFY_REPLACE, [gpoptions])],
    }
    if not conn.modify(ou_dn, changes):
        raise RuntimeError(f"更新 OU 的 GPO 链接失败: {conn.result}")
    return {"gplink": gplink, "gpoptions": gpoptions, "links": _parse_gplink(gplink)}

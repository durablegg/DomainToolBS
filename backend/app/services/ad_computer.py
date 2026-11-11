from __future__ import annotations

from ldap3 import BASE, MODIFY_REPLACE, SUBTREE

from app.core.dn import parent_dn
from app.services import ad_utils

COMPUTER_ATTRS = [
    "sAMAccountName",
    "cn",
    "displayName",
    "name",
    "description",
    "userAccountControl",
    "operatingSystem",
    "operatingSystemVersion",
    "distinguishedName",
    "dNSHostName",
    "whenCreated",
    "lastLogonTimestamp",
]


def _build_filter(keyword=None, enabled=None) -> str:
    flt = "(&(objectClass=computer)"
    if keyword:
        kw = ad_utils.escape_filter(keyword)
        flt += f"(|(sAMAccountName=*{kw}*)(cn=*{kw}*)(displayName=*{kw}*))"
    if enabled == "false":
        flt += "(userAccountControl:1.2.840.113556.1.4.803:=2)"
    elif enabled == "true":
        flt += "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
    flt += ")"
    return flt


def search_computers(conn, base_dn, keyword=None, enabled=None, page=1, size=20):
    flt = _build_filter(keyword, enabled)
    entries = ad_utils.paged_search_entries(conn, base_dn, flt, COMPUTER_ATTRS)
    total = len(entries)
    start = (page - 1) * size
    return total, [computer_to_dict(e) for e in entries[start : start + size]]


def computer_to_dict(entry) -> dict:
    uac = ad_utils.get_single(entry, "userAccountControl")
    flags = ad_utils.decode_uac(uac)
    dn = ad_utils.get_single(entry, "distinguishedName")
    return {
        "dn": dn,
        "ou_dn": parent_dn(dn),
        "sAMAccountName": ad_utils.get_single(entry, "sAMAccountName"),
        "cn": ad_utils.get_single(entry, "cn"),
        "displayName": ad_utils.get_single(entry, "displayName"),
        "name": ad_utils.get_single(entry, "name"),
        "description": ad_utils.get_single(entry, "description"),
        "operatingSystem": ad_utils.get_single(entry, "operatingSystem"),
        "operatingSystemVersion": ad_utils.get_single(entry, "operatingSystemVersion"),
        "dnsHostname": ad_utils.get_single(entry, "dNSHostName"),
        "enabled": flags["enabled"],
        "when_created": ad_utils.parse_generalized(ad_utils.get_single(entry, "whenCreated")),
        "last_logon": ad_utils.filetime_to_dt(ad_utils.get_single(entry, "lastLogonTimestamp")),
    }


def get_computer(conn, dn) -> dict:
    conn.search(dn, "(objectClass=computer)", BASE, attributes=COMPUTER_ATTRS)
    if not conn.entries:
        raise RuntimeError(f"计算机不存在: {dn}")
    return computer_to_dict(conn.entries[0])


def get_uac(conn, dn) -> int:
    conn.search(dn, "(objectClass=computer)", BASE, attributes=["userAccountControl"])
    v = ad_utils.get_single(conn.entries[0], "userAccountControl")
    return int(v) if v else 0


def set_enabled(conn, dn: str, enabled: bool) -> None:
    uac = get_uac(conn, dn)
    new = ad_utils.set_uac_flag(uac, ad_utils.UAC_ACCOUNT_DISABLE, not enabled)
    if not conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, [new])]}):
        raise RuntimeError(f"修改计算机状态失败: {conn.result}")


def move_computer(conn, dn: str, target_ou_dn: str) -> None:
    if not conn.modify_dn(dn, dn.split(",", 1)[0], new_superior=target_ou_dn):
        raise RuntimeError(f"移动计算机失败: {conn.result}")


def delete_computer(conn, dn: str) -> None:
    if not conn.delete(dn):
        raise RuntimeError(f"删除计算机失败: {conn.result}")

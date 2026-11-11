from __future__ import annotations

from datetime import datetime, timezone
from ldap3 import BASE, MODIFY_DELETE, MODIFY_REPLACE

from app.core.dn import parent_dn
from app.services import ad_utils

USER_ATTRS = [
    "sAMAccountName",
    "cn",
    "displayName",
    "name",
    "mail",
    "userPrincipalName",
    "description",
    "department",
    "title",
    "telephoneNumber",
    "userAccountControl",
    "msDS-User-Account-Control-Computed",
    "lockoutTime",
    "pwdLastSet",
    "lastLogonTimestamp",
    "accountExpires",
    "whenCreated",
    "memberOf",
    "distinguishedName",
]


# --------------------------------------------------------------------------- #
# 查询
# --------------------------------------------------------------------------- #
def _build_filter(keyword=None, enabled=None, locked=None) -> str:
    flt = "(&(objectCategory=person)(objectClass=user)"
    if keyword:
        kw = ad_utils.escape_filter(keyword)
        flt += (
            f"(|(sAMAccountName=*{kw}*)(cn=*{kw}*)"
            f"(displayName=*{kw}*)(mail=*{kw}*))"
        )
    if enabled == "false":
        flt += "(userAccountControl:1.2.840.113556.1.4.803:=2)"
    elif enabled == "true":
        flt += "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
    # 锁定状态以 lockoutTime 为准（UAC 的 LOCKOUT 位在 AD 中常不可靠）
    if locked == "true":
        flt += "(lockoutTime>=1)"
    elif locked == "false":
        flt += "(!(lockoutTime>=1))"
    flt += ")"
    return flt


def get_domain_lockout_duration(conn) -> int:
    """返回域账户锁定观察时长（秒）；0 表示永久锁定（需管理员手动解锁）。"""
    try:
        conn.search("", "(objectClass=*)", BASE, attributes=["defaultNamingContext"])
        nc = conn.entries[0].defaultNamingContext.value if conn.entries else None
        if not nc:
            return 0
        conn.search(nc, "(objectClass=domainDNS)", BASE, attributes=["lockoutDuration"])
        raw = conn.entries[0].lockoutDuration.value if conn.entries else None
        if raw is None:
            return 0
        v = int(raw)
        if v == 0:
            return 0
        return int(abs(v) / 10_000_000)
    except Exception:
        return 0


def search_users(conn, base_dn, keyword=None, enabled=None, locked=None, page=1, size=20):
    flt = _build_filter(keyword, enabled, locked)
    entries = ad_utils.paged_search_entries(conn, base_dn, flt, USER_ATTRS)
    lockout_duration = get_domain_lockout_duration(conn)
    total = len(entries)
    start = (page - 1) * size
    page_entries = entries[start : start + size]
    return total, [user_to_dict(e, lockout_duration) for e in page_entries]


def user_to_dict(entry, lockout_duration: int = 0) -> dict:
    uac = ad_utils.get_single(entry, "userAccountControl")
    flags = ad_utils.decode_uac(uac)
    # 锁定判定三重兜底：
    # 1) msDS-User-Account-Control-Computed（AD 实时计算属性，最权威）
    # 2) userAccountControl 的 LOCKOUT 位（部分环境不维护，仅兜底）
    # 3) lockoutTime != 0（锁定写入的时间戳）
    computed_flags = ad_utils.decode_uac(
        ad_utils.get_single(entry, "msDS-User-Account-Control-Computed")
    )
    lockout_time = ad_utils.get_single(entry, "lockoutTime")
    locked = (
        computed_flags["locked"] or flags["locked"] or ad_utils.is_locked(lockout_time)
    )
    lockout_remaining = None
    if locked and lockout_duration:
        lt = ad_utils.filetime_to_dt(lockout_time)
        if lt is not None:
            unlock_at = lt.timestamp() + lockout_duration
            now = datetime.now(timezone.utc).timestamp()
            if unlock_at > now:
                lockout_remaining = int(unlock_at - now)
    dn = ad_utils.get_single(entry, "distinguishedName")
    return {
        "dn": dn,
        "ou_dn": parent_dn(dn),
        "sAMAccountName": ad_utils.get_single(entry, "sAMAccountName"),
        "cn": ad_utils.get_single(entry, "cn"),
        "displayName": ad_utils.get_single(entry, "displayName"),
        "name": ad_utils.get_single(entry, "name"),
        "mail": ad_utils.get_single(entry, "mail"),
        "userPrincipalName": ad_utils.get_single(entry, "userPrincipalName"),
        "description": ad_utils.get_single(entry, "description"),
        "department": ad_utils.get_single(entry, "department"),
        "title": ad_utils.get_single(entry, "title"),
        "telephoneNumber": ad_utils.get_single(entry, "telephoneNumber"),
        "memberOf": ad_utils.get_list(entry, "memberOf"),
        "enabled": flags["enabled"],
        "locked": locked,
        "lockout_remaining": lockout_remaining,
        "pwd_never_expires": flags["pwd_never_expires"],
        "pwd_not_required": flags["pwd_not_required"],
        "must_change_password": ad_utils.must_change_password(
            ad_utils.get_single(entry, "pwdLastSet")
        ),
        "pwd_last_set": ad_utils.filetime_to_dt(ad_utils.get_single(entry, "pwdLastSet")),
        "last_logon": ad_utils.filetime_to_dt(
            ad_utils.get_single(entry, "lastLogonTimestamp")
        ),
        "account_expires": ad_utils.filetime_to_dt(
            ad_utils.get_single(entry, "accountExpires")
        ),
        "when_created": ad_utils.parse_generalized(
            ad_utils.get_single(entry, "whenCreated")
        ),
    }


def get_user(conn, dn) -> dict:
    conn.search(dn, "(objectClass=user)", BASE, attributes=USER_ATTRS)
    if not conn.entries:
        raise RuntimeError(f"用户不存在: {dn}")
    return user_to_dict(conn.entries[0], get_domain_lockout_duration(conn))


def get_user_uac(conn, dn) -> int:
    conn.search(dn, "(objectClass=user)", BASE, attributes=["userAccountControl"])
    v = ad_utils.get_single(conn.entries[0], "userAccountControl")
    return int(v) if v else 0


# --------------------------------------------------------------------------- #
# 写操作
# --------------------------------------------------------------------------- #
def _password_error(result: dict | None) -> str:
    """AD 拒绝改密（WILL_NOT_PERFORM / 0x52D）的常见原因说明。"""
    msg = (result or {}).get("message") or "无详细信息"
    return (
        "设置密码被 AD 拒绝（WILL_NOT_PERFORM）。常见原因："
        "1) 连接未加密——改密码必须走 LDAPS(636) 或 StartTLS；"
        "2) 新密码不满足域密码策略（长度/复杂度/历史/最短使用期限）。"
        f"AD 原始返回: {msg}"
    )


def _set_password(conn, dn: str, password: str) -> None:
    """unicodePwd 必须是 UTF-16LE 编码且外加双引号；必须走加密连接（LDAPS/StartTLS）。"""
    enc = f'"{password}"'.encode("utf-16-le")
    if not conn.modify(dn, {"unicodePwd": [(MODIFY_REPLACE, [enc])]}):
        raise RuntimeError(_password_error(conn.result))


def create_user(conn, data: dict) -> str:
    ou_dn = data["ou_dn"]
    sam = data["sAMAccountName"]
    cn = data.get("name") or data["displayName"] or sam
    dn = f"CN={ad_utils.escape_cn(cn)},{ou_dn}"
    attrs = {
        "objectClass": ["top", "person", "organizationalPerson", "user"],
        "sAMAccountName": sam,
        "cn": cn,
        "displayName": data["displayName"],
    }
    for key in ("userPrincipalName", "mail", "department", "title", "telephoneNumber", "description"):
        if data.get(key):
            attrs[key] = data[key]
    if not conn.add(dn, attributes=attrs):
        raise RuntimeError(f"创建用户失败: {conn.result}")

    # 先设密码（需 LDAPS），再启用，避免启用时被密码策略拦截
    _set_password(conn, dn, data["password"])
    uac = ad_utils.UAC_NORMAL
    if data.get("password_never_expires"):
        uac |= ad_utils.UAC_DONT_EXPIRE
    if not conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, [uac])]}):
        raise RuntimeError(f"启用用户失败: {conn.result}")
    if data.get("must_change_next_logon", True):
        if not conn.modify(dn, {"pwdLastSet": [(MODIFY_REPLACE, [0])]}):
            raise RuntimeError(f"设置下次登录改密失败: {conn.result}")
    return dn


def update_user(conn, dn: str, data: dict) -> None:
    mapping = {
        "displayName": "displayName",
        "userPrincipalName": "userPrincipalName",
        "mail": "mail",
        "department": "department",
        "title": "title",
        "telephoneNumber": "telephoneNumber",
        "description": "description",
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
        raise RuntimeError(f"更新用户失败: {conn.result}")


def delete_user(conn, dn: str) -> None:
    if not conn.delete(dn):
        raise RuntimeError(f"删除用户失败: {conn.result}")


def set_enabled(conn, dn: str, enabled: bool) -> None:
    uac = get_user_uac(conn, dn)
    new = ad_utils.set_uac_flag(uac, ad_utils.UAC_ACCOUNT_DISABLE, not enabled)
    if not conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, [new])]}):
        raise RuntimeError(f"修改账号状态失败: {conn.result}")


def unlock_user(conn, dn: str) -> None:
    # 解锁只能写 lockoutTime=0（UAC 的 LOCKOUT 位是只读的）
    if not conn.modify(dn, {"lockoutTime": [(MODIFY_REPLACE, [0])]}):
        raise RuntimeError(f"解锁失败: {conn.result}")


def reset_password(conn, dn: str, new_password: str, must_change: bool = True) -> None:
    _set_password(conn, dn, new_password)
    pwl = 0 if must_change else -1
    if not conn.modify(dn, {"pwdLastSet": [(MODIFY_REPLACE, [pwl])]}):
        raise RuntimeError(f"设置密码策略失败: {conn.result}")


def move_user(conn, dn: str, target_ou_dn: str) -> None:
    if not conn.modify_dn(dn, dn.split(",", 1)[0], new_superior=target_ou_dn):
        raise RuntimeError(f"移动用户失败: {conn.result}")


def get_default_naming_context(conn) -> str | None:
    """从 RootDSE 读取域根 DN（如 DC=adser,DC=com），作为全域搜索基准。"""
    conn.search("", "(objectClass=*)", BASE, attributes=["defaultNamingContext"])
    if conn.entries:
        return ad_utils.get_single(conn.entries[0], "defaultNamingContext")
    return None


def find_user_dn_by_sam(conn, sam: str, base_dn: str | None = None) -> str | None:
    """按 sAMAccountName 在域内查找用户 DN（用于批量删除/修改定位）。

    搜索基准必须是域根：AD 的 base="" 是 RootDSE，其下不含任何命名上下文，
    以空 base 做 SUBTREE 搜索必然返回 0 条，导致批量删除/修改恒报"用户不存在"。
    """
    if not base_dn:
        base_dn = get_default_naming_context(conn)
    if not base_dn:
        return None
    flt = f"(&(objectCategory=person)(objectClass=user)(sAMAccountName={ad_utils.escape_filter(sam)}))"
    entries = ad_utils.paged_search_entries(conn, base_dn, flt, ["distinguishedName"])
    if entries:
        return ad_utils.get_single(entries[0], "distinguishedName")
    return None

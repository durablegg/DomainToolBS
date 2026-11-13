from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ldap3 import SUBTREE

# LDAP 时间值（GeneralizedTime / FILETIME）一律为 UTC，统一归一化为 UTC 后再交给前端；
# 前端的 formatDateTime 会按浏览器本地时区做唯一的 +8（或其他时区偏移）转换，避免双重换算。
# 注意：后端不要在这里预先 +8，否则会与前端再叠加一次（已删除的 to_local 北京偏移）。
def to_local(dt: datetime | None) -> datetime | None:
    """把任意 LDAP 时间归一化为 UTC（去掉时区信息），交给前端统一转本地时区显示。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

# userAccountControl 标志位
UAC_ACCOUNT_DISABLE = 0x0002
UAC_LOCKOUT = 0x0010
UAC_PASSWD_NOTREQD = 0x0020
UAC_DONT_EXPIRE = 0x10000
UAC_NORMAL = 0x0200  # NORMAL_ACCOUNT

# FILETIME（1601-01-01）到 Unix 纪元的秒数差
_EPOCH_DELTA = 11644473600
_NEVER = 0x7FFFFFFFFFFFFFFF


# --------------------------------------------------------------------------- #
# 属性读取（兼容 ldap3 Entry / Attribute）
# --------------------------------------------------------------------------- #
def _get_attr(entry, name):
    """兼容 ldap3 Entry 对象与 paged_search 返回的 dict。

    - Entry：通过 getattr 取，得到 Attribute 对象（含 .value / .values）
    - dict：response 条目形如 {'dn':..., 'attributes': {...}, 'raw_attributes': {...}}，
            且属性名大小写不敏感匹配
    """
    if isinstance(entry, dict):
        attrs = entry.get("attributes") or {}
        for k, v in attrs.items():
            if k.lower() == name.lower():
                return v
        return None
    return getattr(entry, name, None)


def _scalar(val):
    if val is None:
        return None
    if hasattr(val, "value"):  # ldap3 Attribute
        return val.value
    if isinstance(val, list):
        return val[0] if val else None
    return val


def _aslist(val):
    if val is None:
        return []
    if hasattr(val, "values"):  # ldap3 Attribute
        return list(val.values)
    if isinstance(val, list):
        return val
    return [val]


def get_single(entry, name, default=None):
    val = _scalar(_get_attr(entry, name))
    return val if val is not None else default


def get_list(entry, name):
    return _aslist(_get_attr(entry, name))


# --------------------------------------------------------------------------- #
# 时间转换（AD 用 FILETIME：100 纳秒间隔，自 1601-01-01）
# --------------------------------------------------------------------------- #
def filetime_to_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        ft = int(value)
    except (TypeError, ValueError):
        return None
    if ft in (0, _NEVER):
        return None
    ts = ft / 10_000_000 - _EPOCH_DELTA
    return to_local(datetime.fromtimestamp(ts, tz=timezone.utc))


def parse_generalized(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return to_local(value)
    try:
        s = str(value).replace("Z", "").replace(".0", "")
        return to_local(datetime.strptime(s, "%Y%m%d%H%M%S"))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# userAccountControl 处理
# --------------------------------------------------------------------------- #
def _to_int(val) -> int:
    """把 None / bytes / str / int 统一转成 int（计算属性有时返回原始字节）。"""
    if val is None:
        return 0
    if isinstance(val, bytes):
        return int.from_bytes(val, "little")
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def decode_uac(uac) -> dict:
    uac = _to_int(uac)
    return {
        "enabled": not bool(uac & UAC_ACCOUNT_DISABLE),
        "locked": bool(uac & UAC_LOCKOUT),
        "pwd_not_required": bool(uac & UAC_PASSWD_NOTREQD),
        "pwd_never_expires": bool(uac & UAC_DONT_EXPIRE),
    }


def set_uac_flag(uac: int, flag: int, enabled: bool) -> int:
    uac = int(uac or 0)
    return uac | flag if enabled else uac & ~flag


def must_change_password(pwd_last_set) -> bool:
    try:
        return int(pwd_last_set) == 0
    except (TypeError, ValueError):
        return False


def is_locked(lockout_time) -> bool:
    """根据 lockoutTime 判断账户是否处于锁定窗口内（0 / 0x7FFFFFFFFFFFFFFF 表示未锁定）。"""
    try:
        ft = int(lockout_time or 0)
    except (TypeError, ValueError):
        return False
    return ft not in (0, _NEVER)


def escape_cn(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace("+", "\\+")
        .replace('"', '\\"')
        .replace("<", "\\<")
        .replace(">", "\\>")
        .replace(";", "\\;")
    )


def escape_filter(value: str) -> str:
    return (
        value.replace("\\", "\\5c")
        .replace("*", "\\2a")
        .replace("(", "\\28")
        .replace(")", "\\29")
        .replace("\0", "\\00")
    )


# --------------------------------------------------------------------------- #
# 分页搜索（返回真正的 Entry 对象，规避 paged_search(generator) 返回 searchRef 的问题）
# --------------------------------------------------------------------------- #
def paged_search_entries(conn, base_dn, search_filter, attributes):
    """用 conn.search + 标准分页(Simple Paged Results)取回所有匹配条目。

    conn.search 默认 auto_referrals=True，会自动跟随引用并把 searchResRef 排除在
    conn.entries 之外；而 conn.extend.standard.paged_search(generator=True) 会把
    searchResRef（只有 uri/type，没有 dn）当条目 yield，导致后续解析 dn=None 报错。
    因此对"列表类"查询统一走本函数。
    """
    entries = []
    cookie = None
    while True:
        conn.search(
            base_dn, search_filter, SUBTREE,
            attributes=attributes, paged_size=1000, paged_cookie=cookie,
        )
        entries.extend(conn.entries)
        controls = (conn.result or {}).get("controls", {}) if conn.result else {}
        cookie = controls.get("1.2.840.113556.1.4.319", {}).get("value", {}).get("cookie")
        cookie = cookie or None
        if not cookie:
            break
    return entries

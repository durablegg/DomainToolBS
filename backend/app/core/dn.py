import base64


def encode_dn(dn: str) -> str:
    """把 DN 编码为 URL-safe base64，去掉尾部 = 填充，可直接放进路径参数。"""
    return base64.urlsafe_b64encode(dn.encode("utf-8")).decode("utf-8").rstrip("=")


def decode_dn(b64: str) -> str:
    """解码路径参数里的 DN（自动补回 = 填充）。"""
    pad = "=" * (-len(b64) % 4)
    return base64.urlsafe_b64decode((b64 + pad).encode("utf-8")).decode("utf-8")


def parent_dn(dn: str) -> str | None:
    """返回 DN 的父 DN；已是根则返回 None。"""
    idx = dn.find(",")
    return dn[idx + 1 :] if idx != -1 else None

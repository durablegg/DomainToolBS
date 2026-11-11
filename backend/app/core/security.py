import bcrypt
import jwt
from cryptography.fernet import Fernet
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings

settings = get_settings()


# --------------------------------------------------------------------------- #
# 密码哈希（本地平台账号登录）
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_access_token(sub: str, extra: dict | None = None, expires_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict = {"sub": sub, "iat": now, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# --------------------------------------------------------------------------- #
# 域服务账号凭据加密（Fernet）
# --------------------------------------------------------------------------- #
_fernet_instance = None


def _fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        key = settings.FERNET_KEY
        if not key:
            # 仅开发期：每次进程启动随机密钥，重启后旧密文无法解密
            key = Fernet.generate_key().decode("utf-8")
        _fernet_instance = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    return _fernet_instance


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")

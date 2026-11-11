from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "DomainToolBS"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./domaintool.db"

    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # 用于加密域服务账号密码；生产必须显式配置，否则每次重启进程密钥变化
    FERNET_KEY: str = ""

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    LOG_LEVEL: str = "INFO"
    DB_ECHO: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

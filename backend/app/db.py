from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, echo=settings.DB_ECHO, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # 开发期直接建表；生产环境后续引入 Alembic 做版本化迁移
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate() -> None:
    """对已有库做增量迁移（SQLite 无 ALTER 友好迁移，仅补新增列）。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        # admin_user.role
        if "admin_user" in tables:
            cols = {c["name"] for c in insp.get_columns("admin_user")}
            if "role" not in cols:
                conn.execute(
                    text("ALTER TABLE admin_user ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'super_admin'")
                )
                # 旧数据：超管 is_superuser=true，委派管理员 is_superuser=false（PostgreSQL 严格区分布尔/整数）
                conn.execute(text("UPDATE admin_user SET role='super_admin' WHERE is_superuser = true"))
                conn.execute(text("UPDATE admin_user SET role='admin' WHERE is_superuser = false"))
        # admin_scope.domain_id
        if "admin_scope" in tables:
            scols = {c["name"] for c in insp.get_columns("admin_scope")}
            if "domain_id" not in scols:
                conn.execute(text("ALTER TABLE admin_scope ADD COLUMN domain_id INTEGER"))
                first = conn.execute(text("SELECT MIN(id) FROM domain_config")).scalar()
                if first:
                    conn.execute(text("UPDATE admin_scope SET domain_id=:d"), {"d": first})
        # domain_config.description
        if "domain_config" in tables:
            dcols = {c["name"] for c in insp.get_columns("domain_config")}
            if "description" not in dcols:
                conn.execute(
                    text("ALTER TABLE domain_config ADD COLUMN description VARCHAR(512) NOT NULL DEFAULT ''")
                )
            # CA 证书与信任状态（域控自签名证书导入增强）
            for col, ddl in (
                ("ca_cert", "ALTER TABLE domain_config ADD COLUMN ca_cert TEXT NOT NULL DEFAULT ''"),
                ("cert_not_after", "ALTER TABLE domain_config ADD COLUMN cert_not_after TIMESTAMP"),
                ("cert_trust", "ALTER TABLE domain_config ADD COLUMN cert_trust VARCHAR(16) NOT NULL DEFAULT 'none'"),
                ("ca_enabled", "ALTER TABLE domain_config ADD COLUMN ca_enabled BOOLEAN NOT NULL DEFAULT TRUE"),
            ):
                if col not in dcols:
                    conn.execute(text(ddl))
        # audit_log.domain_id
        if "audit_log" in tables:
            acols = {c["name"] for c in insp.get_columns("audit_log")}
            if "domain_id" not in acols:
                conn.execute(text("ALTER TABLE audit_log ADD COLUMN domain_id INTEGER"))


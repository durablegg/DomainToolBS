"""
服务器端维护工具：创建 / 重置超级管理员账户（绕过 Web，供首次部署与找回密码使用）。

超级管理员自身不能通过 Web 界面增删，只能通过本脚本在服务端操作：
  - 账户不存在时：创建为超级管理员；
  - 账户已存在时：重置其密码并强制为超级管理员、启用。

用法（在 backend 目录下执行）：
  python scripts/reset_superadmin.py --username admin --password 'NewP@ssw0rd'
  python scripts/reset_superadmin.py --username admin --password 'NewP@ssw0rd' --display-name '超级管理员'
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402  (触发配置加载)
from app.core.security import hash_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402

import app.models  # noqa: E402,F401  (确保模型注册)
from app.models import AdminUser  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="创建 / 重置超级管理员账户")
    parser.add_argument("--username", required=True, help="超级管理员用户名")
    parser.add_argument("--password", required=True, help="新密码")
    parser.add_argument("--display-name", default="", help="显示名（可选）")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter_by(username=args.username).first()
        if admin is None:
            admin = AdminUser(username=args.username)
            db.add(admin)
            print(f"[+] 创建超级管理员: {args.username}")
        else:
            print(f"[*] 重置已有账户密码: {args.username}")

        admin.display_name = args.display_name or admin.display_name or args.username
        admin.password_hash = hash_password(args.password)
        admin.role = "super_admin"
        admin.is_superuser = True
        admin.is_active = True
        db.commit()
        print("[+] 操作成功。")
    finally:
        db.close()


if __name__ == "__main__":
    main()

# DomainToolBS

精简版**企业域控制器与域用户管理平台**（对标麒麟天御安全域管平台的 B/S 控制台部分）。
用于集中管理 Windows Server AD 的**组织单元、域用户、用户组、计算机账号**，并支持批量操作与审计。

> 当前阶段：**P1–P5 已落地** —— 本地账号登录、超管初始化、域连接配置（含连通性测试）、OU 树管理、域用户/用户组/计算机账号 CRUD、**批量导入导出（CSV）**、**审计日志**、**委派管理员范围化授权矩阵**。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + ldap3 + SQLAlchemy 2.x + PyJWT + bcrypt |
| 前端 | Vue3 + Vite + Element Plus + Pinia + Axios |
| 本地库 | 开发 SQLite / 生产 PostgreSQL |
| 域对接 | Windows Server AD（LDAPS 636 + ldap3） |
| 部署 | Docker Compose |

## 目录结构

```
DomainToolBS/
├── backend/        # FastAPI 服务
│   ├── app/
│   │   ├── core/        # 配置、JWT/加密、DN 编解码、权限依赖
│   │   ├── models/      # 本地库表（ admin_user / admin_scope / domain_config / audit_log / batch_task ... ）
│   │   ├── schemas/     # Pydantic 出入参
│   │   ├── services/    # ldap_conn（连接/发现）、ad_ou、ad_user、ad_group、ad_computer、audit、batch
│   │   └── api/v1/      # auth / domain / ous / users / groups / computers / audit / batch / rbac 路由
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/       # Vue3 + Element Plus
│   └── src/{api,router,store,views,layout,utils}
├── docker-compose.yml
└── CHANGELOG.md
```

## 快速开始（本地开发）

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cp .env.example .env          # 按需修改 JWT_SECRET_KEY / FERNET_KEY
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

启动后访问 http://localhost:8000/health 验证。

### 前端

```bash
cd frontend
npm install
npm run dev                   # 默认 5173，/api 已代理到后端 8000
```

打开 http://localhost:5173 ：
1. 首次进入点「首次使用？初始化平台」创建超级管理员；
2. 进入「域配置」填写域控地址、LDAPS 端口、绑定账号与密码，点「连通性测试」；
3. 进入「组织与用户」即可看到 OU 树，新建/删除子 OU。

## 关键设计

- **两类凭据分离**：平台登录用本地账号（`admin_user`，bcrypt）；后端连接 AD 用独立的域服务账号（`domain_config`，Fernet 加密），二者互不相关。
- **DN 编码**：OU/用户的 DN 含逗号与等号，URL 路径参数统一用 URL-safe Base64 编码（`core/dn.py` ↔ 前端 `utils/dn.ts`）。
- **范围化授权**：`admin_scope` 表已建，写操作前统一走 `core/deps.check_scope`（超管放行；委派管理员需 base_dn 在授权子树内且含对应 action）。P5 已提供管理界面（`/rbac`）：权限矩阵勾选 + OU/全域作用域，授权取并集。读接口不纳入作用域授权。
- **重置密码/解锁等坑**：后续阶段实现，务必走 LDAPS；`unicodePwd` 需 UTF-16LE + 双引号；解锁写 `lockoutTime=0`（非 userAccountControl）。详见 `docs/AD-Attributes.md`（P1 补充）。

## 部署（Docker）

```bash
# 建议先设置密钥
export JWT_SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
export FERNET_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
docker compose up --build
```

前端 http://localhost:8080 ，后端 API 由 nginx 反代（/api → backend:8000）。

## 路线图

- P0（已完成）：骨架、本地登录、超管自举、域配置与连通性测试、OU 树
- P1（已完成）：域用户 CRUD / 启停 / 重置密码 / 解锁 / 移动 OU
- P2（已完成）：用户组（成员分片管理）、计算机账号
- P3（已完成）：批量导入导出（CSV）、异步任务
- P4（已完成）：审计日志
- P5（已完成）：委派管理员范围化授权界面

## 安全提示

- 域服务账号**不要使用 Domain Administrator**，用 AD「委派控制向导」仅授予目标 OU 的创建/删除用户、重置密码、读写属性等权限。
- 生产环境务必设置 `JWT_SECRET_KEY` 与 `FERNET_KEY`，否则重启后旧凭据密文无法解密。
- AD 写操作（尤其改密码）必须走 LDAPS，明文 389 会被域控拒绝。

# DEPLOY.md — 离线镜像生产部署速查卡

> 完整说明见 `docs/生产服务器离线部署指南.md`（装 Docker/防火墙/开机自启/升级）与 `CHANGELOG.md`。
> 本卡仅给"照着敲"的最少命令。角色：本地 = 你的 Windows 工作区 / 源机 = `luan@myub:/opt/DomainToolBS`（打包源头）/ 生产机 = 目标 Ubuntu。

## 0. 交付文件清单（仓库内已就绪）

| 文件 | 去向 | 用途 |
|---|---|---|
| `backend/Dockerfile` | 源机（已含 `COPY scripts ./scripts`） | 镜像含超管脚本 |
| `docker-compose.prod.yml` | 源机 + 生产机 | 生产编排（去 build、固定镜像名、restart） |
| `.env.prod.example` | 源机 + 生产机 | 生产配置模板（复制为 `.env` 填值） |
| `scripts/export-images.sh` | 源机 | 一键 build+tag+save 离线 tar |
| `scripts/import-images.sh` | 生产机 | 一键 load+up |
| `docs/生产服务器离线部署指南.md` | 查阅 | 系统层 + 实例化全手册 |

## 1. 本地 → 源机（只推改动文件，勿整目录 scp）

```powershell
# 若源机 /opt/DomainToolBS 已属主为 luan，直接 scp 即可；否则先按下面"开通权限"
scp d:/PycharmProjects/DomainToolBS/docker-compose.prod.yml  luan@myub:/opt/DomainToolBS/
scp d:/PycharmProjects/DomainToolBS/.env.prod.example        luan@myub:/opt/DomainToolBS/
scp d:/PycharmProjects/DomainToolBS/scripts/export-images.sh luan@myub:/opt/DomainToolBS/scripts/
scp d:/PycharmProjects/DomainToolBS/scripts/import-images.sh luan@myub:/opt/DomainToolBS/scripts/
```

开通权限（仅首次，解决 `/opt` 下 Permission denied）：
```bash
ssh luan@myub
sudo mkdir -p /opt/DomainToolBS/scripts
sudo chown -R luan:luan /opt/DomainToolBS
```

## 2. 源机 myub：重新导出离线包（让 scripts 进镜像）

```bash
ssh luan@myub
cd /opt/DomainToolBS
bash scripts/export-images.sh          # 产出 domaintoolbs-images-1.0.tar.gz
docker images | grep domaintoolbs      # 确认 backend/frontend:1.0
```

## 3. 生产机 Ubuntu：从零部署

```bash
# A. 装 Docker/防火墙/开机自启（仅首次，详见 docs/生产服务器离线部署指南.md 第 1–3 节）
# B. 拷交付物到 /opt/DomainToolBS-deploy，然后：
cd /opt/DomainToolBS-deploy
docker load < domaintoolbs-images-1.0.tar.gz
cp .env.prod.example .env              # 编辑填 DB_PASSWORD / JWT_SECRET_KEY / FERNET_KEY / CORS_ORIGINS
bash scripts/import-images.sh         # 等效 docker compose -f docker-compose.prod.yml --env-file .env up -d

# C. 服务器侧创建超级管理员
docker compose -f docker-compose.prod.yml exec backend \
  python scripts/reset_superadmin.py --username admin --password 'StrongP@ssw0rd!'

# D. 验证
docker compose -f docker-compose.prod.yml ps
curl -s http://localhost:8080/ | grep -o '<title>.*</title>'
```

## 4. 硬约束（一行记住）

`FERNET_KEY`/`JWT_SECRET_KEY` 固定写 `.env` 不随机、不空；`CORS_ORIGINS` 改生产地址；数据在 `pgdata` 卷不进镜像；生产只用 `docker-compose.prod.yml`，不 `build`。

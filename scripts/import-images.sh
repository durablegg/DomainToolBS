#!/usr/bin/env bash
# 目标服务器一键导入：load 离线 tar -> 用 docker-compose.prod.yml + .env 起服务
# 用法：把本脚本与 domaintoolbs-images-*.tar.gz、docker-compose.prod.yml、.env 放在同一目录后执行
#       bash scripts/import-images.sh  [tar包路径，默认 domaintoolbs-images-1.0.tar.gz]
set -euo pipefail
cd "$(dirname "$0")"

IMG="${1:-domaintoolbs-images-1.0.tar.gz}"
COMPOSE="${COMPOSE:-docker-compose.prod.yml}"
ENVFILE="${ENVFILE:-.env}"

[ -f "$IMG" ]     || { echo "错误：找不到离线包 $IMG"; exit 1; }
[ -f "$COMPOSE" ] || { echo "错误：找不到 $COMPOSE"; exit 1; }
[ -f "$ENVFILE" ] || { echo "错误：找不到 $ENVFILE（可 cp .env.prod.example .env 后填真实值）"; exit 1; }

echo "==> 加载镜像"
docker load < "$IMG"

echo "==> 启动服务"
docker compose -f "$COMPOSE" --env-file "$ENVFILE" up -d

echo "==> 完成。创建/重置超级管理员（容器内含 scripts/reset_superadmin.py）："
echo "    docker compose -f $COMPOSE exec backend python scripts/reset_superadmin.py --username admin --password '你的密码'"

#!/usr/bin/env bash
# 源机一键打包：build 当前源码镜像 -> 打稳定 tag -> docker save 为离线 tar.gz
# 用法：bash scripts/export-images.sh   （在仓库根目录执行）
set -euo pipefail
cd "$(dirname "$0")/.."

BACKEND_TAG="${BACKEND_TAG:-domaintoolbs-backend:1.0}"
FRONTEND_TAG="${FRONTEND_TAG:-domaintoolbs-frontend:1.0}"
OUT="${OUT:-domaintoolbs-images-1.0.tar.gz}"

echo "==> 构建镜像"
docker compose build

echo "==> 打稳定 tag"
# build 已生成 <project>-backend:latest / <project>-frontend:latest（project 默认取目录名 domaintoolbs）
PROJECT="${PROJECT:-domaintoolbs}"
docker tag "${PROJECT}-backend:latest"   "$BACKEND_TAG"
docker tag "${PROJECT}-frontend:latest"  "$FRONTEND_TAG"

echo "==> 导出离线包: $OUT"
docker save "$BACKEND_TAG" "$FRONTEND_TAG" postgres:16 | gzip > "$OUT"
echo "==> 完成。把 $OUT 拷到目标服务器即可（配合 docker-compose.prod.yml 与 .env）。"

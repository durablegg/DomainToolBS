# CHANGELOG

## [2026-11-12] 新增：OU删除友好报错、组策略GPO(3-1)、回收站

- **优化** `backend/app/services/ad_ou.py`：`delete_ou` 删除前统计 OU 直接子对象；非空时抛出友好提示「该 OU 非空，包含 N 个子对象（OU/用户/组/计算机/其他），请先清空后再删除」，避免裸 LDAP 报错（保持 AD 安全策略，不提供强制删除）；删除失败（如「防止对象被意外删除」）也做汉化。
- **新增 组策略 GPO（3-1：读取 + 绑定/解绑）**：
  - `backend/app/services/ad_gpo.py` + `backend/app/api/v1/gpo.py`：列出域内 GPO（`CN=Policies` 元数据）；读取/写入 OU 的 `gPLink`/`gPOptions`（绑定、解绑、禁用、强制、阻止继承），纯 LDAP 实现。
  - `frontend/src/views/gpo/GpoView.vue` + `frontend/src/api/gpo.ts`：新增左侧菜单「组策略 GPO」，GPO 列表页 + OU 关联管理（选 OU → 勾选绑定/禁用/强制 + 阻止继承 → 保存，审计记录）。
- **新增 回收站**：
  - `backend/app/services/ad_recyclebin.py` + `backend/app/api/v1/recyclebin.py`：检测域是否已启用 AD 回收站（`msDS-EnabledFeatureFlags` + 功能级别）；列出已删除对象（Show Deleted 控制位）；`modify_dn` 还原回原父容器；权限限超管/管理员（恢复进审计）。
  - `frontend/src/views/recycle/RecycleBinView.vue` + `frontend/src/api/recyclebin.ts`：新增左侧菜单「回收站」（审计员可看列表），按类型筛选、恢复（恢复 OU 不级联子对象，UI 已提示）。
- **原因** OU 误删报错不友好、缺少 GPO 与回收站的集中管理能力。
- **影响** 无数据库 schema 变更；GPO/回收站均为实时读/写 AD + 复用审计表。生产更新：后端新增 2 个服务/路由文件（需整体重新构建后端镜像或 docker cp 后重启）+ 前端重新打包替换 dist + nginx reload。部署前请在测试域控确认功能级别 ≥ 2008 R2 并已启用回收站（一次性不可逆）。

## [2026-11-11] 修复+新增：批量导入OU级联、新建用户重置、审计日志导出

- **修复** `frontend/src/views/batch/BatchView.vue`：批量导入「选择导入目标 OU」由平铺 `el-select` 改为 `el-tree-select`，复用已有 OU 树（`sub_ous`），支持展开选择子 OU（如「踏浪第一事业部 → 子OU」）。
- **修复** `frontend/src/views/users/UserView.vue`：「新建用户」按钮改为 `openCreate()`，打开弹窗前重置 `createForm` 全部字段，解决残留上次用户信息的问题。
- **新增** 审计日志支持按时间范围筛选（列表与导出一致），并新增「导出 CSV」按钮，按当前筛选（操作/对象类型/操作人/关键字/时间范围）导出全部匹配记录：
  - `backend/app/api/v1/audit.py`：新增 `GET /audit/logs/export`（CSV 流式下载，UTF-8 BOM 适配 Excel），`list_logs` 增加 `start`/`end` 时间筛选；权限保持超管/管理员/审计员。
  - `frontend/src/views/audit/AuditLogView.vue`：查询栏新增「时间范围」daterange + 「导出 CSV」按钮。
  - `frontend/src/api/audit.ts`：新增 `exportAuditLogs()`。
- **原因** 批量导入只能选顶层 OU、新建用户弹窗残留上次信息、审计日志无法按时间筛选导出。
- **影响** 纯功能增强/易用性修复，无数据库 schema 变更；生产更新：后端单文件热更 + 重启后端容器，前端重新打包 + 替换 dist + nginx reload。

## [2026-11-11] 配置：测试环境容器开机自启（restart 策略）

- **修改** `docker-compose.yml`：db / backend / frontend 三个服务统一加 `restart: unless-stopped`——Docker 守护进程随系统启动时自动拉起容器，解决测试虚拟机每次开机都要手动 `docker compose up -d` 的问题。
- **原因** 测试环境 compose 未配置 restart 策略，重启虚拟机后容器不自启（生产 `docker-compose.prod.yml` 已有该策略，不受影响）。
- **影响** 仅编排配置，不动代码与数据；生效需在服务器 `docker compose up -d` 重新应用，且 Docker 服务需开机自启（`sudo systemctl enable docker`）。数据库数据在 volume 中，容器重建不丢失。

## [2026-09-18] 文档：细化生产机离线装 Docker 命令

- **更新** `docs/生产服务器离线部署指南.md` 第 1.2 节：把「完全离线装 Docker」从简述展开为精确命令——下载端加官方源 + 递归 `apt-get download` 抓全 deb → `tar` 携带 → 生产机 `dpkg -i` 安装，含依赖缺失处理与版本一致性提醒。
- **影响** 纯文档。

## [2026-09-18] 修复：export-images.sh 打包打 tag 失败

- **问题** `scripts/export-images.sh` 用 `docker tag "$(docker compose images -q backend)" ...` 取镜像 ID，在源机（Bake 构建、服务未运行）下取不到有效 ID，报 `No such image: sha256:...` 与 `invalid reference format`，导致导出中断。
- **修复** 改为直接引用 `build` 已生成的 `<project>-backend:latest` / `<project>-frontend:latest`（`PROJECT` 默认 `domaintoolbs`，可用环境变量覆盖），不再依赖 `docker compose images -q`。
- **影响** 仅交付脚本，已在源机验证 `docker compose build` + tag + save 全流程通过，产出 `domaintoolbs-images-1.0.tar.gz`。

## [2026-09-18] 文档：根目录 DEPLOY.md 速查卡

- **新增** `DEPLOY.md`：压缩版离线部署速查卡，含「交付文件清单 + 各机最少命令」（本地→源机 scp、源机 export、生产机 load/up/建超管）与硬约束一行提醒；详细系统层操作指向 `docs/生产服务器离线部署指南.md`。
- **影响** 纯文档，不影响代码与运行。

## [2026-09-18] 文档：生产服务器离线部署指南

- **新增** `docs/生产服务器离线部署指南.md`：汇总生产 Ubuntu 从零部署——安装 Docker（含完全离线装 Docker 的替代方案）、防火墙（仅开放 8080 并保留 SSH）、开机自启（Docker daemon + compose `restart` 策略）、离线镜像加载与启动、服务器侧创建超级管理员、验证与升级注意事项。
- **对象** 与《服务部署与运维操作指导》互补：本文聚焦「系统层 + 离线镜像实例化」，不涉及 CA/HTTPS/反向代理（见该文档第 11–13 节）。
- **影响** 纯文档，不影响代码与运行。

## [2026-09-18] 新增：离线镜像交付与 Ubuntu 生产部署支持

- **需求** 支持将测试/源服务器上已构建的服务打包为离线镜像，在生产 Ubuntu 服务器直接实例化部署；不依赖生产机联网 build 或镜像仓库。
- **新增 / 操作**
  - `backend/Dockerfile`：增加 `COPY scripts ./scripts`，使超管维护脚本 `scripts/reset_superadmin.py` 随镜像分发（容器内需用其创建/重置超级管理员）。
  - `docker-compose.prod.yml`（新）：生产编排文件，去掉 `build`、改用固定镜像名 `domaintoolbs-backend:1.0` / `domaintoolbs-frontend:1.0`，各服务加 `restart: unless-stopped`；仅供 `docker compose -f docker-compose.prod.yml` 显式使用，不影响原 `docker-compose.yml`。
  - `.env.prod.example`（新）：生产配置模板（`DB_PASSWORD` / `JWT_SECRET_KEY` / `FERNET_KEY` / `CORS_ORIGINS`），复制到 `.env` 填真实值；命名为 `.example` 避免被 compose 默认读取、误覆盖源机 `.env`、误提交密钥。
  - `scripts/export-images.sh`（新）：源机一键 `build + tag + docker save` 导出离线 tar 包。
  - `scripts/import-images.sh`（新）：目标服务器一键 `docker load + up -d`，并提示用 `reset_superadmin.py` 创建超管。
  - `.gitignore`：新增根 `.env` 忽略，避免真实密钥入库。
- **原因** 原 `docker-compose.yml` 依赖源码 `build`，不适合离线/无源码的生产环境；超管脚本原未进镜像，导致容器内需服务器侧创建超管时缺少脚本。
- **影响** 纯交付/部署配套，不动任何业务代码，不影响现有测试服务与原在线部署流程。生产部署步骤：`docker load` 离线包 → `docker compose -f docker-compose.prod.yml --env-file .env up -d` → 用 `reset_superadmin.py` 建超管；数据库数据不打包（空系统重建），密钥/密码经 `.env` 注入、不进镜像。

## [2026-09-18] 修复：域配置保存 500（name 'admin' is not defined）

- **问题** 「域配置」编辑 → 保存报「服务器内部错误: name 'admin' is not defined」，超管/管理员均复现。
- **根因** `api/v1/domain.py` 的 `update_domain`：引入 CA 开关门控时，函数体内用 `admin.role` 判断，但依赖注入参数名是 `_`，导致 `admin` 未定义抛出 500。
- **修复** 将该函数的依赖参数 `_` 统一更名为 `admin`（`get_domain_config` 引用同步更新），其余逻辑不变；`ca_enabled` 仍仅超级管理员可改。
- **影响** 仅 `backend/app/api/v1/domain.py` 一个文件；热更或重建 `backend` 后恢复，无数据库结构变更。

## [2026-09-18] 新增：域 CA 认证开关（仅超管）+ 补齐 OU 审计日志 + 修复测试套件

- **需求** 域控配置可开启/关闭 CA 认证：启用时与现状一致（证书未通过校验则暂停非超管写操作）；关闭时不启用任何 CA 相关限制，管理员可自由操作；开关权限仅超级管理员。另补齐此前完全缺失的 OU 审计日志。
- **后端**
  - `models/__init__.py` + `db.py`：`domain_config` 新增 `ca_enabled`（Boolean，默认 True），`init_db` 增量补列；存量域默认"启用"，不改变既有行为。
  - `schemas/__init__.py`：`DomainConfigIn/Out` 增加 `ca_enabled`；新增 `DomainCaMode`（`enabled: bool`）。
  - `api/v1/domain.py`：新增超管专用 `PUT /domains/{id}/ca-mode`；`update_domain` 中 `ca_enabled` 仅 `super_admin` 可改（其他角色保存时忽略该字段）；`_full_out` 及普通用户脱敏分支均返回 `ca_enabled`。
  - `core/deps.py`：`check_scope` 的证书拦截改为**仅在该域 `ca_enabled=True` 时生效**，关闭后完全不限制；`get_domain_config` 逻辑不变。
  - `services/scheduler.py`：每日巡检仅处理 `ca_enabled=True` 且已导入 CA 的域，关闭 CA 的域不再产生证书告警。
  - `api/v1/ous.py`：**补齐 OU 审计日志**（此前 create/update/delete/move 均未写审计）。新增 `_ou_name(dn)`（OU 无 sAMAccountName，取 RDN 值作 `target_name`）与 `_ip(req)`；四个接口成功/失败均写 `audit_log`，失败分支记录 `error_msg` 后**原样抛出原异常**（不改变既有错误语义）。
- **前端** `views/domain/DomainConfig.vue` + `api/domain.ts`：新增 `toggleDomainCa` 接口；列表"证书通道"列在关闭时显示「CA关闭(不限制)」；表单新增「CA 认证」开关（仅超管可见，切换即时生效），CA 证书文本域与"导入并验证 CA"按钮仅在启用时展示。
- **测试** `tests/` 修复历史遗留失败，全套 **40 项通过**：
  - `conftest.py`：`bootstrap_super` 改用 `/api/v1/auth/bootstrap`，且 bootstrap **仅建账号不返回 token**，需再登录取 token；新增 `auth_headers` / `super_token` fixture（此前缺失导致 13 个用例 collection error）。
  - 修正多处 `/api/...` 漏 `/v1` 前缀（`test_roles_scope` 的 accounts/domains、`test_rbac` 等）。
  - `check_scope` 调用补 `domain_id`（多域改造后新增必填参数）。
  - `_ensure_delegate` / `_make_delegated` **显式设 `role="admin"`**（此前漏设，模型默认 `super_admin`，导致委派账号实为超管、权限断言失真）。
  - 多域后必填 `domain_id`：`test_batch` 补建域并传 `domain_id`，同时屏蔽后台导入 worker（避免连接真实 LDAP）；`test_rbac` 作用域请求体补 `domain_id`；`test_domain_required` 期望由 404 改为 422（FastAPI 必填查询参数校验返回 422）。
  - `test_scope.py` 改用 `db` fixture（此前用裸 `SessionLocal()` 操作真实库，被其他用例创建的域污染，触发证书拦截误报 403）。
  - 新增 `test_check_scope_ca_disabled_bypasses`：CA 关闭时即使 `cert_trust=untrusted` 也按作用域放行。
- **影响** 前后端均需重建镜像；`domain_config` 表自动增量加列，存量域默认"启用 CA"（行为不变）。关闭 CA 后，该域的证书过期告警与非超管写操作限制均解除。

## [2026-09-17] 调整：缺 CA 也拦截管理员写操作 + 审计 target_name 补 sAMAccountName

- **需求变更** 原设计"不导入 CA 不影响现有功能"，现改为：**连未导入 CA（cert_trust=none）也禁止管理员写操作**，仅超级管理员可继续操作（用于重新导入 CA）；读操作不受影响。
- **后端** `core/deps.py`：`check_scope` 拦截条件由 `("expired","untrusted")` 扩展为 `("none","expired","untrusted")`（超管仍豁免）。
- **后端** 审计 `target_name` 空值修复（此前写接口把 DN 误传到 `object_dn` 第 5 位，导致 `target_name` 恒空）：
  - `api/v1/users.py`：新增 `_sam_of(conn, dn)` 从 AD 取 `sAMAccountName`；`update/delete/enable/disable/unlock/reset_password/move` 的审计（成功与失败分支）均补 `target_name`。
  - `api/v1/groups.py`：新增 `_sam_of_group`；`update/delete/add_members/remove_members` 补 `target_name`。
  - `api/v1/computers.py`：新增 `_sam_of_computer`（含 `$` 后缀）；`enable/disable/move/delete` 补 `target_name`。
  - 说明：`ous.py` 当前**完全未写审计日志**（create/update/delete/move 均无 `write_log` 调用），属另一缺口，本期未改；是否补 OU 审计待定。
- **影响** 行为变更：未导入 CA 的域，管理员禁用/删除/改密等写操作将返回 403「该域证书未配置，写操作已暂停，请由管理员导入 CA」；若需恢复，导入有效 CA 或超管操作即可。需重建 `backend` 镜像。
- **测试** 既有 `test_scope.py`/`test_roles_scope.py` 仍因调用旧版 `check_scope` 签名而失败（历史遗留，与本次无关）；`auth_headers` fixture 仍缺失导致 13 个用例 collection error（待补）。

## [2026-09-17] 域控 CA 证书导入与双通道（可选安全增强）

- **需求** 在域配置中可导入域控自签名/企业 CA 证书：导入后对该域切换到 `CERT_REQUIRED` 安全通道；未导入仍可正常运行（基础通道 `CERT_NONE`），不阻塞业务；证书过期时非超管写操作暂停。
- **后端**
  - `models/__init__.py` + `db.py`：`domain_config` 新增 `ca_cert` / `cert_not_after` / `cert_trust`（none/ok/expiring_soon/expired/untrusted），`init_db` 增量补列。
  - `services/ldap_conn.py`：连接层支持 CA 校验（`Tls(validate=CERT_REQUIRED, ca_certs=…)`），握手失败自动回退 `CERT_NONE`；新增 `_probe_peer_cert` / `_verify_chain` / 到期判定（链校验不强制主机名，避免按 IP 访问误判）。
  - `api/v1/domain.py`：新增 `PUT /domains/{id}/ca`（超管+管理员）导入并即时验证；连通性测试返回证书状态并刷新信任状态；修复缺失的 `status` 导入。
  - `core/deps.py`：`check_scope` 在证书 `expired/untrusted` 时拦截非超管写操作（读操作不受影响）。
  - `services/scheduler.py`（新）+ `main.py`：每日后台巡检已导入 CA 的域，刷新信任状态，对即将到期/已过期写 `audit_log` 告警。
- **前端** `views/domain/DomainConfig.vue` + `api/domain.ts`：域列表新增「证书通道」状态徽标；表单增加 CA 证书文本域与「导入并验证 CA」按钮（超管+管理员可见）；展示信任状态与到期日。
- **文档** 《服务部署运维操作指导》新增第 11 节（CA 下载与导入）、第 12 节（启用 HTTPS，仅配置不改代码）、第 13 节（端口冲突与反向代理）。
- **测试** `tests/test_domain_ca.py`：CA 列持久化、导入角色控制（超管+管理员可、普通用户 403）、过期拦截非超管写操作；全部通过。
- **影响** 前后端均有改动，部署需重建 `backend` 与 `frontend`；`domain_config` 表自动增量加列，无手工迁移。外部互联网 HTTPS 本期不做，列入下一期。

## [2026-09-17] 授权管理：仅「管理员」可分配授权，其余角色展示内置默认权限

- **需求** 授权管理页选择不同角色时，只有「管理员」才需要（且允许）分配域 + OU + 权限；普通用户、审计员使用系统内置默认权限，不再展示可编辑的授权矩阵。
- **前端** `frontend/src/views/rbac/ScopeView.vue`：
  - 新增 `selectedRole` / `isDelegable`（判断选中账户是否为 `admin`）；仅 `isDelegable` 时渲染授权矩阵与「新增授权范围 / 保存授权」按钮。
  - 非管理员角色改为只读展示 `DEFAULT_PERMISSIONS`（普通用户：全部域只读、无写/删除/授权/账户管理/审计权限、域详情凭据脱敏；审计员：仅查看/导出审计日志、无域目录访问权限）。
  - `onAdminChange` 对非管理员角色不再请求授权范围接口。
  - 页头说明同步更新。
- **后端** `backend/app/api/v1/rbac.py`：
  - `PUT /rbac/admins/{id}/scopes` 增加角色校验，非 `admin` 角色返回 400「该角色使用系统内置默认权限，无需配置作用域」（防止绕过界面直接调接口授权）。
  - `GET /rbac/admins/{id}/scopes` 对非 `admin` 角色返回空列表。
- **测试** 新增 `backend/tests/test_rbac_scope_role.py`：普通用户/审计员配置授权被拒（400）且读取为空列表；与密码历史测试一并通过。
- **影响** 前后端均有改动，部署需重建 `backend` 与 `frontend`；无数据库结构变更。

## [2026-09-17] 修复：账户创建时间格式 / 计算机名后缀 $ / DNS 主机名为空

- **问题 1：账户管理「创建时间」格式不统一** —— 该列直接渲染后端 ISO 原始串（如 `2026-09-16T09:28:00.325369`），与其余页面不一致。
  - `frontend/src/views/accounts/AccountView.vue`：改用统一工具 `formatDateTime(row.created_at)`（输出 `YYYY-MM-DD HH:mm:ss` 本地时间）。
- **问题 2：计算机列表「计算机名」都带 `$`** —— 原列绑定 `sAMAccountName`。AD 中计算机（机器）账户的登录名约定必须以 `$` 结尾（用于与用户账户区分），属技术性后缀，非显示名。
  - `frontend/src/views/computers/ComputerView.vue`：展示改用 `cn`/`name` 并去掉结尾 `$`（`computerName()`），完整 `sAMAccountName` 通过悬浮提示查看；`关键字` 搜索不受影响（后端同时匹配 `sAMAccountName`/`cn`/`displayName`）。
- **问题 3（顺带修复）：「DNS 主机名」列始终为空** —— 前端列绑定 `dnsHostname`，但后端从未返回该字段。
  - `backend/app/services/ad_computer.py`：`COMPUTER_ATTRS` 增加 `dNSHostName`，`computer_to_dict` 输出 `dnsHostname`。
  - `backend/app/schemas/__init__.py`：`ComputerOut` 增加 `dnsHostname`。
  - `frontend/src/api/computers.ts`：`ComputerItem` 补全 `dnsHostname`/`ou_dn`/`last_logon` 字段类型。
- **影响** 前端与后端均有改动，部署需同时重建 `backend` 与 `frontend` 镜像；无数据库结构变更。

## [2026-09-17] 修复：改密可复用历史密码（密码历史校验失效）

- **问题** 用户修改自身密码时，使用「上一个」或「最近 3 次内用过的」密码仍能修改成功，历史密码防重用校验未生效。
- **根因** 历史密码原先存于 `AdminUser.password_history`（JSON/`TEXT` 列），在 PostgreSQL 下存在序列化/反序列化隐患，导致读取到的历史值异常、比对失效。
- **文件 / 操作**
  - `app/models/__init__.py`：新增独立表 `AdminPasswordHistory(admin_id, password_hash, created_at)`（外键级联删除），移除 `AdminUser.password_history` JSON 列。
  - `app/db.py`：移除 `password_history` 列的增量迁移步骤（`create_all` 自动建新表）。
  - `app/services/password_policy.py`：新增 `get_recent_hashes(db, admin_id)`、`record_history(db, admin_id, password_hash)`（仅存旧密码、保留最近 3 条），保留纯函数 `validate_new_password`/`validate_complexity`。
  - `app/api/v1/auth.py`（`/auth/change-password`）、`app/api/v1/accounts.py`（`PATCH /accounts/{id}` 重置密码）：改用独立的 `AdminPasswordHistory` 表做「不得与前 3 次相同」校验。
  - `backend/tests/test_password_history.py`：新增回归测试（复用上一次/最近三次内拒绝、可滑出窗口、与当前相同拒绝、弱密码拒绝），全部通过；`tests/conftest.py` 修正 `app.db` 引用为模块级 `get_db`/引擎注入。
- **影响** 部署重启后 `init_db` 会自动创建 `admin_password_history` 表；旧 `password_history` 列保留但不再使用（无害）。密码复杂度（≥8 位且含大小写/数字/符号）与前 3 次防重用策略保持不变。
- **审计范围约定** 与用户确认：审计日志仅记录域相关操作（AD 用户/组/计算机/批量等），平台账号自身的改密/账户管理操作**不写入审计日志**，维持现状。

## [2026-09-16] P6 多域控 + 四角色权限体系（后端）

- **新增角色体系** `core/roles.py`：四角色 `super_admin`(超级管理员) / `admin`(管理员) / `user`(普通用户) / `auditor`(审计员)。`AdminUser` 增加 `role` 列（保留 `is_superuser` 兼容列）。
- **超级管理员**：全部权限，可管理其他角色（增删改/授权）；自身增删仅限服务器用户数据库（UI 拦截）。
- **管理员**：超管授权的一个或多个域控范围内写操作；作用域 = 域(`domain_id`) + OU 子树(`base_dn`) + 权限字符串。
- **普通用户**：全部域只读，无写/授权/审计权限；查看域详情时连接凭据(host/bind_dn)脱敏。
- **审计员**：仅 `GET /audit/logs` 查看/导出审计，无目录访问。
- **多域控**：`AdminScope` 增加 `domain_id`（P5 单域 OU 扩展为「域+OUscope+权限」）；`DomainConfig` 增加 `description`；新增 `api/v1/domains.py` 多域 CRUD（`GET /domains`、`POST /domains`(仅超管)、`GET/PUT/DELETE /domains/{id}`(超管或管辖内管理员)、`/test`、`/{id}/info`），普通用户列表脱敏为 `DomainBriefOut`。
- **账户管理** `api/v1/accounts.py`（仅超管）：`GET/POST /accounts`、`GET/PATCH/DELETE /accounts/{id}`；`role` 仅可为 `admin/user/auditor`，禁止通过界面创建/编辑/删除超级管理员，禁止删除自身。
- **鉴权内核** `core/deps.py`：新增 `require_role(*roles)`、`get_domain_config(domain_id, admin, db)`（按角色做域可见性/管辖校验），`check_scope` 改为 `(admin, action, domain_id, target_dn, db)` 多域版；审计 `write_log` 增加 `domain_id`，`AuditLog` 增加 `domain_id`。
- **业务路由域化**：`users/groups/computers/ous/batch` 全部接收 `domain_id` 查询参数，经 `get_domain_config` 解析连接并执行域作用域校验；批量导入/导出按 `domain_id` 落域。
- **迁移** `db.py`：`init_db` 增加增量迁移（补 `admin_user.role`、`admin_scope.domain_id`、`domain_config.description`、`audit_log.domain_id`，旧 `is_superuser` 行回填为 `admin`/`super_admin`，旧 `admin_scope` 行回填首个域）。

### 影响 / 注意
- 所有目录/批量接口均新增必填 `domain_id` 查询参数，前端需配合全局域切换器传参（P6-5 前端待做）。
- 读接口仍不纳入作用域授权，仅角色 + 域可见性约束；写/删受 `check_scope`（域 + OU + 权限）约束。
- 当前环境未安装 fastapi 运行依赖，后端仅通过编译与 lint 校验，未做运行时导入/接口自测；前端与测试（P6-5/P6-6）待续。

## [2026-09-16] P6 补充：管理员建域 / 密码自管 / 批量扩展 / OU 查询 / 测试

- **1. 管理员可新建域（带重复校验 + 自动授权）** `api/v1/domain.py`：`POST /domains` 放开给 `super_admin` 与 `admin`；新建时按 `name` 或 `base_dn` 查重，已存在则 400「域已存在，请由超级管理员分配」；**管理员自建的域自动写入一条 `AdminScope`（整个域根 + 全部写权限）**，即时出现在该管理员的可管理域列表中。超级管理员仍可分配/新建任意域。
- **2. 超级管理员账户的增删与密码找回**
  - 首次部署：`POST /auth/bootstrap` 在平台无任何账户时创建超级管理员（部署期引导）。
  - 忘记密码：新增服务器端脚本 `backend/scripts/reset_superadmin.py`（`python scripts/reset_superadmin.py --username <u> --password <p>`），可创建或重置超级管理员密码，**绕过 Web、仅限服务器侧执行**，满足「密码忘记只能服务端找回」的硬性安全约束。
  - Web 端改密：新增 `POST /auth/change-password`（当前登录用户修改自身密码，所有角色含超管通用）；前端布局下拉新增「修改密码」弹窗；其他账户密码亦可在 Web 端修改/重置。
- **3. 批量任务扩展** `api/v1/batch.py` + `services/batch.py`：在「批量新增用户」基础上新增 **批量删除用户**（`POST /batch/delete-users`，CSV 仅 `sAMAccountName`）与 **批量修改用户**（`POST /batch/update-users`，CSV 支持修改属性/密码/启用状态）；新增对应 CSV 模板下载（`/batch/template/delete-users`、`/batch/template/update-users`）。后台 worker 按行解析、逐条作用域校验、记录任务明细；`ad_user` 新增 `find_user_dn_by_sam` 按登录名定位 DN。前端 `BatchView` 增加「新增/删除/修改」操作类型切换与对应模板下载。
- **4. 用户/计算机按 OU 归属查询** `api/v1/users.py` 原已支持 `ou` 参数；`api/v1/computers.py` 新增 `ou` 查询参数（按 OU 子树过滤）；前端 `UserView`/`ComputerView` 工具栏新增「OU 归属」树选择器（默认全域）。
- **5. 测试 P6-6** 新增 `backend/tests/conftest.py` 与 `test_roles_scope.py`：共享内存 SQLite + TestClient 脚手架；覆盖角色常量、作用域校验（命中/越域/缺权限/超管绕过）、账户禁止创建超管、域重复拦截、管理员自建域自动授权。运行：`pip install pytest httpx` 后 `pytest -q`（需 fastapi/sqlalchemy 依赖）。

### 影响 / 注意
- 管理员新建域后默认获得该域完整管理权，若需收窄权限，仍由超管在「授权管理」中调整其 `AdminScope`。
- 批量删除/修改会真正变更 AD 数据，按行做作用域校验，失败行不中断整体任务，明细可在任务列表查看。
- 环境仍缺 fastapi/node 运行依赖；后端仅编译/lint 校验，测试与前端构建需在具备依赖的环境执行。

## [2026-09-16] P6 前端（多域切换 + 四角色菜单 + 账户/授权页）

- **角色与权限** `utils/roles.ts`：四角色常量、标签、写权限判定 `canWrite`；`api/auth.ts` 的 `Admin` 增加 `role`。
- **全局域切换** `store/domain.ts`：维护域列表与当前选中域（持久化到 localStorage）；`layout/DefaultLayout.vue` 顶部新增域下拉，切换即触发各业务页刷新。
- **角色化菜单**：按 `user.role` 过滤侧边菜单——审计员仅见「审计日志」；普通用户仅见只读业务页（无批量/授权/账户）；管理员见业务页+批量+审计（无授权/账户）；超管全量。
- **多域接口** `api/domain.ts` 改写为多域 CRUD；`users/groups/computers/ou/batch` 全部追加 `domain_id` 参数（GET 走 query，POST/PUT/DELETE 走 query）；`api/rbac.ts` 增加 `role`/`domain_id`；新增 `api/accounts.ts`。
- **业务页改造**：用户/组/计算机/组织/OU/批量 均从域 store 取 `domain_id` 调接口，监听域切换自动重载，非写角色（`canWrite` 为 false）隐藏所有写按钮。
- **新页面**：`views/domain/DomainConfig.vue` 重写为多域列表 + 新建/编辑/删除/连通测试（普通用户只读、凭据脱敏）；`views/accounts/AccountView.vue` 账户 CRUD（超管专用，禁止超管自身）；`views/rbac/ScopeView.vue` 每条授权增加「域」选择与按域加载 OU 树。
- 路由新增 `/accounts`；`AuditLogView` 增加按域过滤。

### 影响 / 注意
- 前端需安装依赖（当前环境无 node，未做 tsc/构建校验），请在具备 node 的环境 `npm i && npm run build` 验证。
- 所有目录/批量接口均依赖顶部已选域；未选域时页面给出提示且禁止写操作。
- 后端接口与前端调用已对齐（新增必填 `domain_id`），但最终联调需在有 AD/运行环境的机器完成。

## [2026-09-16] P5 委派管理员范围化授权界面

- **新增** 接口 `api/v1/rbac.py`：`GET /rbac/permissions`（返回权限矩阵定义）、`GET /rbac/admins`（超管列出管理员）、`GET/PUT /rbac/admins/{id}/scopes`（委派管理员作用域的整体读写）。
- **权限模型**：资源 × 操作字符串（`user:write`/`user:delete`/`user:reset_password`、`group:write`/`group:delete`、`computer:write`/`computer:delete`、`ou:write`），与 `core/deps.check_scope` 实际使用的 action 完全一致；未知权限被 400 拒绝，超级管理员不可被配置作用域。
- **作用域粒度**：支持「整个域根（全域）」或某个 OU 子树（`base_dn`）；委派管理员可拥有多条 `AdminScope` 行，授权取并集。
- **新增** 前端 `views/rbac/ScopeView.vue`（管理员列表 + 作用域矩阵勾选 + OU/全域选择）、`api/rbac.ts`、路由 `/rbac` 与菜单「授权管理」。
- **新增** 测试 `tests/test_rbac.py`：权限矩阵、超管约束、作用域 CRUD、越权拒绝。

### 影响 / 注意
- 读接口（GET）按既定方案**不纳入作用域授权**，仅写/删受 `base_dn` 约束。
- P5 仅做「授权矩阵管理」，管理员账户（增删改/改密/设为超管）不在本次范围。

## [2026-09-16] P4 审计日志

- **新增** 接口 `api/v1/audit.py`：`GET /audit/logs`（按 `action`/`object_type`/`operator`/关键字分页过滤）、`GET /audit/logs/{id}`（明细）。
- **新增** 前端 `views/audit/AuditLogView.vue`（过滤检索 + 明细抽屉）、`api/audit.ts`、路由 `/audit` 与菜单「审计日志」。
- 既有各写操作接口（P1/P2 的 user/group/computer/ou）已接入 `services/audit.write_log`，本阶段补齐只读检索面。
- **新增** 测试 `tests/test_audit.py`：列表过滤、明细与 404。

## [2026-09-16] P3 批量导入导出（CSV）+ 异步任务

- **新增** 服务 `services/batch.py`：CSV 解析/渲染/模板 + 后台导入 worker（独立会话与 LDAP 连接，逐行创建用户并回写 `BatchTaskItem` 明细与统计）。
- **新增** 接口 `api/v1/batch.py`：`GET /batch/template/users`（模板下载）、`POST /batch/import-users`（CSV 异步导入，需 `user:write` 授权）、`GET /batch/export-users`（导出当前域用户 CSV）、`GET /batch/tasks` 与 `GET /batch/tasks/{id}`（任务与明细）。
- **新增** 前端 `views/batch/BatchView.vue`（模板下载/导入/导出/任务进度与明细）、`api/batch.ts`、路由 `/batch` 与菜单「批量任务」。
- **新增** 测试 `tests/test_batch.py`：模板、CSV 校验、任务创建、解析单测。

### 影响 / 注意
- 导入为异步（FastAPI `BackgroundTasks`），前端提交后轮询 `/batch/tasks` 查看进度；无域配置时任务标记 failed。
- CSV 列：`sAMAccountName, displayName, name, password, userPrincipalName, mail, department, title, telephoneNumber, description, password_never_expires, must_change_next_logon`。

## [2026-09-11] P2 用户组与计算机账号

- **新增** 用户组服务 `services/ad_group.py`：查询（关键字/安全组过滤）、创建（安全/通讯组、全局/域本地/通用作用域，`groupType` 位运算）、更新、删除、**成员分片管理**（分页查看 + 按 DN 或 sAMAccountName 解析后添加/移除）。
- **新增** 计算机账号服务 `services/ad_computer.py`：查询（关键字/启用过滤）、详情、启用/禁用（`userAccountControl`）、移动、删除。
- **新增** 接口 `api/v1/groups.py`：`/groups` 列表/增删改、成员查看/添加/移除，均接入 `check_scope` 与审计。
- **新增** 接口 `api/v1/computers.py`：`/computers` 列表/详情、启用/禁用/移动/删除，均接入授权与审计。
- **修正** `core/deps.check_scope`：改为按 `action` 匹配 `AdminScope.permissions` 列表 + `base_dn` DN 后缀子树判定（与 `AdminScope` 模型一致，免去每次请求的 LDAP 查询）。
- **新增** 前端 `views/groups/GroupView.vue`（组列表/新建/编辑/删除/成员分片）、`views/computers/ComputerView.vue`（计算机列表/启停/移动/删除）、`api/groups.ts`、`api/computers.ts`、路由与菜单项。
- **新增** 测试套件 `tests/`（pytest）：健康检查、鉴权、DN 编解码、AD 工具（UAC/FILETIME/组类型）、未配置域时 404、范围化授权（超管放行/无授权拒绝/子树内允许外拒绝）。`requirements-dev.txt` 提供 pytest。

### 影响 / 注意
- 授权基于 `AdminScope.permissions`（如 `["ou:write","group:read"]`）与 `base_dn` 后缀匹配，P5 提供委派界面。
- 添加组成员支持直接传 DN 或 sAMAccountName（后端自动解析）。
- 前端未在本沙箱构建（无 Node），需本机 `npm install && npm run dev`。

## [2026-09-11] P1 域用户管理

- **新增** AD 工具层 `services/ad_utils.py`：`userAccountControl` 位掩码解析/设置、FILETIME 与广义时间转换、CN/过滤转义。
- **新增** 域用户服务 `services/ad_user.py`：
  - 查询（分页 + 关键字/启用/锁定过滤，ldap3 `paged_search`）；
  - 创建（先设密码再启用，支持密码永不过期、下次登录改密）；
  - 更新常规属性、删除、启用/禁用、解锁（写 `lockoutTime=0`）、重置密码（`unicodePwd` UTF-16LE + 双引号，必须 LDAPS）、移动 OU。
- **新增** 接口 `api/v1/users.py`：列表、详情、增删改、启用/禁用/解锁/重置密码/移动，均接入范围化授权 `check_scope` 与审计落库 `audit.write_log`。
- **新增** 审计辅助 `services/audit.py`（`audit_log` 表写入）。
- **新增** 前端 `views/users/UserView.vue`：用户表格、查询、新建/编辑/重置密码/移动/启停/解锁/删除；`api/users.ts`；路由 `/users` 与菜单项。
- **新增** 用户相关 Pydantic 模型（UserOut / UserCreate / UserUpdate / ResetPasswordIn / UserMove / UserPage）。

### 影响 / 注意
- 域写操作（改密码、启用等）必须走 LDAPS，明文 389 会被域控拒绝。
- 解锁账号写 `lockoutTime=0`（UAC 的 LOCKOUT 位只读，不可直接写）。
- 新建用户默认禁用，本实现先设密码再启用，避免被密码策略拦截。
- 前端 Node 环境未在本沙箱验证（沙箱无 Node），需本机 `npm install && npm run dev`。

## [2026-09-11] P0 骨架

## [2026-09-11] P0 骨架

- **新增** 后端 FastAPI 工程骨架（`app/main.py`、CORS、路由挂载、启动建表）。
- **新增** 配置中心 `core/config.py`（pydantic-settings 读 `.env`）。
- **新增** 本地库模型 `models/`：`admin_user`、`admin_scope`、`domain_config`、`audit_log`、`batch_task`、`batch_task_item`（SQLAlchemy 2.x 声明式）。
- **新增** 认证 `core/security.py`（bcrypt 密码哈希、PyJWT 签发校验、Fernet 凭据加密）与 `core/deps.py`（当前管理员、超管、范围化授权校验）。
- **新增** 接口 `api/v1/auth.py`：本地账号登录、超管自举（首次初始化）、当前用户。
- **新增** 接口 `api/v1/domain.py`：域配置读写、连通性测试、域信息（BASE_DN 自动发现）。
- **新增** 接口 `api/v1/ous.py`：OU 树浏览、创建、重命名、删除、移动（含 `check_scope` 授权）。
- **新增** AD 对接 `services/ldap_conn.py`（连接池/自动发现/测试）与 `services/ad_ou.py`（OU 树构建与增删改）。
- **新增** DN 与 URL-safe Base64 互转工具（`core/dn.py` 后端 / `utils/dn.ts` 前端），避免 DN 进 URL 路径被切碎。
- **新增** 前端 Vue3 + Vite + Element Plus 脚手架：登录/初始化、主布局、概览、域配置、组织树页面，Axios 拦截器统一鉴权与错误处理。
- **新增** Docker 部署：`docker-compose.yml`、后端/前端 Dockerfile、nginx 反代配置。
- **新增** `backend/requirements.txt`、`.env.example`、`.gitignore`、`README.md`、`CHANGELOG.md`。

### 设计决策（本次）
- 登录平台用**本地账号**，连接 AD 用**独立的域服务账号**（凭据分离）。
- 范围化委派授权表 `admin_scope` 在 P0 即建好，P5 启用界面。
- 部署采用 Docker（postgres + backend + frontend）。

### 影响
- 仅 P0 骨架，域用户/组/计算机/批量/审计尚未实现（路线图 P1–P5）。
- 本地库用 `create_all` 建表；生产迁移后续由 Alembic 接管。

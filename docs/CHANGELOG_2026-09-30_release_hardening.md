# 2026-09-30 发布硬化（codex/release-hardening）

基线：`codex/release-local-validation` `00e8d49`。不新增业务功能；未连接生产、未执行 D1～D12、未推送或部署。

## 问题

本地发布验证发现：执行 P1～P3 的 migration 后，如果把代码回滚到 P0 之前（基线 `de95411`），旧代码新建 Case・Document・請求書・領収書时会报 MySQL 1364「Field ... doesn't have a default value」。原因是 Django 4.2 在添加 NOT NULL 列时只在执行 migration 时临时使用默认值，之后会去掉数据库级默认值；旧代码的 INSERT 不包含这些新列。

修复前实测（旧代码在最新表结构上）：Case 创建 `waiting_reason` 1364、請求書/領収書创建 `invoice_status` 1364；Document 因依赖案件而未能执行。

## 原先不兼容的字段与修复方式

由旧代码自身的模型对照最新表结构自动盘点（`scripts/rollback_compat/inventory.py`）得到 9 列，均以 follow-up migration 设置**数据库级默认值**（不修改已提交的旧 migration，不回填数据）：

| 列 | 默认值 | migration |
|---|---|---|
| `cases.work_status` | `'active'` | `cases/0021_db_defaults_for_rollback_compat` |
| `cases.waiting_reason` | `''` | 同上 |
| `cases.archive_reason` | `''` | 同上 |
| `case_documents.category` | `'other'` | `documents/0005_db_defaults_for_rollback_compat` |
| `case_documents.is_archived` | `0` | 同上 |
| `case_documents.sha256` | `''` | 同上 |
| `case_documents.archive_reason` | `''` | 同上 |
| `accounting_vouchers.invoice_status` | `''`（＝状態未設定・旧データ） | `accounting/0019_db_defaults_for_rollback_compat` |
| `accounting_vouchers.receipt_status` | `''` | 同上 |

- 为什么不用「允许 NULL」：这些列被新代码按值筛选（`is_archived=False` 的默认书类列表、`work_status` 的工作台、帳票状态筛选），NULL 会让旧代码新建的记录在新代码中「消失」；数据库默认值与模型默认值一致，读写语义不变。
- 已检查但无需修改：`cases.waiting_note`・`next_action_blocked_reason`・`accounting_vouchers.issued_snapshot`（MySQL 8.0.13+ 保留表达式默认值，mysql:8.0.46 确认）；P0 权限・审计相关列（均可空或在新表中）；見積書・契約書关联 FK（可空）；OfficeSettings・不动产台账快照（新表或可空）。
- 实现：`apps/common/db_defaults.py`（`ALTER TABLE ... ALTER COLUMN ... SET DEFAULT`，仅 MySQL/PostgreSQL；反向为 `DROP DEFAULT`），三个 migration 设为 `atomic = False`（MySQL 不能回滚 DDL）。

## 固定回归测试

- `backend/scripts/rollback_compat/run.sh <旧代码 backend> [--recreate]`：
  0. （`--recreate`）只重建 `gyoseishoshi_erp_rollback_compat_preview`，先用旧代码 migration 建旧表结构，记录最新代码的 `migrate --plan`；
  1. 最新代码 `migrate` 与 `migrate --check`；
  2. 旧代码 `inventory.py`：阻止旧代码 INSERT 的列（NOT NULL・无默认值・非自增）必须为 0，旧代码需要但不存在的列必须为 0；列出新表→旧表的外键（旧代码删除时的注意事项）；
  3. 旧代码 `old_code_writer.py`：经旧 API 创建 Case、Document（创建・更新・替换文件）、請求書、領収書，经旧 ORM 创建 Expense・Timeline・Task 并删除未被引用的 Document；
  4. 最新代码 `new_code_reader.py`：24 项检查（work_status=active、category=other、is_archived=False、帳票状态＝旧数据、出现在列表、受保护下载、可继续更新、旧請求書可迁移到発行済み）。
  - 脚本只连接该专用库，输出不含密码或个人信息。
- 单元测试 `apps/cases/tests_db_defaults.py`：检查 9 列的数据库默认值与 3 列的表达式默认值存在，并用不含新列的 INSERT 实际写入請求書。

## 结果

| 环境 | 结果 |
|---|---|
| 本地 MySQL 9.7.1，全新库（最新代码 migrate） | 盘点阻止列 0；旧代码写入失败 0；最新代码 24/24 |
| 本地，从基线表结构升级（`--recreate`，本来的生产路径） | `migrate --plan` 22 个；盘点 0；写入失败 0；读取 24/24 |
| 容器 mysql:8.0.46（已执行到 `00e8d49` 的库上增量执行 3 个硬化 migration；旧代码使用 `de95411` 镜像、共享 media 卷） | 盘点 0；写入失败 0；读取 24/24 |

## 其他修正

- `apps/real_estate/tests_import.py`：dry-run 重复执行测试每次重新生成 XLSX，openpyxl 写入保存时刻，跨秒时 SHA-256 不同导致全量测试偶发失败 → 两次执行使用同一字节序列（仅测试修正）。

## 文档

- `DEPLOY.md`：说明本次合并发布的 migration 与兼容性；新增「发布前固定回归：旧代码兼容性检查」；第 5/6 步补充 migrate 前后验证命令（`check`、`showmigrations`、`migrate --plan`、`migrate --check`、数据库默认值确认）；回滚分为「代码镜像回滚（无需恢复数据库）」与「数据操作需专用回滚命令或数据库整体恢复」。
- `RELEASE_LOCAL_VALIDATION_2026-09-29.md` §6～§8、`DATABASE.md` §11.10、`AI_HANDOFF.md` 已更新。

## 验证

- 后端 `python manage.py test`：292 项全部通过（新增 3 项）；`manage.py check`：no issues；`makemigrations --check --dry-run`：No changes detected；`git diff --check`：clean。
- 前端 `npm run test:unit`：12 项通过；`npm run build`：通过。
- 旧代码兼容性回归（本地全新库・本地基线升级・容器 mysql:8.0.46）：全部通过（见「结果」）。

## 追加：平台预览库与 nginx/前端回滚解耦

### 平台预览库

- 只对 `gyoseishoshi_erp_platform_preview` 执行 `accounting.0019`・`cases.0021`・`documents.0005`；执行前后 `SELECT DATABASE()` 均为该库；`migrate --check` 通过；9 列数据库默认值全部确认；浏览器确认 Dashboard・案件详情・书类一览・請求書・領収書正常。其他预览库未修改。

### 问题

旧的 frontend 镜像同时包含静态文件和 nginx 配置（P0 之前的配置公开 `/media/`），而且按提交回滚会连同 compose 和 nginx 配置一起退回，导致「回滚前端＝重新公开案件文件」。

### 解耦方式

- `frontend/Dockerfile`：只生成静态文件（`assets` 阶段：启动时把构建结果写入 `/dist` 后结束），不再包含 nginx 配置。
- `docker-compose.yml`：
  - `frontend-assets`：一次性服务，把静态文件写入 `frontend_dist` 卷。
  - `frontend`：`nginx:1.27-alpine`，只读挂载 `./nginx/default.conf`（最新安全配置）、`frontend_dist`（静态文件）、`static_volume`、`media_volume`（Web 根外 `/var/protected_media`）；依赖 `frontend-assets` 成功结束。
  - `backend`：`image: ${BACKEND_IMAGE:-sunrise-backend:current}`，可直接指定旧镜像启动。
- `scripts/deploy/release.sh`：
  - `verify-config`：解析正在运行的 `nginx -T`，`/media/`・`/sun/media/` 必须 `return 404`，`/_protected_media/` 必须 `internal`；不满足则失败（切换前自动执行，发现旧配置时拒绝切换）。
  - `verify-http`：`/media/`・`/sun/media/`・`/_protected_media/` 404，`/sun/` 200，`/sun/api/auth/csrf/` 正常。
  - `frontend-assets current|--from-image IMG|--from-ref REF`：只替换 `frontend_dist` 的内容（旧的「nginx 同梱」镜像也只取静态文件，并删除其中的 `media` 目录）。
  - `backend --image IMG`：`BACKEND_IMAGE=IMG up -d --no-build backend` 后 `wait-backend`，再做配置和 HTTP 检查。
  - `wait-backend`：轮询 `/api/auth/csrf/`（新旧 backend 都有；旧版没有 `/api/health/`），HTTP 200・本文 `CSRF cookie set`・`csrftoken` Cookie 三者齐全才判定启动；默认 180 秒（`WAIT_TIMEOUT`/`WAIT_INTERVAL`），超时把 `ps` 和 backend 日志保存到 `p0_ops/backend_timeout_*.log`（`RELEASE_LOG_DIR` 可改）并非 0 结束，不停止其他容器。

### 隔离容器验证（mysql:8.0.46）

| 场景 | 结果 |
|---|---|
| 当前静态文件 | `/media/`・`/sun/media/`・`/_protected_media/` 404；X-Accel 下载本人 200（书类・不动产文件内容一致），他人 404；`X-Accel-Redirect` 不外泄 |
| 静态文件切换到 `de95411` 旧镜像（镜像内含公开 `/media/` 的旧配置） | 旧 JS 加载 200；真实文件路径 `/media/`・`/sun/media/`・`/_protected_media/` 404；旧调试页面 404；受保护下载正常；浏览器中旧页面登录进入仪表盘 |
| 故意挂载旧 nginx 配置后执行切换 | `verify-config` 失败，切换被拒绝（退出码 1） |
| backend 切换到 `de95411` 旧镜像 / 切回当前 | 各约 3 秒通过 CSRF 检测，配置・HTTP 检查通过；旧 backend `No migrations to apply` |
| backend 停止状态下 `WAIT_TIMEOUT=6` | 6 秒后退出码 1，日志文件已保存，其他容器未停止 |

- 旧 backend 期间书类下载 404：旧代码依赖公开 `/media/`，安全配置下按设计不可用，数据不受影响。
- 环境限制：Docker Hub 拉取超时，nginx 运行环境使用本机已有的同一 `nginx:1.27-alpine` 基础镜像（配置与 html 被挂载覆盖）；`--from-ref`（需要拉取 node 镜像）未在容器中实测。

### 文档

- `DEPLOY.md`：第 13/15/16/17 步改为 `frontend-assets`＋nginx 运行环境与 `release.sh verify-config/verify-http`；回滚表改为「不 checkout 旧提交」，backend 与前端静态文件分别用 `release.sh` 回滚，nginx 安全配置不属于应用回滚对象；注明旧 backend 期间的下载限制。
- `RELEASE_LOCAL_VALIDATION_2026-09-29.md` §2b・§4・§7・§8、`AI_HANDOFF.md` 已更新。

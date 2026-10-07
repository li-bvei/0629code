# DEPLOY

## 服务器目录

生产服务器项目目录：

```bash
/www/wwwroot/0629code
```

进入项目目录：

```bash
cd /www/wwwroot/0629code
```

## 生产环境变量文件

生产环境使用：

```bash
.env.prod
```

不要使用 `.env.production` 作为部署环境文件名。

可以参考根目录的 `.env.prod.example` 创建 `.env.prod`，但不要提交真实密码。

`FIELD_ENCRYPTION_KEY` 用于加密マイナンバー（`Customer`/`FamilyMember`/`CompanyStaff` 的 `my_number` 字段），首次部署前必须生成一个真实值并写入 `.env.prod`（`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`），且之后不能再更改——改了旧数据就无法解密。

## Docker Compose 命令

所有生产部署命令统一使用：

```bash
docker compose --env-file .env.prod build
docker compose --env-file .env.prod up -d
```

后端启动时会执行 `collectstatic`，Django Admin / SimpleUI 静态文件会写入 Docker 共享卷 `static_volume`。
前端 Nginx 直接从该共享卷提供 `/static/` 和 `/sun/static/`。

上传文件使用共享卷 `media_volume`。**2026-09 P0 起不再公开 `/media/`、`/sun/media/`**：backend 把卷挂在 `/app/media`，frontend 只读挂在 Web 根目录之外的 `/var/protected_media`，文件只能经 `/api/documents/{id}/download|preview/` 鉴权后由 nginx `internal` location（X-Accel-Redirect）发送。

查看服务：

```bash
docker compose --env-file .env.prod ps
```

查看日志：

```bash
docker compose --env-file .env.prod logs -f
```

重启服务：

```bash
docker compose --env-file .env.prod restart
```

停止服务：

```bash
docker compose --env-file .env.prod down
```

## 更新上线流程

```bash
cd /www/wwwroot/0629code
git pull
docker compose --env-file .env.prod build
docker compose --env-file .env.prod up -d
```

## 访问地址

前端：

```text
http://43.139.37.150/sun/
```

Django Admin：

```text
http://43.139.37.150/sun/admin/
```

API：

```text
http://43.139.37.150/sun/api/
```

## 宝塔反向代理

Docker 前端服务只绑定服务器本机：

```text
127.0.0.1:8081
```

公网访问应通过宝塔 / Nginx 反向代理到：

```text
http://127.0.0.1:8081
```

当前服务器端口分配（2026-08-03 已核对）：

- `8080`：服务器原有 Java / `jsvc` 服务，本项目不可占用。
- `8081`：本项目 `0629code-frontend-1`。
- `8090`：另一个项目 `sunrise-diagnosis-web`，不可停止或改作本项目端口。

宝塔 vhost 中 `/sun/` 应保留完整路径转发：

```nginx
location ^~ /sun/ {
    proxy_pass http://127.0.0.1:8081;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

`proxy_pass` 末尾不要加 `/`，否则 `/sun/admin/`、`/sun/api/` 等路径会被错误改写。

## django-axes 首次迁移兼容

如果生产数据库已经存在 `axes_accessattempt`，但 `showmigrations axes` 显示 `0001_initial` 未应用，普通 `migrate` 会报 `Table 'axes_accessattempt' already exists`。先核对迁移状态：

```bash
docker compose --env-file .env.prod exec backend python manage.py showmigrations axes
```

仅在初始迁移显示未应用且现有 axes 表来自此前安装时，执行：

```bash
docker compose --env-file .env.prod exec backend python manage.py migrate axes --fake-initial
docker compose --env-file .env.prod exec backend python manage.py migrate
```

不要删除现有 axes 表，也不要执行 `docker compose down -v`。如果 `--fake-initial` 仍报错，应先检查 axes 表是否只创建了一部分，不能直接使用普通 `--fake`。

## 2026-08 新增迁移

以下迁移随本轮案件业务/税务证明改动一起产生，上线时按 `docker compose --env-file .env.prod exec backend python manage.py migrate` 的常规流程即可全部应用，不需要额外手工步骤——但其中一条涉及具体生产数据，需要按下方说明单独核对。

- `apps/cases/migrations/0012_casechecklisttemplate_application_category_and_more.py`：加法迁移，给 `CaseChecklistTemplate` 新增可选外键 `case_type_master`/`application_category`。
- `apps/cases/migrations/0013_seed_checklist_template_case_type_links.py`：数据迁移（`RunPython`），按名称精确匹配把 5 个已有模板关联到对应「案件種別＋申請区分」。幂等，按名称查找、找不到就跳过，不会重复关联也不会报错。
- `apps/cases/migrations/0014_seed_engineer_humanities_change_template.py`：数据迁移，创建一份新模板"技人国ビザ変更申請"（复制"技人国ビザ新規申請"的全部项目内容）。幂等，同名模板已存在则跳过。
- `apps/cases/migrations/0015_case_residence_card_received_at.py`：加法迁移，给 `Case` 新增可选字段 `residence_card_received_at`。
- `apps/cases/migrations/0016_apply_change_template_to_case_zhang_jing.py`：**数据迁移，涉及具体生产案件记录，上线前必须先核对**。按 `case_number='技人国-変更-202608-張 静-0001'` 精确查找这一条真实案件，仅当该案件当前完全没有任何清单项（`CaseChecklistItem`）时，才会把"技人国ビザ変更申請"模板的材料清单套用进去；如果这条案件在生产环境已经有清单项（不管是手动加的还是别的原因），迁移会直接跳过、不做任何改动。**执行前要求**：
  1. 确认生产库里确实存在案件号为 `技人国-変更-202608-張 静-0001` 的案件（不同环境如果案件号生成时间不同，理论上应该一致，但仍建议先用只读查询确认一次）。
  2. 迁移前对相关表（至少 `cases`、`case_checklist_items`）做一次数据库备份，或确认已有常规备份机制覆盖到本次上线时间点。
  3. 迁移执行完成后，登录后台核对这条案件的「案件進捗・必要資料」是否已经正确出现约 22 项材料清单，且没有产生重复项。
  4. 该迁移是可逆的（`reverse` 会删除由它创建的清单项），但反向操作同样建议先核对再执行，不要在不确定的情况下直接 `migrate cases 0015` 回退。
- `apps/companies/migrations/0009_company_establishment_number_and_more.py`：加法迁移，给 `Company` 新增可选字段 `establishment_symbol`/`establishment_number`。
- `apps/accounting/migrations/0014_taxrenewalvoucherrecord_case.py`：加法迁移，给 `TaxRenewalVoucherRecord` 新增可选外键 `case`。

以上除 `0016` 外均为纯加法迁移或按名称匹配的幂等数据迁移，不修改任何现有记录的既有字段值，风险较低；`0016` 是本轮唯一"迁移逻辑会写入具体一条生产记录数据"的例外，按上面 4 步走。


## 2026-09 P0 访问控制上线（尚未执行，每个数据操作须用户单独批准）

设计依据：`docs/SYSTEM_ARCHITECTURE.md`、`docs/P0_ACCESS_CONTROL_DESIGN.md`（D1～D12）。本节是生产执行清单，**AI 不得自行执行**。**任何一步失败都立即停止**，不要继续后面的步骤；按本节末尾的回滚表处理。

### 新增 migration（均为加法，不写业务数据）

| migration | 内容 |
|---|---|
| `employees/0002_employee_user` | `employees.user_id`（OneToOne，可空） |
| `authentication/0001_initial` | `authentication_protected_accounts` 表，以及权限 `manage_users`、`use_diagnostics` |
| `audit/0001_initial` | `audit_logs` 表 |
| `accounting/0015_expense_owner_and_business_permissions` | `accounting_expenses.owner_id/created_by_id/updated_by_id`（可空），以及会计各模块权限 |
| `cases/0017`、`customers/0009`、`customers/0010_party_link_permissions`、`documents/0003` | 只新增自定义 Permission（含 `customer_link_all`、`company_link_all`），不改表结构 |

本次合并发布（P0～P3＋平台收尾＋发布硬化）的完整 migration 列表与顺序见 `docs/RELEASE_LOCAL_VALIDATION_2026-09-29.md` §6。P1～P3 新增了若干 NOT NULL 列；发布硬化的 follow-up migration（`accounting/0019`、`cases/0021`、`documents/0005`，只设置数据库级默认值、不写数据）让 P0 之前的旧代码在最新表结构上仍能创建 Case・Document・請求書・領収書等。因此**代码镜像回滚不需要反向 migration**，前提是发布前的「旧代码兼容性检查」通过（见下节）。

### 发布前固定回归：旧代码兼容性检查

每次发布前（含本次）必须执行，结果保存到 `p0_ops/`。检查内容：用最新代码 migrate 到最新表结构 → 用 P0 之前的旧代码（基线 `de95411`）列出会阻止旧代码 INSERT 的列并实际写入 Case・Document（创建・更新・替换）・請求書・領収書・Expense・Timeline・Task → 用最新代码读取并更新这些记录。

本地（专用临时库 `gyoseishoshi_erp_rollback_compat_preview`，脚本拒绝连接其他库）：

```bash
git worktree add --detach ../0629code-baseline-de95411 de95411      # 旧代码（依赖与现行 requirements 相同）
backend/scripts/rollback_compat/run.sh ../0629code-baseline-de95411/backend --recreate
# 期望：inventory 的 blocking/missing 为空；old_writer failures 为空；new_reader failures 为空
```

容器（mysql:8.0，与生产相同的镜像构成；在隔离的 compose 项目中执行，不要对生产执行）：

```bash
docker build -t <项目>-old-backend <de95411 的 git archive>/backend
docker run --rm --network <项目>_default --env-file .env.prod -e MYSQL_HOST=db -e ROLLBACK_COMPAT_DB=<该隔离库名> \
  -v <项目>_media_volume:/app/media -v $PWD/backend/scripts/rollback_compat:/rc:ro -w /app <项目>-old-backend python /rc/inventory.py
#（同样执行 /rc/old_code_writer.py，再用新 backend 镜像执行 /rc/new_code_reader.py <writer 输出>）
```

常规测试 `apps/cases/tests_db_defaults.py` 会检查这些数据库默认值是否存在（如果以后的 `AlterField` 把默认值去掉，测试会失败，需在新 migration 中用 `apps.common.db_defaults` 重新设置）。

### 关于新旧代码交接

- 新代码对业务权限只认显式的 Group 或授权，不认 `is_superuser`。所以 **D2～D7 必须在新后端对用户开放之前完成**，本清单把它们放在维护模式中、启动新后端之前执行。
- compose 里 backend 的启动命令会自动执行 `migrate`。本清单改为用一次性容器（`run --rm`）先执行 `migrate --plan` 和 `migrate`，再 `up`；`up` 时的自动 `migrate` 就不会再有变化。
- 旧镜像里没有新的管理命令，所以 D1 用旧系统自带的 `manage.py shell` 做只读查询。

### 变量

```bash
cd /www/wwwroot/0629code
mkdir -p p0_ops                      # 快照、回填 CSV、日志保存到宿主机
OLD_EXEC="docker compose --env-file .env.prod exec backend python manage.py"      # 旧系统运行中使用
RUN="docker compose --env-file .env.prod run --rm --no-deps -v $PWD/p0_ops:/ops backend python manage.py"  # 新镜像一次性容器
```

### 执行顺序

**1. D1 只读核对（旧系统仍在运行）**：结果交用户确认，确认后才进入第 2 步。

```bash
$OLD_EXEC shell -c "
from django.contrib.auth.models import User, Group
from django.db.models import Count, Min, Max, Sum
from apps.employees.models import Employee
from apps.accounting.models import Expense
from apps.documents.models import Document
for u in User.objects.order_by('id'):
    print('user', u.id, u.username, u.last_name + u.first_name, 'active', u.is_active, 'staff', u.is_staff, 'superuser', u.is_superuser, list(u.groups.values_list('name', flat=True)))
for e in Employee.objects.order_by('id'):
    print('employee', e.id, e.name, e.is_active)
print('groups', list(Group.objects.values_list('name', flat=True)))
print('expense', Expense.objects.aggregate(n=Count('id'), min_id=Min('id'), max_id=Max('id'), min_date=Min('expense_date'), max_date=Max('expense_date'), total=Sum('amount')))
print('documents', Document.objects.count(), 'with_file', Document.objects.exclude(file='').count())
" | tee p0_ops/d1_readonly.txt
docker run --rm -v 0629code_media_volume:/m:ro alpine sh -c 'echo files: $(find /m -type f | wc -l); find /m -type f | sed "s#^/m/##" | cut -d/ -f1 | sort | uniq -c' | tee -a p0_ops/d1_readonly.txt
```

（不输出密码哈希或 Token。卷名以 `docker volume ls` 为准。）

**2. 开启维护模式**：在宝塔 vhost 中对 `/sun/` 返回维护页（503），只放行操作人员的 IP。

**3. 备份**（必须）

```bash
docker compose --env-file .env.prod exec db sh -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE"' > p0_ops/backup_before_p0_$(date +%Y%m%d_%H%M).sql
docker run --rm -v 0629code_media_volume:/m:ro -v "$PWD/p0_ops":/b alpine tar czf /b/media_before_p0_$(date +%Y%m%d_%H%M).tgz -C /m .
docker compose --env-file .env.prod images | tee p0_ops/images_before_p0.txt     # 记录回滚用的镜像
```

**4. 准备新后端镜像，并停止旧后端**（防止迁移期间有写入）

```bash
git fetch && git checkout <P0 合并后的提交>
# .env.prod 追加 .env.prod.example 中「P0 アクセス制御」的变量（PROTECTED_ADMIN_ENFORCEMENT=False, LOCALDEV_CHECK_MODE=warn）
docker compose --env-file .env.prod build backend
docker compose --env-file .env.prod stop backend
```

**5. migrate 前的验证**（确认只包含 `RELEASE_LOCAL_VALIDATION_2026-09-29.md` §6 列出的 migration；发布前的旧代码兼容性检查已通过）

```bash
$RUN check | tee p0_ops/check_before.txt                      # System check identified no issues
$RUN showmigrations --plan | grep '\[ \]' | tee p0_ops/migrate_pending.txt   # 待执行的 migration 一览
$RUN migrate --plan | tee p0_ops/migrate_plan.txt
```

**6. migrate 与 migrate 后的验证**

```bash
$RUN migrate | tee p0_ops/migrate.txt
$RUN migrate --check && echo "no unapplied migrations"         # 未执行的 migration 为 0（非 0 退出则停止）
$RUN shell -c "
from django.db import connection
from apps.common.db_defaults import ROLLBACK_COMPAT_DEFAULTS
with connection.cursor() as c:
    for items in ROLLBACK_COMPAT_DEFAULTS.values():
        for t, col, lit in items:
            c.execute('SELECT column_default FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s', [t, col])
            print(t, col, 'default=', c.fetchone()[0])
" | tee p0_ops/db_defaults_after.txt                           # 9 列全部有默认值（None 则停止）
$RUN check_access_config            # 阶段 A：保护账号为空时只输出 WARNING
```

**7. D2/D3 关联账号**（先不加 `--apply` 看差异，确认后再加 `--apply --yes`）

```bash
$RUN link_user_employee --plan
$RUN link_user_employee --map zbry6947@gmail.com:李 --map zywwind@gmail.com:周 --create-employee jiao:焦
$RUN link_user_employee --map zbry6947@gmail.com:李 --map zywwind@gmail.com:周 --create-employee jiao:焦 --apply --yes
```

**8. D4 阶段 A：快照 + 注册李为受保护账号**

```bash
$RUN export_access_snapshot --output /ops/access_snapshot_before_p0.json
$RUN protect_account --username zbry6947@gmail.com
$RUN protect_account --username zbry6947@gmail.com --apply --yes
```

**9. D6/D7 创建角色并分配**

```bash
$RUN setup_access_roles
$RUN setup_access_roles --apply --yes
$RUN assign_business_roles --username zbry6947@gmail.com --roles system_admin,accounting_admin,business_admin --apply --yes
$RUN assign_business_roles --username jiao --roles business_admin,expense_viewer --apply --yes
$RUN assign_business_roles --username zywwind@gmail.com --roles business_admin,expense_viewer --apply --yes
$RUN check_access_config
```

**10. 启动新后端**

```bash
docker compose --env-file .env.prod up -d backend
curl -s http://127.0.0.1:8081/sun/api/health/        # {"status":"ok"}
curl -s http://127.0.0.1:8081/sun/api/readiness/     # {"status":"ready"}
```

**11. 验证登录和权限**（维护模式下从放行 IP 访问）

- 李：能登录；能看到全部案件、全部 Expense、余额、收入和帐票；能使用账号管理；能进 Django Admin。
- 焦、周：能登录；Expense 能看全部，但不能修改或导出他人记录；看不到余额、收入、帐票、Visa、税务；案件能看全部，但只能修改本人担当的；关联其他担当者的顾客/公司会返回 403。
- 确认恢复命令可用：`$RUN help changepassword`、`$RUN restore_access_snapshot /ops/access_snapshot_before_p0.json --dry-run`。

**12. D8 Expense 回填**（`P0_ACCESS_CONTROL_DESIGN.md` §9.2 的 8 个步骤）

```bash
$RUN backfill_expense_owner --username zbry6947@gmail.com                   # 核对条数 N（应与 D1 一致）
$RUN backfill_expense_owner --username zbry6947@gmail.com --apply --yes --expect-count N --output-dir /ops
```

**13. 准备前端静态文件**

发布硬化后，前端静态文件（`frontend-assets`，只写入 `frontend_dist` 卷）与 nginx 运行环境（`frontend`，`nginx:1.27-alpine` 只读挂载仓库的 `nginx/default.conf`）已经分离。这一步只 **build** 静态文件镜像，并提前拉取 nginx 镜像；实际切换放在第 16 步（D10）。

```bash
docker compose --env-file .env.prod build frontend-assets
docker compose --env-file .env.prod pull frontend             # nginx:1.27-alpine
grep -nE "location \^~ /(sun/)?media/|_protected_media|internal|return 404" nginx/default.conf   # 安全规则存在
```

**14. D9 媒体引用盘点**（只读；若「/media/ 参照 合計」大于 0，先停下来确认处理方式）

```bash
$RUN inventory_media_references | tee p0_ops/d9_media_inventory.txt
```

**15. nginx 语法检查**：放到第 16 步切换之后，用运行中的容器执行 `docker compose --env-file .env.prod exec -T frontend nginx -t`。不要在切换前用 `run --rm frontend nginx -t`：首次部署时 `frontend_dist` 卷还是空的，只读挂载下无法创建 `/static` 挂载点，容器会启动失败（2026-10-02 生产实际遇到；不是配置错误）。第 16 步的 `release.sh verify-config` 也会读取运行中 nginx 的完整配置。

**16. D10 切换前端和 nginx**（关闭公开 `/media/`，media 卷改挂到 Web 根目录之外）

```bash
docker compose --env-file .env.prod up -d frontend            # 先执行一次 frontend-assets 写入静态文件，再启动 nginx
scripts/deploy/release.sh verify-config                        # 正在运行的 nginx 含 /media/ 404・/_protected_media/ internal
```

**17. 验证下载、预览和旧文件**

```bash
scripts/deploy/release.sh verify-http      # /media/・/sun/media/・/_protected_media/ → 404，/sun/ → 200，/sun/api/auth/csrf/ 正常
curl -sI http://127.0.0.1:8081/sun/media/case_documents/任意文件名 | head -1          # 期望 404（用真实文件名再确认一次）
```

然后用李的账号，在书类一览中下载和预览一个既有文件（PDF、日文文件名、大文件断点续传），确认审计里有 `download_authorized`/`download_started`。再用焦的账号访问非本人担当案件的文件，确认返回 403 并有 `download_denied`。

**18. D5 阶段 B：Admin 只允许受保护账号**

```bash
# .env.prod：DJANGO_PROTECTED_ADMIN_ENFORCEMENT=True
docker compose --env-file .env.prod up -d backend
$RUN check_access_config            # 保护表为空时会失败
```

确认李能进 Admin，焦、周不能进。

**19. D11 焦、周降级**

```bash
$RUN export_access_snapshot --output /ops/access_snapshot_before_demote.json
$RUN shell -c "from django.contrib.auth.models import User; print(User.objects.filter(username__in=['jiao','zywwind@gmail.com']).update(is_superuser=False, is_staff=False))"
```

确认焦、周仍能登录，业务范围不变，但进不了 Admin 和账号管理。

**20. D12 localdev**：根据 D1 结果决定。生产上存在且启用的 `localdev`，经批准后只能停用（`is_active=False`），不删除；确认后把 `DJANGO_LOCALDEV_CHECK_MODE` 改为 `enforce`，再执行 `check_access_config`。

**21. 退出维护模式**：恢复宝塔 vhost。

### 生产诊断端点

生产只保留 `GET /api/health/`（存活）和 `GET /api/readiness/`（DB 连接），两者都不返回业务数据，未登录也可访问。seed、demo、PDF 坐标调试、调试 HTML，以及任何返回业务数据的诊断端点，在生产中都不注册（`ENABLE_DEV_TOOLS=False`，或 `APP_ENV=production`）。

### 回滚

回滚分为两类。**代码镜像回滚不再以数据库整体恢复为唯一手段**：发布硬化后，旧代码可以在最新表结构上运行（由「旧代码兼容性检查」保证），所以只要没有做过下面第 2 类的数据操作，退回旧镜像即可。

**1. 兼容性修正后可执行的代码镜像回滚（不需要反向 migration，不需要恢复数据库）**

| 对象 | 方法 |
|---|---|
| 第 5～9 步失败（新后端尚未对用户开放） | 停止操作；`docker compose up -d backend` 用第 4 步之前的镜像（见 `p0_ops/images_before_p0.txt`）或上线前的提交重新 build。新表・新列（含数据库默认值）保留 |
| backend 代码 | **不要 checkout 旧提交**（旧 compose/nginx 会一起回退）。保持当前仓库，执行 `scripts/deploy/release.sh backend --image <第 3 步记录的旧 backend 镜像>`：以旧镜像启动 backend，轮询 `/api/auth/csrf/`（新旧版本都存在；默认最长 180 秒，`WAIT_TIMEOUT` 可调），HTTP 200 且取得 CSRF 响应后，再检查 nginx 安全配置和 HTTP；超时会把 backend 日志保存到 `p0_ops/backend_timeout_*.log` 并以非 0 结束。新表・新列保留。回到新版：`release.sh backend --image sunrise-backend:current` |
| frontend 静态文件 | **nginx 配置不随之回滚**。`scripts/deploy/release.sh frontend-assets --from-image <旧 frontend 镜像>`（旧的「nginx 同梱」镜像也可以，只取静态文件）或 `--from-ref <旧 git 版本>`（仅重新构建静态文件）。脚本在切换前检查正在运行的 nginx 含受保护媒体规则（缺少则拒绝切换），切换后再做 HTTP 检查。回到新版：`release.sh frontend-assets current` |
| nginx 安全配置 | 不属于应用代码回滚对象。`nginx/default.conf` 以当前（最新安全）版本只读挂载；如需修改须作为单独的变更审查，并再次执行 `release.sh verify-config`・`verify-http` |

回到 P0 之前的旧 backend 时的限制：旧代码的书类下载依赖公开的 `/media/`，在最新安全 nginx 下会返回 404。回滚期间案件文件无法下载（文件和元数据不会丢失，重新上线新 backend 后恢复）；这是为了不因回滚而重新公开文件。
| 阶段 B | `DJANGO_PROTECTED_ADMIN_ENFORCEMENT=False`，重启 backend |
| 李无法登录 | `$RUN changepassword zbry6947@gmail.com`、`$RUN axes_reset_username zbry6947@gmail.com`、`$RUN protect_account --username zbry6947@gmail.com --apply --yes`、`$RUN restore_access_snapshot /ops/<file> --user zbry6947@gmail.com --apply --yes` |

注意（2026-10-02 批次）：`real_estate/0005_bulk_change_permission` 只新增一个 Permission 行；`accounting/0020_expense_category_rules` 新建规则表并写入 3 条初始规则（提案先为既有类别「停车费」，不改写支出记录）。两者都不影响旧代码运行。`0020` 不创建也不启用类别。migrate 后需执行 `setup_access_roles --apply --yes`，`system_admin` 才会得到 `real_estate.bulk_change_real_estate`；并执行只读检查 `$RUN check_expense_category_rules`（非 0 退出时按输出处理：缺失用 `--apply --yes --username <执行者>` 补登记；类别被停用时由管理员决定是否启用，命令不会自动启用，也不会创建「駐車場代」等别名类别）。详见 `docs/CHANGELOG_2026-10-02_real_estate_batch_reception.md` §4。

注意（不动产 `real_estate.0004_collaborative_ledger`）：该 migration 会删除旧担当关联、三项废止来源金额列和旧权限 `real_estate_view_all`・`real_estate_change_all`，反向 migrate 无法复原这些内容。生产首次上线时不动产表为空，不丢数据；回滚到 P0 之前的代码不受影响，但**不得回滚到 `0004` 之前的 P3 版本镜像**。详见 `docs/RELEASE_LOCAL_VALIDATION_2026-09-29.md` §6。

注意（旧代码在新表结构上的已知限制）：旧代码不认识 P1～P3 的新表（見積書・契約書・不動産・监查日志等）。如果新代码运行期间已经有新表数据引用了某个案件、顾客、公司、书类或用户，旧代码删除该记录时会被数据库外键拒绝（不会产生不一致，只是删除失败）。日常请用归档而非删除。新代码运行期间写入的新表数据在回滚期间保留，重新上线新代码后恢复可见。

**2. 代码回滚不能撤销、需要专用回滚命令或数据库整体恢复的情况**

| 对象 | 方法 |
|---|---|
| 账号、Group、superuser（D2～D7、D11） | `$RUN restore_access_snapshot /ops/<snapshot>.json`（先看差异，再加 `--apply --yes`；可以用 `--user` 限定账号）。代码回滚本身不会恢复权限变更 |
| Expense 回填（D8，真实数据写入） | `$RUN backfill_expense_owner --rollback /ops/<csv>`（先看差异，再加 `--apply --yes`）；CSV 丢失时只能整体恢复 |
| localdev 停用（D12） | 由李确认后手动恢复 `is_active` |
| 正式 Excel（LIST.xlsx）导入（`import_real_estate_list`） | `import_real_estate_list --rollback /ops/<ID 清单 CSV> --username <执行者>`（先看差异，再加 `--apply --yes`）；导入后被修改或已有台账等子数据的记录不会被删除，只报告 |
| 反向 migration（仅在必须删除新表/新列时） | 须先备份并批准；会丢失 owner、关联、审计、帳票、不动产等数据。一般不需要 |
| 数据整体恢复（误操作、数据损坏） | 用第 3 步的 SQL 和媒体卷备份恢复（须批准，先在测试环境演练） |


## 案件文件的备份与恢复（P2 文件管理）

文件实体保存在 Docker 卷 `media_volume`（backend 挂载为 `/app/media`，frontend nginx 只读挂载为 `/var/protected_media`），元数据保存在数据库 `case_documents` 和 `case_document_replacements` 表。**两者必须一起备份和恢复。**

### 备份（建议每天，另外在上线或大量导入之前额外做一次）

```bash
cd /www/wwwroot/0629code
STAMP=$(date +%Y%m%d_%H%M)
docker compose --env-file .env.prod exec db sh -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE"' > backups/db_$STAMP.sql
docker run --rm -v 0629code_media_volume:/m:ro -v "$PWD/backups":/b alpine tar czf /b/media_$STAMP.tgz -C /m .
sha256sum backups/db_$STAMP.sql backups/media_$STAMP.tgz > backups/checksums_$STAMP.txt
```

- 备份文件存放到服务器之外（加密存储），定期检查能否恢复。
- 替换前的文件也留在卷里，所以它们也会被备份。
- 卷名以 `docker volume ls` 显示为准。

### 恢复（需批准；先在测试环境演练）

1. 进入维护模式，停止 backend。
2. 用同一时间点的 SQL 恢复数据库。
3. 恢复媒体卷：`docker run --rm -v 0629code_media_volume:/m -v "$PWD/backups":/b alpine sh -c "cd /m && tar xzf /b/media_<STAMP>.tgz"`。
4. 执行 `python manage.py inventory_media_references`（只读），核对「有 Document 但实体文件不存在」的数量为 0；「实体文件没有对应 Document」的只报告，不删除。
5. 抽查几个 Document，用受保护下载确认能取到文件，SHA-256 与数据库一致。

### 保留与删除

- 日常请用「归档」，不要删除。归档后文件仍保留，也仍可以通过受保护下载获取。
- 删除（DELETE）会物理删除文件，只在确有必要时执行；批量删除必须先预览并获得批准。
- 替换历史和替换前的文件不会自动删除。需要清理时，另行设计并获得批准。
- 没有接入杀毒软件，只做扩展名白名单和文件头签名检查。如果要接入外部扫描，另行评估。

## P6 部署与生产数据整理（D5、D11、费用负责人回填）

> **状态（2026-10-07）：没有执行。** AI 没有服务器访问权限，生产操作由用户在服务器终端执行。以下步骤必须在 P6 代码验收和部署之后、按顺序执行。任何一步出现异常都要**立即停止并报告**，不要继续写入。整个过程不修改任何密码。

### P6 部署要点

- 新 migration：`accounting/0025～0027`（服务项目价格状态；投入 8 项暂定价格项目）、`customers/0011`（My Number 表示权限）、`documents/0006～0007`（资料内容、显示名）。都是新增，旧代码仍可运行。
- 新依赖：`jpholiday==1.0.3`（已在 `requirements.txt` 中，构建镜像时安装，运行时不需要外网）。
- migrate 后执行 `setup_access_roles`：先 dry-run 确认只有 `system_admin` 增加 `customers.reveal_my_number`，再加 `--apply --yes`。
- 需要个别授权时：`$RUN grant_business_permission --username <账号> --permission customers.reveal_my_number`，dry-run 确认后加 `--apply --yes`；收回时加 `--revoke`。
- 不新增 `FIELD_ENCRYPTION_KEY`，My Number 不重新加密。

### 变量

```bash
cd /www/wwwroot/0629code
mkdir -p p6_ops
EXEC="docker compose --env-file .env.prod exec -T backend python manage.py"
STAMP=$(date +%Y%m%d_%H%M)
```

### 1. 只读确认（结果写入 `p6_ops/readonly_$STAMP.txt`，交用户确认）

```bash
{
git rev-parse HEAD; git status --short | head
docker compose --env-file .env.prod ps
$EXEC showmigrations --plan | grep '\[ \]' || echo "no pending migrations"
$EXEC check_access_config
$EXEC shell -c "
from django.contrib.auth.models import User
from django.db.models import Count, Min, Max, Sum
from apps.authentication.models import ProtectedAccount
from apps.employees.models import Employee
from apps.accounting.models import Expense
print('protected', list(ProtectedAccount.objects.values_list('user__username', flat=True)))
for u in User.objects.order_by('id'):
    print('user', u.id, u.username, 'active', u.is_active, 'staff', u.is_staff, 'superuser', u.is_superuser,
          sorted(u.groups.values_list('name', flat=True)), 'employee', getattr(getattr(u, 'employee', None), 'id', None))
print('employees', list(Employee.objects.values_list('id', 'name', 'is_active')))
q = Expense.objects.filter(owner__isnull=True)
print('null_owner', q.aggregate(n=Count('id'), min_id=Min('id'), max_id=Max('id'), min_date=Min('expense_date'),
      max_date=Max('expense_date'), min_amount=Min('amount'), max_amount=Max('amount'), total=Sum('amount')))
"
df -h / /var/lib/docker
ls -lh backups p0_ops p6_ops 2>/dev/null | tail -20
} 2>&1 | tee p6_ops/readonly_$STAMP.txt
```

确认要点（任何一项不符都停止）：

- 提交和容器与已部署的 P6 一致，没有未执行的 migration。
- 受保护账号只有 `zbry6947@gmail.com`（李）。
- 李：`system_admin, accounting_admin, business_admin`，关联 Employee「李」。
- 周（`zywwind@gmail.com`）、焦（`jiao`）：`business_admin, expense_viewer`，各自关联 Employee。如果 Group 不符，就停止（D11 不负责补 Group）。
- NAING：截至 2026-10-03 只有担当者记录、没有账号。如果已建账号，必须是普通用户（staff、superuser 都是 False，没有管理 Group），否则停止并报告，不要修改。
- `null_owner` 的件数、ID 范围、日期范围、金额范围都记录下来。件数以本次实测为准，不使用历史值 1335。
- 磁盘剩余空间足够容纳数据库和媒体备份（至少是上一次备份大小的 2 倍）。

### 2. 备份与完整性确认

```bash
docker compose --env-file .env.prod exec -T db sh -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE"' > p6_ops/db_before_p6data_$STAMP.sql
docker run --rm -v 0629code_media_volume:/m:ro -v "$PWD/p6_ops":/b alpine tar czf /b/media_before_p6data_$STAMP.tgz -C /m .
tail -1 p6_ops/db_before_p6data_$STAMP.sql | grep -q 'Dump completed' && echo "sql complete"
gzip -t p6_ops/media_before_p6data_$STAMP.tgz && echo "tgz ok"
tar tzf p6_ops/media_before_p6data_$STAMP.tgz | wc -l
sha256sum p6_ops/db_before_p6data_$STAMP.sql p6_ops/media_before_p6data_$STAMP.tgz | tee p6_ops/checksums_$STAMP.txt
$EXEC export_access_snapshot --output /tmp/access_snapshot_before_p6data.json && docker compose --env-file .env.prod cp backend:/tmp/access_snapshot_before_p6data.json p6_ops/
```

没有出现 `sql complete` 和 `tgz ok`、文件数与第 1 步明显不一致，或者快照没有生成时，都要停止。

### 3. dry-run（不写入）

```bash
# D5：只确认，不修改。保护账号为空或有问题时 check_access_config 会失败
$EXEC check_access_config | tee p6_ops/d5_check_$STAMP.txt
# D11：确认降级对象只有焦、周，并且他们已经有业务角色
$EXEC shell -c "
from django.contrib.auth.models import User
for u in User.objects.filter(username__in=['jiao', 'zywwind@gmail.com']):
    print(u.username, 'staff', u.is_staff, 'superuser', u.is_superuser, sorted(u.groups.values_list('name', flat=True)))
" | tee p6_ops/d11_dryrun_$STAMP.txt
# 费用负责人回填（dry-run）：记下输出的件数 N，必须与第 1 步的 null_owner 一致
$EXEC backfill_expense_owner --username zbry6947@gmail.com | tee p6_ops/backfill_dryrun_$STAMP.txt
```

### 4. 向用户报告并取得批准

报告第 1～3 步的结果（账号关系、件数 N、ID、日期和金额范围、备份文件与校验值），得到明确批准后再进入第 5 步。

### 5. 执行（只在第 1～4 步都一致时）

```bash
# D5：开启 Admin 只允许受保护账号
# .env.prod：DJANGO_PROTECTED_ADMIN_ENFORCEMENT=True
docker compose --env-file .env.prod up -d backend
$EXEC check_access_config
# D11：焦、周去掉 superuser 和 staff，保留业务角色（不改密码）
$EXEC shell -c "from django.contrib.auth.models import User; print(User.objects.filter(username__in=['jiao','zywwind@gmail.com']).update(is_superuser=False, is_staff=False))"   # 期望输出 2
# 回填：N 使用第 3 步的实际值
docker compose --env-file .env.prod run --rm --no-deps -v $PWD/p6_ops:/ops backend python manage.py backfill_expense_owner --username zbry6947@gmail.com --apply --yes --expect-count N --output-dir /ops
```

### 6. 验证

- 再次执行第 1 步的 shell：
  - 焦、周的 staff 和 superuser 都是 False，Group 不变；
  - 李不变，NAING 不变；
  - `null_owner` 为 0；
  - 生成了回填 CSV。
- 李能进入 Admin；焦、周登录后业务范围不变，但不能进入 Admin 和账号管理。
- 回滚：
  - 权限用 `restore_access_snapshot /ops/access_snapshot_before_p6data.json`（先看差异，再加 `--apply --yes`）；
  - 回填用 `backfill_expense_owner --rollback /ops/<csv>`；
  - D5 改回 `DJANGO_PROTECTED_ADMIN_ENFORCEMENT=False` 后执行 `up -d backend`。

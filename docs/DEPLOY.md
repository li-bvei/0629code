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

旧代码可以在新表结构上运行（新增列都可空），所以代码回滚不需要反向 migration。

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

**5. migrate --plan**（确认只包含上表列出的 migration）

```bash
$RUN migrate --plan | tee p0_ops/migrate_plan.txt
```

**6. migrate**

```bash
$RUN migrate | tee p0_ops/migrate.txt
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

**13. 准备前端**

frontend 镜像里同时包含前端页面和 nginx 配置，所以这一步只 **build**，不 `up`；实际切换放在第 16 步（D10）。

```bash
docker compose --env-file .env.prod build frontend
```

**14. D9 媒体引用盘点**（只读；若「/media/ 参照 合計」大于 0，先停下来确认处理方式）

```bash
$RUN inventory_media_references | tee p0_ops/d9_media_inventory.txt
```

**15. 在 nginx 容器中检查语法**（本地从未做过，这是阻断项）

```bash
docker compose --env-file .env.prod run --rm --no-deps frontend nginx -t
```

**16. D10 切换前端和 nginx**（关闭公开 `/media/`，media 卷改挂到 Web 根目录之外）

```bash
docker compose --env-file .env.prod up -d frontend
```

**17. 验证下载、预览和旧文件**

```bash
curl -sI http://127.0.0.1:8081/sun/media/case_documents/任意文件名 | head -1          # 期望 404
curl -sI http://127.0.0.1:8081/media/case_documents/任意文件名 | head -1              # 期望 404
curl -sI http://127.0.0.1:8081/_protected_media/case_documents/任意文件名 | head -1   # 期望 404
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

| 对象 | 方法 |
|---|---|
| 第 5～9 步失败（新后端尚未对用户开放） | 停止操作；`docker compose up -d backend` 用第 4 步之前的镜像（见 `p0_ops/images_before_p0.txt`）或上线前的提交重新 build。新增列和新表可以保留，不影响旧代码 |
| backend 代码 | 回到上线前的提交，`build backend && up -d backend`；不需要反向 migration |
| frontend + nginx | 回到上线前的提交或旧镜像，`build frontend && up -d frontend`（docker-compose 的 media 挂载一起恢复） |
| 阶段 B | `DJANGO_PROTECTED_ADMIN_ENFORCEMENT=False`，重启 backend |
| 账号、Group、superuser | `$RUN restore_access_snapshot /ops/<snapshot>.json`（先看差异，再加 `--apply --yes`；可以用 `--user` 限定账号） |
| Expense 回填 | `$RUN backfill_expense_owner --rollback /ops/<csv>`（先看差异，再加 `--apply --yes`） |
| 反向 migration（仅在必须删除新表/新列时） | `migrate accounting 0014`、`migrate employees 0001`、`migrate authentication zero`、`migrate audit zero`（会丢失 owner、关联、审计数据，须先备份并批准） |
| 李无法登录 | `$RUN changepassword zbry6947@gmail.com`、`$RUN axes_reset_username zbry6947@gmail.com`、`$RUN protect_account --username zbry6947@gmail.com --apply --yes`、`$RUN restore_access_snapshot /ops/<file> --user zbry6947@gmail.com --apply --yes` |
| 数据整体恢复 | 用第 3 步的 SQL 和媒体卷备份恢复（须批准） |

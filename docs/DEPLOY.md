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

上传文件使用共享卷 `media_volume`，前端 Nginx 直接提供 `/media/` 和 `/sun/media/`。

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

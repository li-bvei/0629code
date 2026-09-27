# 2026-09-28 P0 访问控制本地实现（最终 CHANGELOG）

分支：`codex/p0-access-control`（基于 `main` = `de95411`，未推送、未部署）
依据：`docs/SYSTEM_ARCHITECTURE.md`、`docs/P0_ACCESS_CONTROL_DESIGN.md`（实现差异见其 §14）
本阶段唯一的 CHANGELOG；2026-09-26/27 的需求整理记录保留为历史。

## 范围

实现了 P0-A4/A6/A7/A8 的全部本地代码：
- User–Employee 一对一、ProtectedAccount、BusinessAccessPolicy、显式业务 Group/Permission；
- AuditLog；
- Expense 所有者隔离；
- Case/Customer/Company/Document 的数据范围和敏感字段边界；
- 受保护下载；
- 生产禁用开发端点；
- 仓库内 nginx/compose 调整；
- 管理命令与权限矩阵测试。

**没有**连接生产库，没有执行 D1～D12，没有修改任何真实账号，没有部署。

## 主要变更

- **后端基础**：
  - 新增 `apps/audit`；
  - `apps/authentication` 下新增 `access_policy.py`、`access_rules.py`、`drf.py`、`roles.py`、`snapshot.py`、`admin_guard.py`、`models.py`；
  - `Employee.user`；
  - `Expense.owner/created_by/updated_by`。
- **业务接入**：所有业务 ViewSet 和函数视图都声明 `access_resource` 并经过策略；Dashboard、受付、期限、会计首页、余额、图表、Excel、复制到项目都做了范围限定。
- **账号管理**：要求 superuser 且显式持有 `manage_users`；受保护账号不能被停用、降级、改名或重置密码；Admin 两阶段启用（`PROTECTED_ADMIN_ENFORCEMENT`）；`me` 只返回显式业务权限。
- **文件**：
  - 新增 `/api/documents/{id}/download|preview/`；
  - 删除 Django 公开的 `/media/` 路由；
  - nginx 公开 `/media/` 返回 404，新增 `internal` 的 `/_protected_media/`；
  - media 卷改挂到 Web 根目录之外。
- **开发端点**：`ENABLE_DEV_TOOLS=False` 时不注册；保留的诊断功能需要 superuser + `use_diagnostics`，并写审计。
- **管理命令**（都默认只做预演，需显式 `--apply` 才写入）：`setup_access_roles`、`assign_business_roles`、`link_user_employee`、`protect_account`、`rename_protected_account`、`export_access_snapshot`、`restore_access_snapshot`、`backfill_expense_owner`、`check_access_config`、`inventory_media_references`（只读）。
- **前端**：
  - 按业务权限显示菜单并控制页面跳转（仅作显示用）；
  - 余额只在有权限时显示，全员视图显示所有者列；
  - 书类一览增加下载和预览；
  - 顾客的最小信息行和基础级别页面正常显示；
  - 受付页的担当者提示；
  - seed 按钮只在开发环境显示；
  - 账号管理只在有权限时显示。
- **修复的现有问题**：
  - 公司职员接口会明文返回 My Number；
  - 顾客列表的分页排序不稳定。

## Migration

`employees/0002_employee_user`、`authentication/0001_initial`、`audit/0001_initial`、`accounting/0015_expense_owner_and_business_permissions`、`cases/0017_alter_case_options`、`customers/0009_alter_customer_options`、`documents/0003_alter_document_options`。全部是加法 migration，不写入业务数据，旧代码可以在新表结构上运行。

## 验证

- `python manage.py test`：170 项全部通过（原有 97 项 + 新增 73 项）。
- `makemigrations --check`：无差异；`check`：0 issues；`npm run build`：通过；`git diff --check`：通过。
- 预览库冒烟：结果与权限矩阵一致。
- **未完成**：浏览器实测（预览进程没有读取 venv 的权限）；`nginx -t`（本机 Docker 未运行）。

## 部署与回滚

见 `docs/DEPLOY.md`「2026-09 P0 访问控制上线」。backend 新代码启动后、执行 D6/D7 之前，所有人的业务 API 都会返回 403，因此 D1～D7 必须在同一个维护时间窗内完成。

## 已知待办

- 待用户确认：未立案顾客 `basic` 级别的字段清单（Q7）；生产保留的诊断功能清单（Q10）。
- 现有问题：`seed_demo_data` 引用了不存在的 `Task.STATUS_TODO`，运行时失败（与 P0 无关，未修）。
- 家族关联到任意既有顾客、以及新建案件时关联任意既有顾客，会让担当者获得该顾客的完整访问权限。这是"按担当推导范围"模型本身的结果，已记为残余风险，P1 可以考虑增加审计或限制。

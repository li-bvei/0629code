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

## 稳定化修正（同日）

- **修复权限绕过**：原来可以通过提交任意既有 Customer/Company ID，让对象进入自己的担当范围。现在以下入口统一执行受控关联规则（`PartyRule.check_link`）：Case 新建和更新、受付（`existing_customer_id`、`existing_company_id`、家族 `customer`、代表者）、FamilyMember 的 `family_customer`、CompanyStaff 的 `customer`、Company 的代表者。
  - 对象有其他担当者（含未分配）的进行中案件：返回 403。只有持有 `customers.customer_link_all` / `company_link_all`（`system_admin`，李）的用户可以关联，写 `cross_scope_link`；被拒绝写 `cross_scope_link_denied`；关联无担当对象写 `party_link_unassigned`。
  - 后端检查提交的真实 ID，不依赖前端候选列表。
- **未立案顾客**：`basic` 级别最终确定为姓名、フリガナ、生年月日、国籍、登记时间、遮罩后的电话和邮箱。
- **生产诊断**：只保留 `/api/health/`、`/api/readiness/`；`tax-renewal-pdf-diagnostics` 也改为只在开发环境注册。前端的「PDF字段诊断」按钮只在开发环境显示。
- **部署顺序**：`DEPLOY.md` 改为 21 步（D1 在旧系统上只读 → 维护模式 → 备份 → `migrate --plan` → `migrate` → D2～D7 → 启动新后端 → 验证 → D8 → 准备前端 → D9 → `nginx -t` → D10 → 验证下载 → D5 → D11 → D12 → 退出维护模式），任何一步失败都停止。
- **新增测试**：13 项关联绕过测试，health/readiness 测试，basic 级别字段测试。
- **无担当进行中案件**：未分配（`responsible_employee` 为空）的进行中案件显式算作「其他担当」，关联其顾客/公司同样返回 403（提示文案注明「未割当」），只有 link_all 可以关联；已结案、inactive/archived 的案件不构成阻断。新增 6 项测试，全量测试 189 项通过。

## Migration

`employees/0002_employee_user`、`authentication/0001_initial`、`audit/0001_initial`、`accounting/0015_expense_owner_and_business_permissions`、`cases/0017_alter_case_options`、`customers/0009_alter_customer_options`、`customers/0010_party_link_permissions`、`documents/0003_alter_document_options`。全部是加法 migration，不写入业务数据，旧代码可以在新表结构上运行。

## 验证

- `python manage.py test`：189 项全部通过（原有 97 项 + 访问控制 92 项）。
- `makemigrations --check`：无差异；`check`：0 issues；`npm run build`：通过；`git diff --check`：通过。
- 预览库冒烟：结果与权限矩阵一致。
- **未完成，属于部署前阻断项**：浏览器实测（预览进程没有读取 venv 的权限）；`nginx -t`（本机 Docker 未运行，在上线第 15 步执行）。

## 部署与回滚

见 `docs/DEPLOY.md`「2026-09 P0 访问控制上线」。backend 新代码启动后、执行 D6/D7 之前，所有人的业务 API 都会返回 403，因此 D1～D7 必须在同一个维护时间窗内完成。

## 已知待办

- Q7（未立案顾客字段）和 Q10（生产诊断）已在稳定化修正中确定并实现。
- 现有问题：`seed_demo_data` 引用了不存在的 `Task.STATUS_TODO`，运行时失败（与 P0 无关，未修）。
- 关联**无担当**（没有进行中案件）的既有顾客/公司仍然允许，关联后即进入本人范围（写 `party_link_unassigned` 审计）。这是本次确认的规则；P1 增加 `Customer.created_by` 后可以进一步收紧。

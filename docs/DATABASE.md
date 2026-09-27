# DATABASE

## 1. Database Overview

数据库使用 MySQL。

数据模型以 Case 为中心设计。数据库以 Case 为核心设计，业务数据优先围绕 Case 组织。

表结构保持清晰，不设计多租户结构，也不给普通业务表滥加审计字段。

2026-09-26/27 已确认、2026-09-28 本地已实现（生产未部署）：User–Employee 一对一关系、Expense 的 `owner`/`created_by`/`updated_by`、模块动作权限 + 数据范围（BusinessAccessPolicy）、独立 AuditLog 表、ProtectedAccount。详见 §11。

## 2. Naming Rules

命名规则：

- 表名使用小写蛇形命名
- 字段名使用小写蛇形命名
- 主键统一使用 `id`
- 外键使用 `{model}_id`
- 时间字段使用 `_at` 结尾
- 布尔字段使用 `is_` 或 `has_` 开头

示例：

- `customers`
- `companies`
- `cases`
- `case_tasks`
- `case_documents`

## 3. Common Fields

核心业务表默认包含：

- `id`
- `created_at`
- `updated_at`

需要软删除时再增加：

- `deleted_at`

MVP 阶段不默认给所有表添加软删除。只有明确需要恢复或隐藏历史数据的表才使用。

## 4. Core Entities

核心实体：

- `customers`: 客户
- `companies`: 公司
- `cases`: 案件
`cases` 是主表之一，应包含案件号、案件类型、状态、客户、公司、受理日期等基础字段。

- `employees`：业务担当者

`employees.Employee` 用于案件负责人（`cases.responsible_employee`）等业务关联；它与 Django `auth.User` 通过 `employees.user_id`（OneToOne，可空）关联（2026-09-28 本地已实现，生产未部署；关联用 `link_user_employee` 命令执行）。登录账号由前端 `/settings` 的账号管理功能维护。



客户和公司可以独立存在，但业务操作应尽量从案件进入。

## 5. Relationships

基础关系：

- 一个 Customer 可以关联多个 Case
- 一个 Company 可以关联多个 Case
- 一个 Case 可以关联一个 Customer
- 一个 Case 可以关联一个 Company
- 一个 Case 可以拥有多个 CaseChecklistItem（当前前端实际使用的步骤 / 必要资料）
- 一个 Case 可以拥有多个 Task（历史模型，后端保留但前端已下线）
- 一个 Case 可以拥有多个 Reminder
- 一个 Case 可以拥有多个 Timeline
- 一个 Case 可以拥有多个 Document
- 一个 Employee 可以负责多个 Case

以后负责人、创建人都会用到。

MVP 阶段暂不设计复杂多对多参与人结构。如后续案件需要多个客户或多个公司，再单独扩展。

## 6. Workflow Tables

工作流相关表：

- `case_tasks`: 案件任务
- `case_reminders`: 案件提醒
- `case_timelines`: 案件时间线

`case_tasks` 是历史独立待办模型，后端保留；当前前端用 CaseChecklistItem 管理案件步骤和必要资料，不再提供 Task 新建、编辑入口。

`case_reminders` 用于记录重要日期和提醒事项。

`case_timelines` 用于记录案件进展，既可给内部查看，也可选择性展示给客户 Portal。Timeline 为系统操作记录，不允许修改，只允许追加。

## 7. Resource Tables

资源相关表：

- `case_documents`: 案件文件
- `forms`: 客户填写的表单记录

文件应关联 Case，并记录文件来源：

- 内部上传
- 客户上传
- 系统生成

当前 `case_documents` 已有字段：`case_id`（必填，`on_delete=CASCADE`）、`title`、`file`（`upload_to='case_documents/'`）、`file_name`、`file_path`、`file_size`、`content_type`、`source`、`is_visible_to_client`、`created_at`、`updated_at`。

第一阶段（P2-C9，计划中）只补齐：文件分类、关联 Checklist、原始文件名/存储名/MIME/大小/哈希、上传人与上传时间、归档状态，以及归档写入 AuditLog（上传、替换、删除、下载、预览的 AuditLog 已在 P0 本地实现）。**第一阶段不建设完整版本管理**（版本树、版本比较、版本恢复以后再评估）；“替换”只需保留审计记录。

> 安全风险（2026-09-27 发现，P0-A8）：生产 nginx 把 `/media/`、`/sun/media/` 直接公开，`case_documents/` 下的文件可以绕过登录访问。2026-09-28 本地已修复：Django 受保护接口 `/api/documents/{id}/download|preview/` + nginx `internal` + X-Accel-Redirect，media 卷改挂到 Web 根目录之外；**生产尚未部署**（D10）。

## 8. Portal

Portal 访问基于：

- 案件号
- 客户生日

Portal 不使用客户账号。

Portal 相关数据应支持：

- 判断案件是否允许 Portal 访问
- 判断时间线是否对客户可见
- 判断文件是否允许客户下载
- 记录客户上传的资料

生日属于敏感信息，后端接口不得返回不必要的生日字段。

## 9. Future Extensions

未来可按需要扩展：

- 多客户或多公司参与同一案件
- 完整文件版本管理（版本树、比较、恢复）
- 部门级数据范围等更细的权限
- 通知发送记录
- 外部系统同步记录（Google Drive 本阶段明确不做）

这些能力不进入当前计划，除非有明确业务需求。操作日志（AuditLog）和模块权限/数据范围已从本列表移出，属于 2026-09-26 已确认的 P0 要求，见 §11。

## 10. 近期字段变更（2026-08）

以下字段/关系为近期新增，详细业务背景见 `AI_CONTEXT.md` 对应小节，此处只记录数据库层面的事实：

- `cases.residence_card_received_at`（可选日期）：在留カード受取日，不是新的 `status` 枚举值，只是一个普通日期字段，跟"許可"状态一起使用。
- `case_checklist_templates.case_type_master_id` / `application_category_id`（均可选外键，`on_delete=SET_NULL`）：模板与「案件種別＋申請区分」的对应关系，用于新建案件时自动套用材料清单。
- `companies.establishment_symbol` / `establishment_number`（均为可选自由文本）：厚生年金/社会保険相关的「事業所整理記号」「事業所番号」，公司级编号，不是每个案件各自的。
- `tax_renewal_voucher_records.case_id`（可选外键，指向 `cases`，`on_delete=SET_NULL`）：税务证明记录关联到具体案件，用于自动带出该案件的顧客/会社/担当者，减少重复选择。**这不是"一个案件对应一份税务证明"的强约束**——`case` 可以为空，一个案件下也可以有多份不同用途的税务证明记录。
- `customers.family_members`（`FamilyMember`）：配偶/兄弟姐妹（对称关系）新增了服务层的自动反向链接行为——给 A 添加"配偶 B"且 B 已是独立顧客时，会自动在 B 名下也生成一条"配偶 A"的 `FamilyMember`，避免两边各录一次。这不是数据库约束层面的变化（没有新增表/字段），是 `backend/apps/customers/utils.py` 里的应用层同步逻辑，在 `FamilyMemberSerializer` 保存后触发。

## 11. 2026-09 横切字段/表与 P0 访问控制结构

### 11.1 已实现（有 migration 和测试）

- `case_timelines` 新增字段（`apps/timelines/migrations/0003_...`）：
  - `event_type`（CharField，可空字符串）：自动事件类型，如状态变更、Checklist 完了；手动记录可为空。
  - `actor_id`（FK → `auth.User`，`on_delete=SET_NULL`，可空）：记录者/操作者。
  - `metadata`（JSONField，默认 `{}`）：事件附加信息（变更前后状态等）。
  - Timeline 仍是业务进展记录，只追加不修改；它**不是** AuditLog。
- `reception_idempotency_records`（`api.ReceptionIdempotencyRecord`，`api/migrations/0001_initial.py`）：
  - `request_id`（unique）、`response`（JSONField，可空；`NULL` 表示处理中）、`created_at`、`updated_at`。
  - 只服务于 `POST /api/receptions/` 的重复提交保护，不复用于其它语义。
- 会计模块中已有 `created_by`（FK → `auth.User`）的表：`AccountingVoucher`、`VisaReturnApplication`、`SeifuNoticePdfRecord`、`TaxRenewalVoucherRecord`。`accounting_expenses`（Expense）的 owner/created_by/updated_by 见 §11.2（P0 本地已实现）。
- `accounting_expenses.category` 是自由文本 CharField，不是 `ExpenseCategory` 外键。P2-C7 第一阶段保持自由文本，不强制改外键，不批量清洗历史数据。

### 11.2 P0 访问控制结构（2026-09-28 本地已实现；生产尚未部署）

> 以下表、字段、权限已在分支 `codex/p0-access-control` 中实现，有 migration 和测试；**生产数据库尚未应用**。表中数据的写入（关联账号、注册受保护账号、分配 Group、回填 Expense）属于待批准的数据操作（`docs/P0_ACCESS_CONTROL_DESIGN.md` §12 D1～D12），通过管理命令执行，不写进 migration。

| 对象 | 结构 | migration | 说明 |
|---|---|---|---|
| `employees.user_id`（Employee.user） | OneToOne → `auth.User`，`null=True`，`SET_NULL`，`related_name='employee'` | `employees/0002_employee_user` | 放在 Employee 一侧，不改内置 User；由 `link_user_employee` 按 username 关联 |
| `authentication_protected_accounts`（ProtectedAccount） | `user_id` OneToOne（`PROTECT`）、`reason`、`created_at`；权限 `authentication.manage_users`、`authentication.use_diagnostics` 也挂在此模型上 | `authentication/0001_initial` | 用外键关联账号，不在代码中固定 ID；只能用 `protect_account` 增删；Admin 两阶段启用由 `PROTECTED_ADMIN_ENFORCEMENT` 控制 |
| `accounting_expenses.owner_id`（`PROTECT`）/`created_by_id`/`updated_by_id`（`SET_NULL`） | 均为 FK → `auth.User`，`null=True` | `accounting/0015_expense_owner_and_business_permissions` | 新建记录时由后端强制写入；历史数据用 `backfill_expense_owner` 回填（dry-run、expect-count、CSV、可回滚）；NOT NULL 以后另行评估 |
| `audit_logs`（AuditLog，`apps/audit`） | 用户、username 快照、Employee、IP、User-Agent、request_id、module、action、object_type/id/repr、result、changes、reason、via_permission、extra | `audit/0001_initial` | 只能经 `apps.audit.services.record()` 写入；没有 API；Admin 只读，仅受保护账号且有 `audit.view_auditlog` 时可见 |
| 自定义业务权限（Meta.permissions） | accounting：`use_expense`、`expense_view_all`、`expense_change_all`、`expense_export_all`、`manage_expense_category`、`use_income`、`use_vehicle`、`use_project`、`use_voucher`、`use_visa`、`use_tax_renewal`、`use_seifu`；cases：`use_cases`、`case_view_all`、`case_change_all`、`manage_case_settings`；customers：`customer_view_all`、`view_sensitive_identity`；documents：`document_view_all`、`document_download_all` | `accounting/0015`、`cases/0017`、`customers/0009`、`documents/0003` | 数据范围用权限名表达，不新建权限表或范围表 |

#### Group 与初期成员（`setup_access_roles` 创建，`assign_business_roles` 分配；生产分配须经 D6/D7 批准）

| Group | 初期成员 | 权限 |
|---|---|---|
| `system_admin` | 李 | `manage_users`、`use_diagnostics`、`audit.view_auditlog`、`case_change_all`、`manage_case_settings`、`view_sensitive_identity`、`document_download_all` |
| `accounting_admin` | 李 | `use_expense`、`expense_view_all`、`expense_change_all`、`expense_export_all`、`manage_expense_category`，以及全部会计、帐票、Visa、税务、清風模块的 `use_*` |
| `business_admin` | 李、焦、周 | `use_cases`、`case_view_all`、`customer_view_all`（不含敏感字段）、`document_view_all`（只看元数据） |
| `expense_viewer` | 焦、周 | `use_expense`、`expense_view_all` |
| `staff` | 以后的普通员工 | `use_cases`、`use_expense` |

- 业务判定由 `apps/authentication/access_policy.py`（BusinessAccessPolicy）和 `access_rules.py` 执行：只读取 Group 或直接授权的 Permission 行，**不读取 `is_superuser`**。
- Case 按 `responsible_employee` 判定 assigned；子资源和 Document 继承 Case；Customer/Company 按"是否有本人担当的关联 Case"判定，并分为 full、masked、basic、minimal 四个表现级别。
- Income、VehicleUsage、AccountingProject 等 P0 不加 owner，只做模块级权限。

#### 当前实际状态

- 本地开发库 `gyoseishoshi_erp` **未应用**上述 migration（为了不改动现有数据）。验证使用 Django 测试库，以及独立的预览库 `gyoseishoshi_erp_p0_preview`。
- 本地开发库账号现状（2026-09-27 只读核对）：4 个 User 全部 `is_superuser=True`、`is_staff=True`，没有 Group；3 个 Employee 与 User 无关联。
- 生产库尚未核对（D1）。

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
| 自定义业务权限（Meta.permissions） | accounting：`use_expense`、`expense_view_all`、`expense_change_all`、`expense_export_all`、`manage_expense_category`、`use_income`、`use_vehicle`、`use_project`、`use_voucher`、`use_estimate`、`use_contract`（P2-C11，`accounting/0018`）、`use_visa`、`use_tax_renewal`、`use_seifu`；cases：`use_cases`、`case_view_all`、`case_change_all`、`manage_case_settings`；customers：`customer_view_all`、`view_sensitive_identity`；documents：`document_view_all`、`document_download_all` | `accounting/0015`、`cases/0017`、`customers/0009`、`documents/0003` | 数据范围用权限名表达，不新建权限表或范围表 |

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


### 11.3 P1 案件工作台字段（2026-09-28 本地已实现，分支 `codex/p1-case-workspace`；生产未部署）

| 对象 | 字段 | migration | 说明 |
|---|---|---|---|
| `cases` | `work_status`（`active`/`waiting`，默认 `active`）、`waiting_reason`（`customer_documents`/`immigration_review`/`third_party`/`payment`/`other`）、`waiting_note`、`waiting_since`、`waiting_until` | `cases/0018_case_work_status_next_action` | 作业状态，**不改变 13 个进捗 `status`**；案件进入完了/取下/不许可时自动解除待机 |
| `cases` | `next_action_assignee_id`（FK Employee，`SET_NULL`）、`next_action_blocked_reason`、`next_action_completed_at`、`next_action_completed_by_id`（FK User，`SET_NULL`） | 同上 | 与既有的 `next_action`、`next_action_due_at` 一起构成 Next Action；负责人必须能查看该案件 |
| `case_checklist_items` | `received_at`（DateField）、`document_id`（FK Document，`SET_NULL`，只能是同一案件的文件） | `cases/0019_checklist_item_document_link` | 资料受领；文件仍然只能经受保护下载访问 |

- 上述字段在通用序列化器中为只读，只能通过 `apps/cases/work_service.py` 修改（事务 + Timeline + AuditLog）。
- 均为加法 migration，不写入数据；旧代码可以在新表结构上运行。
- Timeline 新增事件常量：`document_received`、`accounting_linked`（`event_type` 是自由 CharField，不涉及 migration）。


### 11.4 P2 会计关联（2026-09-28 本地已实现，分支 `codex/p2-accounting`；生产未部署）

| 对象 | 字段 | migration | 说明 |
|---|---|---|---|
| `accounting_expenses`、`accounting_income_sources` | `customer_id`、`company_id`、`case_id`（均为可空 FK，`SET_NULL`） | `accounting/0016_income_expense_party_links` | 关联案件需要对该案件有「变更」权限，顾客/公司需要在本人可见范围内；关联或解除关联时，只在案件 Timeline 记录日期和分类（不记金额，不记所有者） |

- `is_reimbursed`（精算済み）是历史兼容字段：当前 UI 已废止（新增、编辑、列表、筛选、仪表盘统计均不再显示，前端不再发送），不构成报销流程；模型字段、数据库列和历史数据保持不变，后端 API 暂时保留兼容（省略时新建为默认 False，更新时保留原值）。
- `Expense.category` 仍是自由文本；分类建议（`category_suggestions.py`）只读取本人的历史记录，不写入数据。
- Visa 分支从本分支的最新提交创建，Visa 的 migration 编号接在 `0016` 之后。


### 11.5 P2 Visa 一括导入（2026-09-28 本地已实现，分支 `codex/p2-visa-import`；生产未部署）

| 对象 | 字段 | migration | 说明 |
|---|---|---|---|
| `accounting_visa_import_batches`（VisaImportBatch） | 文件名、SHA-256、工作表、字符编码、列映射、创建方式、状态、行数/成功/错误/跳过件数、`results`（逐行结果）、已处理 `request_id` | `accounting/0017_visa_import_batch`（接在会计分支 0016 之后） | 不保存行数据本身；只保存错误行的字段、原值和错误原因（供修正用） |
| `accounting_visa_return_applications` | `import_batch_id`（可空 FK，`SET_NULL`）、`import_row_number` | 同上 | 标记由哪个导入批次、第几行创建 |

### 11.6 P2 文件管理（2026-09-28 本地已实现，分支 `codex/p2-documents`；生产未部署）

| 对象 | 字段 | migration | 说明 |
|---|---|---|---|
| `case_documents` | `category`（本人确认/在留/申请/证明/公司/合同请求/联络/其他）、`sha256`、`uploaded_by_id`、`is_archived`、`archived_at`、`archived_by_id`、`archive_reason`；`file` 的保存名改为 `case_documents/YYYY/MM/<uuid>.<扩展名>` | `documents/0004_document_metadata_archive_replacements` | 原始文件名存在 `file_name`；MIME 按扩展名推断；既有文件的保存路径不变 |
| `case_document_replacements`（DocumentReplacement） | 替换前的保存名、原始文件名、大小、SHA-256、MIME、原因、执行人、时间 | 同上 | 只保留替换历史，不是完整版本管理；替换前的文件不删除 |

- Checklist 关联沿用 P1 的 `case_checklist_items.document_id`；上传时可以指定同一案件的必要资料。
- 已在集成分支 `codex/p2-integration` 与会计、Visa 分支合并（文档冲突已手动合并；migration 分属 `accounting/0016～0017` 与 `documents/0004`，互不依赖）。

### 11.7 P2-C11 帐票（2026-09-29 本地已实现，分支 `codex/p2-c11-vouchers`；生产未部署）

| 对象 | 字段 | migration | 说明 |
|---|---|---|---|
| `accounting_estimates`（Estimate，見積書） | `estimate_number`（EST-YYYYMMDD-NNNN，唯一）、`status`（draft/submitted/accepted/declined/cancelled）、`valid_until`，以及共享抽象列 | `accounting/0018_business_documents_c11` | 権限 `accounting.use_estimate` |
| `accounting_contracts`（Contract，契約書） | `contract_number`（CON-…）、`status`（draft/sent/signed/terminated/cancelled）、`start_date`、`end_date`、`payment_terms`、`body`、`signed_date`、`source_estimate_id`（SET_NULL），以及共享抽象列 | 同上 | 権限 `accounting.use_contract` |
| 共享抽象列（見積書・契約書） | 宛先（名称/敬称/邮编/住所）、`title`、`line_items`、`amount`/`tax_amount`/`total_amount`、発行者、`issued_snapshot`、`status_changed_at`、`case_id`/`customer_id`/`company_id`（SET_NULL）、`created_by_id`/`updated_by_id` | 同上 | 只共享列，不共享状态 |
| `accounting_vouchers`（請求書・領収書） | `invoice_status`（''/draft/issued/sent/paid/cancelled）、`receipt_status`（''/draft/issued/voided）、`paid_date`、`status_changed_at`、`issued_snapshot`、`source_estimate_id`、`source_contract_id`、`source_invoice_id`（self）、`case_id`/`customer_id`/`company_id`、`updated_by_id` | 同上 | 两种帐票各用自己的状态列；**既有行状态为空（旧数据），不批量回填** |
| `accounting_document_number_sequences` | `key`（前缀-日期，唯一）、`last_number` | 同上 | 加锁取号，且大于同前缀已有最大号；旧 INV/REC 编号格式不变 |

- 离开下書き时写入 `issued_snapshot`，之后宛先・金额等锁定（只可改备注和关联案件），不可删除。
- 状态迁移、创建、更新、删除、PDF 下载写 AuditLog（`module='voucher'`）。

### 11.8 P3 不动产（2026-10-01 协同台账修订；生产未部署）

| 对象 | 主要字段 | migration | 说明 |
|---|---|---|---|
| `real_estate_transactions` | `transaction_number`（RE-YYYYMM-NNNN）、`transaction_type`、`stage`、`party_name`＋`customer_id`、物件、`management_company_name`＋`management_company_id`、`responsible_name`（自由文本）、业务金额、支付/振込状态、归档/恢复元数据、来源文件哈希/工作表/行号/原值、`created_by`/`updated_by` | `real_estate/0001_initial`＋`0004_collaborative_ledger` | 协同台账；担当不关联 Employee。入口、查看、新建、编辑、归档、恢复、导出、台账管理/更正/年度关闭、利润分配、导入均为明确权限 |
| `real_estate_number_sequences` | `key`（RE-YYYYMM）、`last_number` | 同上 | 加锁取号 |
| `real_estate_transaction_parties` | `role`（贷主/借主/卖主/买主/代理人/媒介业者/共同宅建业者）、姓名、住所、免许番号、`customer_id`/`company_id` | 同上 | 台账锁定后不可增删改 |
| `real_estate_legal_ledgers` | 1:1 交易（PROTECT）；取引态样、类型、所在地/名称/房间/面积/建物概要、赁料/价格、报酬、广告费、手续费、特约、取引日、`fiscal_year`、`fiscal_year_closed_at`、`retention_years`（默认 5）、`retention_until`、`legal_hold`/理由、`is_locked`/`locked_at`/`locked_by`/`locked_snapshot`、`version` | 同上 | 无删除 API；到期只标记复核 |
| `real_estate_legal_ledger_corrections` | `ledger_id`（PROTECT）、`version`、`changes`（旧→新）、`reason`、`corrected_by`、时间 | 同上 | 更正历史 |
| `real_estate_files` | `transaction_id`、`kind`、`title`、`file`（`real_estate_files/YYYY/MM/<uuid>`）、原文件名/大小/MIME/SHA-256、`document_id`（参照案件书类）、`uploaded_by` | 同上 | 复用 Document 上传检查与受保护下载 |
| `real_estate_accounting_links` | `transaction_id`、`income_source_id`、`voucher_id`、备注 | 同上 | 只引用，不复制会计数据 |
| `real_estate_profit_distributions` | 分配对象（名称/担当）、`method`（fixed/ratio）、`base_amount`、`ratio_percent`、`fixed_amount`、`amount`（自动计算）、`status`（draft/settled）、`settled_at`、备注 | 同上 | 不进入法定台账 |
| `real_estate_import_runs` | 文件名、SHA-256、工作表、`summary`、`report`（行号・原值・规范化・错误・候选） | `real_estate/0002_import_runs` | dry-run 履历；隔离 QA 库也保存验收导入报告，生产禁用 |

| `real_estate_transactions`（权限） | 新增 `bulk_change_real_estate` | `real_estate/0005_bulk_change_permission` | 2026-10-02。只有 Permission 行，无列变更；批量变更不新增表，履历写 AuditLog（`transaction_updated`＋`extra.bulk`、`transaction_bulk_updated`） |

### 11.8.1 支出类别建议规则（2026-10-02 本地已实现；生产未部署）

| 对象 | 主要字段 | migration | 说明 |
|---|---|---|---|
| `accounting_expense_category_rules`（ExpenseCategorySuggestionRule） | `pattern`、`pattern_key`（规范化匹配键）、`match_field`（place/expense_target/note）、`expense_category_id`（CASCADE）、`priority`、`is_active`、`source`（seed/manual/user_confirmed）、`owner_id`（空＝全事务所；有值＝仅本人，CASCADE）、`created_by`/`updated_by`、时间戳；唯一约束 `owner`＋`match_field`＋`pattern_key`（全事务所规则的重复由应用层检查） | `accounting/0020_expense_category_rules` | 同一 migration 写入 3 条初始规则（駐車場・停车场・parking → 既有类别「停车费」）。这是设置数据，不改写任何支出记录 |
| `accounting_expense_categories` | 结构不变 | — | 保存支出时把确认使用的类别名沉淀为主档（已有同名或仅表记不同则复用；停用的不重新启用）。`accounting_expenses.category` 仍是自由文本，不改外键 |

### 11.9 P2 平台能力收尾（2026-09-29 本地已实现，分支 `codex/p2-platform-completion`；生产未部署）

| 对象 | 字段 | migration | 说明 |
|---|---|---|---|
| `office_settings`（OfficeSettings，单例 pk=1） | `fiscal_year_end_month`（1～12）、`updated_by_id`、`updated_at` | `office/0001_office_settings` | 不插入初始行；无行时用环境变量 `OFFICE_FISCAL_YEAR_END_MONTH`（兼容 `REAL_ESTATE_FISCAL_YEAR_END_MONTH`）→ 默认 3；权限 `office.manage_office_settings` |
| `real_estate_legal_ledgers` | `fiscal_year_end_month`（决算月快照，可空） | `real_estate/0003_ledger_fiscal_month_snapshot` | 创建・年度关闭时保存；关闭后冻结；既有行为空，不回填 |
| `cases` | `archived_by_id`、`archive_reason`、`restored_at`、`restored_by_id` | `cases/0020_case_archive_metadata` | `archived_at` 沿用；复原时清空 `archived_*`，旧值留在 Timeline/AuditLog；既有行不回填 |

### 11.10 发布硬化：旧代码兼容的数据库默认值（2026-09-30 本地已实现，分支 `codex/release-hardening`；生产未部署）

P1～P3 追加的 NOT NULL 列中，以下 9 列原本没有数据库级默认值（Django 4.2 添加列后会去掉默认值），P0 之前的旧代码 INSERT 时会报 MySQL 1364。follow-up migration 只设置数据库默认值，不改列类型、不写数据：

| 表.列 | 数据库默认值 | migration | 选择理由 |
|---|---|---|---|
| `cases.work_status` | `'active'` | `cases/0021_db_defaults_for_rollback_compat` | 新代码按值筛选（对応中/待機中）；NULL 会让旧代码新建的案件从工作台消失，所以用业务默认值 |
| `cases.waiting_reason` | `''` | 同上 | 空＝未待机，与新代码一致 |
| `cases.archive_reason` | `''` | 同上 | 空＝未归档 |
| `case_documents.category` | `'other'` | `documents/0005_db_defaults_for_rollback_compat` | 新代码的「その他」 |
| `case_documents.is_archived` | `0` | 同上 | 默认列表按 `is_archived=False` 筛选，NULL 会让旧代码上传的书类消失 |
| `case_documents.sha256` | `''` | 同上 | 空＝未计算（旧代码上传） |
| `case_documents.archive_reason` | `''` | 同上 | 空＝未归档 |
| `accounting_vouchers.invoice_status` | `''` | `accounting/0019_db_defaults_for_rollback_compat` | 空＝「状態未設定（旧データ）」，正是旧代码创建的含义 |
| `accounting_vouchers.receipt_status` | `''` | 同上 | 同上 |

- 未选择「允许 NULL」：上述列都被新代码按值筛选或判断（`is_archived=False`、`work_status`、帳票状态），改为可空需要在所有查询中特殊处理 NULL，风险更大；数据库默认值与新代码的模型默认值一致，新旧代码读写结果相同。
- 已有表达式默认值（MySQL 8.0.13+ 由 Django 保留）：`cases.waiting_note`・`next_action_blocked_reason`（`''`）、`accounting_vouchers.issued_snapshot`（`{}`）。
- 其余新增列均可空或属于旧代码不写入的新表（P0 的 `owner` 等、各关联 FK、OfficeSettings、不动产、帳票新表）。
- 以后若 `AlterField` 这些列，Django 会去掉默认值；`apps/cases/tests_db_defaults.py` 会失败，需在新 migration 中用 `apps.common.db_defaults` 重新设置。
- 旧代码删除被新表（見積書・契約書・不動産・审计日志等）引用的父记录时会被外键拒绝（`scripts/rollback_compat/inventory.py` 列出全部此类外键）。

### 11.11 2026-10-03 规划中的数据结构（A 与 Visa 生成记录已由 P1 实施，C 已由 P3 实施，B、D 已由 P4 实施，F 已由 P5 单模板实施，G 为 P6 追加）

以下为已确认需求对应的推荐数据方向，用于后续 migration 设计。实际字段名应在实施阶段结合现有命名规范最终确认。P1 已实施部分以本节末尾的「P1 实际结构」为准。

#### A. 单据状态历史（已实施，见「P1 实际结构」）

建议新增不可变的单据状态历史记录，或提供等价的不可变审计存储：

- 单据类型与单据 ID。
- `from_status`、`to_status`。
- 状态变更时的单据快照／快照引用。
- 操作者、变更时间、可选原因。

现有单据状态不再设置终态限制；任意有效状态可互相切换。单据正文仍只在草稿状态修改，切回草稿后产生的新发行版本必须保留可追溯信息。

#### B. 服务价格主数据

建议新增服务价格主表，核心字段包括：

- `category`、`code`、`name`、`description`。
- `default_customer_price`：默认对客报价。
- `outsourcing_floor_price`：委托底价。
- `professional_type`：税理士／行政书士／司法书士／翻译等。
- `tax_category`、`unit`、`is_active`、`sort_order`、`notes`。
- 创建／更新人和时间。

单据明细或案件服务项需要保存名称、价格、税区分、委托底价等快照，不得只保存主表外键。

#### C. 每日计划与工作报告

优先扩展现有任务模型：

- `case` 改为可空，以支持内部任务。
- 新增工作日期、显示顺序、优先级、完成备注、结转来源／结转目标等字段。
- 保留负责人、完成时间和审计信息。

建议新增每日工作报告表：

- 员工／用户、报告日期、状态。
- 生成文本、人工编辑后的最终文本。
- 生成时的任务快照（已完成、未完成／结转、备注、案件摘要）。
- 生成时间、最后编辑人和时间。

工作报告不保存外部发送状态，因为已确认本阶段不自动外发。

**P3 实际结构（2026-10-05 本地已实现；migration `tasks/0003_daily_plan_and_reports`、`tasks/0004_db_defaults_for_rollback_compat`；生产未部署）**

`case_tasks`（Task）的变更：

| 列 | 说明 |
|---|---|
| `case_id` | 改为可空。为空表示不关联案件的内部工作，仅限有 `work_date` 的计划项 |
| `work_date` | 作业日，可空，带索引。有值的是每日计划项，为空的是原有案件任务 |
| `priority` | `high` / `normal` / `low`，默认 `normal`（DB 默认值 `'normal'`） |
| `result_note` | 完成后的结果备注（DB 表达式默认值 `''`） |
| `carried_from_id` | 结转来源（OneToOne → 自身，SET_NULL）。反向关联 `carried_to` 即结转目标 |
| `created_by_id` | 登记人（User，SET_NULL） |
| `status` | 增加 `carried_over`（结转完毕） |
| 索引 | `task_plan_owner_date_idx`（`responsible_employee_id`, `work_date`） |

新表 `daily_work_reports`（DailyWorkReport）：

| 列 | 说明 |
|---|---|
| `employee_id` | 担当者（PROTECT） |
| `report_date` | 报告日期；`employee`＋`report_date` 唯一（每人每天一份） |
| `status` | `draft` / `confirmed` |
| `snapshot` | 生成时的计划项（标题、状态、备注、结果备注、优先级、结转来源和目标日期、关联案件摘要）及汇总 |
| `generated_text` / `final_text` | 生成的正文 / 人工编辑后的正文 |
| `generated_at` / `generated_by_id`、`confirmed_at` / `confirmed_by_id`、`updated_by_id` | 生成、确定、最后编辑的记录 |
| `created_at` / `updated_at` | `updated_at` 用作并发核对的版本 |

**兼容性与回滚**
- 已有任务的 `work_date` 为空，仍按原有案件任务处理，不需要回填。
- 新增列都可空或带 DB 默认值，旧代码不写入新列也能 INSERT，`tasks/tests_daily_plan.py` 中有测试。
- 回滚到旧代码时：
  - 旧代码读取 `case_id` 为空的内部工作时，序列化器的 `case_number` 会被省略，不会报错；但旧的 `CaseChildRule` 只让有全件查看权限的人看到这些记录。
  - 旧代码删除担当者时，如果该担当者已有工作报告，会被外键拒绝（PROTECT）。
- 生产部署时需执行 `migrate`。

#### D. 案件工作流模板

建议将案件类型与状态流程解耦：

- 工作流模板：名称、工作流族、适用案件类型、是否启用、版本。
- 工作流步骤：模板、步骤代码、名称、顺序、默认期限、默认负责人角色。
- 必要资料模板：工作流／步骤、资料名称、是否必需、取得先等默认值。
- 案件保存所使用的模板和版本；历史案件继续保留原状态语义。
- 对复合服务使用案件关联关系（主案件／子案件或关联案件），不要把多个业务结果塞进同一状态字段。

**P4 实际结构（2026-10-06 本地已实现；migration `accounting/0022_service_items_line_costs`、`cases/0022_workflow_templates`、`cases/0023_db_defaults_for_rollback_compat_p4`、`cases/0024_seed_p4_workflows_and_case_types`；生产未部署）**

B 的实现与规划的差别：
- 不设 `code`、`description` 两列。
- 增加 `price_type`（价格是税込还是税抜）和 `first_used_at`（首次被使用的时间，用来禁止物理删除）。
- 快照沿用明细行 JSON，不另建关联表；底价单独存放在内部列。

新表 `accounting_service_items`（ServiceItem）：

| 列 | 说明 |
|---|---|
| `category` / `name` | 分类 / 项目名称（同一分类内名称不重复，由 serializer 检查） |
| `default_price` | 对客标准价，`DECIMAL(12,0)`，可空 |
| `price_type` | `tax_included` / `tax_excluded` |
| `floor_price` | 委托底价，`DECIMAL(12,0)`，可空。只有拥有 `accounting.view_service_floor_price` 的人能看到和修改 |
| `professional_type` | 空（なし）/ `gyousei` / `tax_accountant` / `judicial_scrivener` / `labor_consultant` / `other` |
| `tax_category` / `unit` | `tax_10` / `tax_8` / `non_taxable`，单位 |
| `is_active` / `sort_order` / `note` | 启用 / 排序 / 内部备注（不打印到 PDF） |
| `first_used_at` | 首次被单据或案件使用的时间。不为空时禁止物理删除 |
| `created_by_id` / `updated_by_id` / `created_at` / `updated_at` | `updated_at` 用作版本确认 |
| 权限 | `use_service_item`、`manage_service_item`、`view_service_floor_price` |

新表 `accounting_issued_line_cost_snapshots`（IssuedLineCostSnapshot，只追加）：

| 列 | 说明 |
|---|---|
| `document_kind` / `document_id` / `document_number` | `estimate` / `invoice`，单据 ID 和编号。不设外键，单据删除后仍保留 |
| `version` | 该单据的第几次发行；`document_kind`＋`document_id`＋`version` 唯一 |
| `status_history_id` | 对应的状态履历（仅请求书），SET_NULL |
| `line_costs` | 发行时的 `internal_line_costs` |
| `created_by_id` / `created_at` | 发行人和时间 |

已有表的变更：

| 表 / 列 | 说明 |
|---|---|
| `accounting_vouchers.internal_line_costs`、`accounting_estimates.internal_line_costs` | JSON（MySQL 表达式默认值 `[]`）。每项为 `{line_key, service_item_id, floor_price, professional_type, captured_at}`。API 只返回给底价权限者 |
| `line_items` 中每行的键（无结构变化） | `line_key`（后端生成），选了服务项目的行另有 `service_item_id` 和 `service`。`service` 是选择时的 `{id, category, name, default_price, price_type, tax_category, unit, professional_type, professional_type_display, selected_at}`，不含底价 |
| `cases.service_items` | JSON（表达式默认值 `[]`），受付时服务项目的快照（同上，另有 `quantity`），不含底价 |
| `cases.parent_case_id` | 关联元案件，自身外键，可空，SET_NULL |
| `cases.workflow_template_id` / `workflow_stage_id` | 创建时固定的流程和当前阶段，可空，PROTECT。为空表示原 13 阶段 |
| `case_type_masters.workflow_template_id` | 该种别使用的流程，可空，PROTECT |
| `case_type_masters.requires_application_category` | 是否需要申请区分，默认 True（DB 默认值 1） |

新表 `case_workflow_templates`（WorkflowTemplate）：`code`（唯一）、`name`、`family`（`immigration` / `professional` / `employee_procedure` / `general`）、`description`、`is_active`、`sort_order`。

新表 `case_workflow_stages`（WorkflowStage）：

| 列 | 说明 |
|---|---|
| `template_id` | 所属流程（CASCADE；被案件引用的阶段受案件的 PROTECT 约束） |
| `code` | `template`＋`code` 唯一；创建后不能修改 |
| `name` / `sort_order` / `is_active` | 段阶名 / 排序 / 启用（停用后不能新选，已在该阶段的案件仍显示） |
| `base_status` | 对应的旧 `Case.status`，供一览、仪表盘、期限、完了判断等现有处理使用 |

流程一旦被案件使用（有 `cases.workflow_template_id` 指向它），流程的 `name`、`family`、`is_active` 和它的所有阶段都不能修改（API 层检查）。需要改动时复制为新流程，再把种别重新绑定；已有案件继续使用原流程。

初始数据（`cases/0024`，用户 2026-10-06 确认）：
- 汎用、専門家委託、従業員・社会保険手続三个流程及其阶段，详见 `DEVELOPMENT_PLAN.md` §5.12。
- 新增税理士委託、会社解散、就労ビザ社員入社手続、年金脱退・加入手続四个种别。
- 「その他」绑定汎用流程，并改为不需要申请区分。
- 每个种别建一个空的必要资料模板（`application_category` 为空）。
- 不写入任何服务项目数据。

**兼容性与回滚**
- 已有案件的 `workflow_template` 为空，继续使用 13 阶段，不回填。
- 已有单据没有 `line_key`，下次修改明细时才补上，不回填。
- 旧代码不写入新列也能 INSERT：JSON 列有表达式默认值，布尔列有 DB 默认值，`tests_db_defaults` 会检查。
- `cases/0024` 可以反向执行，`cases` 和 `accounting` 都可以回滚到 0021（已在独立 QA 库验证回滚和再迁移）。
- 回滚会丢失流程绑定、服务项目、底价快照、关联案件和受付快照；明细行 JSON 中的 `line_key` 和 `service` 会留下，旧代码会忽略。

#### E. 文件批量操作

批量上传与 ZIP 下载原则上复用现有逐文件记录，不要求把多个文件合并成一个数据库对象。需要确保每个文件均保存案件、资料分类、原始文件名、存储键、大小、校验值、上传人和时间。ZIP 为即时或短期生成物，不作为永久业务文件写入，除非后续另有归档要求。

P2 已实施（2026-10-04，本地）：**没有结构变化，也没有 migration**。
- 现有的 `case_documents` 已有所需字段：`case_id`、`category`、`file_name`（原始文件名）、`file`（UUID 存储键）、`file_size`、`sha256`、`uploaded_by_id`、`created_at`。批量上传时每个文件仍建一条记录。
- ZIP 只写在临时文件里，不建记录，也不保存文件；只有审计（`document_zip_download` 等）留下记录。
- 必要资料批量更新只修改现有 `case_checklist_items` 的列：`is_completed`、`completed_at`、`completed_by`、`received_at`、`responsible_party`、`acquisition_place`、`note`。

#### F. 清風模板元数据

PSD／背景文件应作为受版本控制的模板资产保存，数据库只记录必要元数据：模板版本、资产校验值、姓名／日期区域配置、所需字体标识、启用状态。生成记录保存模板版本、输入姓名、日期、输出文件和生成结果。不得把“任意文字覆盖项”继续作为主要业务接口。

**P5 单模板实际结构（2026-10-06 本地已实现，含同日独立审查修正；migration `accounting/0023_seifu_notice_fixed_fields`、`accounting/0024_seifu_notice_pdf_generations`；生产未部署）**

记录表 `accounting_seifu_notice_pdf_records` 新增的列（都可空，旧代码仍能 INSERT，旧记录不回填）：

| 列 | 说明 |
|---|---|
| `recipient_name` | 宛名。生成时必填；规则见 `DEVELOPMENT_PLAN.md` §5.13（最长 40 字，列长 100） |
| `permit_number` | 許可番号。NFKC 规范化并大写；3～12 位英数字，可含连字符 |
| `issue_date` | 通知日。2000～2099 年 |
| `template_key` | 当前固定为 `seifu_2year_2027`，是将来扩展多模板的入口 |

新表 `accounting_seifu_notice_pdf_generations`（`SeifuNoticePdfGeneration`，只记录成功的生成）：

| 列 | 说明 |
|---|---|
| `record_id` | 所属记录，SET_NULL。删除记录后生成记录仍保留 |
| `status` | 只有 `success`。失败不建记录，只写审计 |
| `request_id` | 画面每次操作的 ID，唯一，可空。同一 ID 重复提交时返回已有记录 |
| `recipient_name`、`permit_number`、`notice_number`、`issue_date` | 生成时的输入值和派生的编号（快照） |
| `template_key`、`template_version`、`font_version` | 模板标识，以及模板文件和字体文件 SHA-256 的前 16 位 |
| `method` | 生成方式，`server_fixed_layout` |
| `file`、`file_sha256`、`file_size` | 存储中的 PDF（`seifu_notice_pdfs/YYYY/MM/<uuid>.pdf`）及其摘要和大小。确认存储中存在且大小一致后才写入 |
| `created_by_id`、`created_at` | 生成人和生成时间 |

- 旧列 `text_items` 保留，API 只读；修改旧记录时不再清空（审查前的实现会清空，已修正）。
- 课程年数和在籍期間是模板常量，不写进每条记录。
- 模板 PDF 放在受版本控制的 `backend/assets/pdf_templates/seifu/`。MS Mincho 属于需单独授权的运行资产，通过 `SEIFU_MS_MINCHO_FONT_PATH` 配置，开发环境的默认路径在 Git 忽略的 media 目录中。`backend/.dockerignore` 会把 media 排除在镜像之外。
- 回滚：
  - 回滚 `0024` 会删除生成记录表，已生成的 PDF 文件留在存储中，需要另行清理；
  - 回滚 `0023` 只删除上述四列，旧的 `title/status/text_items/note` 数据保留；
  - 回滚后旧代码会恢复任意文字工具，正式回滚时应同时限制旧 URL 的访问。

#### P1 实际结构（2026-10-03 本地已实现，migration `accounting/0021_voucher_history_visa_generations`；生产未部署）

**`accounting_voucher_status_history`**（`VoucherStatusHistory`，请求书・领受书状态履历；只追加，API 不提供修改或删除）

| 列 | 说明 |
|---|---|
| `voucher_id` | FK → `accounting_vouchers`，可空，`on_delete=SET_NULL`。单据删除后履历仍保留 |
| `document_kind` | `invoice` / `receipt` |
| `voucher_number` | 变更时的单据编号（单据删除后仍可识别） |
| `from_status` / `to_status` | 变更前后的状态（旧数据的空状态 `''` 按草稿处理） |
| `version` | 到 `issued` 的变更为第 N 版（以前的发行次数 + 1），其他变更为 0 |
| `snapshot` | 变更后的单据内容：编号、日期、收件人、明细（含 `unit`、`note`）、金额、备注、付款信息、两种状态 |
| `reason` | 理由／备注（最长 500） |
| `changed_by_id` / `changed_at` | 操作者（SET_NULL）与时间 |

**`accounting_visa_return_pdf_generations`**（`VisaReturnPdfGeneration`，Visa PDF 生成记录；成功和失败都记录）

| 列 | 说明 |
|---|---|
| `application_id` | FK → Visa 申请（CASCADE） |
| `status` | `success` / `failed` |
| `method` | `form`（表单字段写入）/ `coordinates`（坐标绘制） |
| `template_name` / `template_version` | 使用的 PDF 模板与版本（模板 PDF + 映射／坐标 JSON 的 SHA-256 前 16 位） |
| `guarantor_template_id` / `guarantor_template_version` | 担保人模板（SET_NULL）与选择时的模板 `updated_at` |
| `file` / `file_sha256` / `file_size` | 成功时的文件（`visa_return_pdfs/YYYY/MM/<uuid>.pdf`）及其校验值和大小 |
| `error_code` / `error_message` | 失败的种别与可读说明 |
| `details` | 写入统计，例如 `drawn_fallback`（无法写入表单字段、改为绘制的字段）；`source` 表示生成来源，`single`（generate-pdf）或 `batch_zip`（批量 ZIP） |
| `created_by_id` / `created_at` | 生成者与时间 |

**`accounting_visa_return_applications.guarantor_template_id`**：可空 FK → `VisaGuarantorTemplate`（SET_NULL）。
- `guarantor_snapshot` 在 API 中为只读，只由服务器按该模板生成，并带上 `guarantor_template_id`、`template_name`、`template_version`。
- 取消模板时清空快照；没有模板的旧数据保持原样。
- 手入力的担保人信息保存在 `guarantor_*` 列和 `form_data`，生成 PDF 时优先于快照。

**兼容性**
- 只新增两张表和一个可空列，不改已有列，也不需要数据回填。
- 旧记录的 `guarantor_template` 为 NULL，仍按以前的快照和手入力值生成 PDF。
- 回滚到旧代码时，旧代码不会写入这些表。但旧代码删除带履历的单据或带生成记录的 Visa 申请时，会被外键拒绝（Django 的 SET_NULL／CASCADE 在应用层执行），与 11.10 末条的情况相同。
- 生成记录的 PDF 文件约 20MB／份，保存在 media 卷中，需要关注磁盘空间。

#### G. P6 追加（2026-10-07 本地已实现；生产未部署）

migration：`accounting/0025_service_item_price_status`、`0026_db_defaults_for_rollback_compat_p6`、`0027_seed_provisional_service_items`、`customers/0011_reveal_my_number_permission`、`documents/0006_document_content_label`、`0007_db_defaults_for_rollback_compat_p6`。

`accounting_service_items`（ServiceItem）：

| 列 | 说明 |
|---|---|
| `code` | 基本项目的固定代码（唯一，可空；手动建立的项目为空） |
| `price_status` | `provisional` / `confirmed`，默认 `provisional`（DB 默认值 `'provisional'`） |
| `price_confirmed_at` / `price_confirmed_by_id` | 确定时间和确定人（User，SET_NULL）；回到暂定时清空 |

- 明细快照（`line_items[].service`）和案件快照（`Case.service_items[]`）新增 `price_status`、`code`，保存选择时的状态，之后不会变化。
- `0027` 投入的 8 项和回滚条件见 `DEVELOPMENT_PLAN.md` §5.14。

`case_documents`（Document）：

| 列 | 说明 |
|---|---|
| `content_label` | 资料内容（新登录时必填，最长 60；DB 默认值 `''`） |
| `display_name` | 后端生成的「资料内容-顾客名.原扩展名」，重名时加 ` (ID n)`（DB 默认值 `''`） |

- 原文件名 `file_name` 和保存名（`file`，UUID）不变。旧文件的两列都为空，下载时使用原文件名。

权限：`customers.reveal_my_number`（Customer 的 Meta permissions）。My Number 的列和加密方式没有变化。

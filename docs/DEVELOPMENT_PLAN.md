# SUNRISE 开发计划（当前有效版本）

更新时间：2026-09-28
状态：进行中。与 `docs/AI_HANDOFF.md`、`docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md` 配套使用——本文件回答“接下来按什么顺序实施”，需求文档回答“必须实现什么、边界是什么”，交接文档回答“项目现在是什么状态”。三者冲突时，先核对代码/测试/migration，并报告冲突后同步文档。

---

## 0. 现状确认（2026-09-28）

- 分支 `codex/p0-access-control`（基于 `main` = `de95411`）上已在本地完成 P0-A4/A6/A7/A8 的代码实现，并按切片提交；**未推送、未部署生产，D1～D12 均未执行**。
- 验证：后端 170 项测试全部通过（原有 97 项 + 新增 73 项访问控制测试）；`makemigrations --check` 无差异；`manage.py check` 0 issues；`npm run build` 通过。
- 本地开发库 `gyoseishoshi_erp` 未应用新 migration；验证使用测试库和独立预览库 `gyoseishoshi_erp_p0_preview`。
- 生产执行清单与回滚：`docs/DEPLOY.md`「2026-09 P0 访问控制上线」。

---

## 1. 任务清单与状态

标记说明：✅ 已完成并有测试　🚧 进行中/部分完成　⬜ 未开始

### P0 — 恢复可交付性并建立权限基础（阻断继续扩展新功能）

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| P0-A1 | 修复"既存会社"绑定 | ✅ | 见 §2.1 |
| P0-A2 | 收紧顾客候选匹配 strong 规则 + 电话规范化 | ✅ | 见 §2.2 |
| P0-A3 | 新规受付服务端幂等保护 | ✅ | 见 §2.3 |
| P0-A4 | User–Employee 关系、模块动作权限与数据范围 | ✅（本地） | BusinessAccessPolicy + Group/Permission；Expense/Case/Customer/Company/Document 全路径接入；生产待 D1～D7 |
| P0-A5 | Dashboard 指标口径固化为文档 + 测试 | 🚧 | 口径已在 `AI_HANDOFF.md` §7 写明，缺显式回归测试 |
| P0-A6 | 独立 AuditLog 与敏感操作审计 | ✅（本地） | `apps/audit`；登录、账号、跨人员查看、导出、下载、拒绝、诊断均记录 |
| P0-A7 | 会计及私有记录 owner 归属与历史数据迁移方案 | ✅（本地） | Expense owner 三列 + `backfill_expense_owner`（dry-run/expect-count/CSV/回滚）；生产回填待 D8 |
| P0-A8 | `/media/` 未鉴权公开风险：改为 Django 受保护下载 | ✅（本地） | 受保护 download/preview + nginx internal + X-Accel；media 卷移出 Web 根；生产切换待 D9/D10 |

### P1 — 案件工作台闭环

| # | 任务 | 状态 |
|---|---|---|
| P1-B1 | Case Workspace Action Bar（対応記録/資料受領/タスク/ファイル/入金/待機/完了） | ✅（本地，分支 `codex/p1-case-workspace`） | `components/case/CaseActionBar.vue`；只用 Dialog/Drawer；「タスク」未单独做（历史 Task 模块保持隐藏），用「次の対応」代替 |
| P1-B2 | 统一 Next Action（负责人/期限/状态/完成/snooze/阻塞原因） | ✅（本地） | Case 字段 + `work_service`；snooze 用「改期限」代替，未单独实现 |
| P1-B3 | Waiting 机制（`work_status`、原因、开始日、预计恢复日） | ✅（本地） | Dashboard `waiting` 改为按 work_status 统计 |
| P1-B4 | 今日作业台（我的作业 / 全体，支持直接操作） | ✅（本地） | `/api/workbench/today/`、`/workbench` |
| P1-B5 | Timeline 自动化剩余（文件、入金、支出、PDF、完了、再开） | ✅（本地） | 文件登记/替换、资料受领、Waiting、Next Action、完了/再开、入金记录、税务证明关联/PDF；支出（Expense）无 case 外键，未接入（P2-C1） |
| P1-B6 | Checklist 与资料受领联动 | ✅（本地） | `received_at`、`document`（同一案件）、`receive` action |
| P1-B7 | RemoteSelect 请求竞态 / 错误状态 / 初始值测试 | ✅（本地） | `npm run test:unit`（esbuild + node:test，无新依赖）+ 后端权限范围测试 |

### P2 — 数据与财务闭环

| # | 任务 | 状态 |
|---|---|---|
| P2-C1 | Income/Expense 增加 customer/company/case 可选外键 | ✅（本地，分支 `codex/p2-accounting`） | 关联案件需要该案件的「变更」权限；只指定案件时自动带出顾客/公司 |
| P2-C2 | 从 Case 查看账务、从账务回到 Case | ✅（本地） | `cases/{id}/accounting-summary/`（按会计权限范围）、支出一览的关联案件列、`?case=` 筛选 |
| P2-C3 | 归档完善（`archived_by`、理由、恢复、审计） | ✅（本地，分支 `codex/p2-platform-completion`） | 归档中只读；子资源写入由策略拒绝；不删除 |
| P2-C4 | 全局搜索 `/api/search/?q=` | ✅（本地，分支 `codex/p2-platform-completion`） | 仅权限范围；范围外顾客/公司最小识别；不记录检索词 |
| P2-C5 | 关联案件创建、公司详情扩展 | ⬜ |
| P2-C6 | 前端路由级 lazy loading | ✅（本地，分支 `codex/p2-platform-completion`） | 主 chunk 2,131→1,126 kB（gzip 633→372 kB） |
| P2-C7 | 支出分类手动输入、规范化与本人历史推荐 | ✅（本地） | `expenses/category-suggestions/`；只用本人历史；只做建议，不改写旧数据 |
| P2-C8 | 个人报销按 owner 隔离并保持简单登记 | ✅（本地） | 维持 P0 的 owner 隔离；没有新增任何审批/支付/入账状态（有测试确认） |
| P2-C9 | Checklist/Document 现有系统文件管理 | ✅（本地，分支 `codex/p2-documents`） | 分类、元数据、上传检查、Checklist 关联、归档/恢复、替换历史、备份恢复说明；不连接 Drive，不做版本树 |
| P2-C10 | Visa CSV/XLSX 导入、校验与批量 PDF | ✅（本地，分支 `codex/p2-visa-import`，基于会计分支） | `accounting/visa-imports/*`；导出全部写审计 |
| P2-C11 | 报价/契约/请求/领收帐票分别完善 | ✅（本地，分支 `codex/p2-c11-vouchers`） | 各自状态/编号/快照/PDF；共用编号、金额、审计基础；既有請求書・領収書状态不回填 |

### P3 — 不动产业务模块

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| P3-D1 | 确认租赁/买卖范围、法定台账字段和金额字段 | ✅（2026-10-01 修订） | 租赁为主、sale 只保留字段；三项无业务意义的来源金额已从最终结构删除 | 只使用 `工作表1` |
| P3-D2 | 新建独立 `real_estate` 模块、列表、详情和简易新规输入 | ✅（2026-10-01 协同台账修订，分支 `codex/p3-real-estate-collaborative-ledger`） | 首屏 7 项；工作台分区：物件・当事者・业务金额・文件・法定台帳・会計参照・内部利益配分・业务可读履历（技术详细仅审计权限者折叠显示）；归档/恢复 | 不并入 Case/Accounting |
| P3-D3 | 保存期限、年度关闭、锁定、更正、权限和审计 | ✅（2026-10-01 协同台账修订） | 担当与权限解绑；操作人写可读履历；李通过明确权限覆盖全操作 | 上线前再次核对有效法令 |
| P3-D4 | `LIST.xlsx` dry-run、独立 QA 导入和对账；正式导入命令 `import_real_estate_list`（2026-10-02） | ✅（本地 QA；正式导入命令已实现，生产执行状态见 AI_HANDOFF §3） | 仅 `工作表1`；QA 命令拒绝生产及非 QA 库；报告不打印真实值 | 保留原文件和 QA 库 |
| P3-D5 | 独立内部利润分配功能 | ✅（本地；10-01 修订后仍有效） | 需 `use_real_estate`＋`manage_profit_distribution`；查看写审计 | 不读取其他工作表，不进入法定台账 |
| P3-D6 | 不动产搜索补齐与批量变更 | ✅（2026-10-02 本地） | 取引日范围・振込状态筛选；原子 `bulk-update`（段階・担当者・取引日）；独立权限 `bulk_change_real_estate`（仅 system_admin） | 已确认只给李；其他人有需求时单独授权 |

### 2026-10-02 变更请求（`CHANGE_REQUEST_2026-10-02_real_estate_batch_reception.md`）

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| CR-1 | 不动产批量变更 | ✅（本地） | 同 P3-D6 |
| CR-2 | 支出：文字规则的类别建议、类别沉淀主档、显式记忆规则 | ✅（本地） | `accounting/0020`；记忆规则默认仅本人，管理员可提升为全事务所；规则管理需 `manage_expense_category`；类别名称确认保留「停车费」 |
| CR-3 | 新规受付改为直接输入，400 字段级显示 | ✅（本地） | 后端兼容接口保留；已确认保持必须关联 Employee，不做未分配案件 |
| CR-5 | 上线前补强：批量版本确认（预览后变化则 409）、停车费类别检查命令、第二轮 QA | ✅（本地，2026-10-02） | `bulk-update` 只接受 token；`check_expense_category_rules` |
| CR-4 | 删除旧照合 API 与 `existing_customer_id` 分支 | ⬜ 暂缓（2026-10-02 确认本次不删） | 确认无其他调用方后另开任务 |

### UI — 表单与操作区布局

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| UI-1 | 共享表单与操作区布局组件，修正窄宽度下按钮挤压字段、横向溢出、Dialog/Drawer 操作列 | ✅（本地，分支 `codex/ui-form-layout`） | 只改前端布局；不改 API・权限・数据库・migration。详见 `CHANGELOG_2026-09-30_ui_form_layout.md` |

暂缓（等业务决策，不在本计划范围内推进）：客户 Portal、税务证明剩余 6 份 PDF 字段映射、年金 PDF 被扶养人数据结构、真实数据 Customer 合并、清風合格通知書业务化、通知/邮件/日历/电子签名。Checklist 模板内容审阅已纳入 P2-C9，不再属于完全暂缓项。

---

## 2. 内容修改计划（按任务列出具体改动点）

### 2.1 P0-A1：既存会社绑定 —— ✅ 已完成

**问题**：`ReceptionNewPage.vue` 有"既存の会社"选择 UI，但 `buildPayload()` 在该模式下清空公司字段，后端 `ReceptionSerializer` 也没有对应参数，导致选中的公司实际未绑定到新建案件。

**改动**：
- `backend/api/serializers.py`
  - `ReceptionSerializer` 新增 `existing_company_id`（可选整数），`validate()` 校验存在性
  - `create()`：`existing_company_id` 提供时直接 `Company.objects.get(pk=...)` 复用，不再进入新建公司分支；新增 `company_reused` 返回字段
  - 顺带修复：`family_members` 循环内变量名与外层 `existing_customer_id` 同名遮蔽的问题（重命名为 `family_member_existing_customer_id`，不影响原有行为，只是消除隐患）
- `backend/api/tests.py`：新增 `test_reception_with_existing_company_binds_case_without_duplicating_company`、`test_reception_rejects_unknown_existing_company_id`
- `frontend/src/pages/ReceptionNewPage.vue`：`buildPayload()` 在 `companyMode === 'existing'` 时发送 `existing_company_id`；新增 `existingCompanyName`（通过 `RemoteCompanySelect` 的 `@change` 捕获），确认页显示"会社：既存を使用（○○）"
- `frontend/src/types/api.ts`：`ReceptionCreatePayload` 增加 `existing_company_id`；`ReceptionResponse` 增加 `company_reused`

**验收**：选中既存公司提交后，`Case.company_id` 等于所选公司，且 `Company.objects.count()` 不增加。已通过测试验证。

### 2.2 P0-A2：顾客候选匹配规则收紧 —— ✅ 已完成

**问题**：原规则里"氏名部分一致 + 生日一致"被判为 `strong`，容易把同姓同名的不同人误判为强匹配；电话号码只做后 7 位比较，未处理国际区号/连字符的等价性。

**改动**（`backend/apps/customers/utils.py` `find_customer_candidates()`）：
- 新增 `_normalize_phone_digits()`：去除非数字字符，`81` 国际区号前缀归一化为国内 `0` 开头
- 新增 `_phone_digits_match()`：末尾 8 位比较（而非 7 位），降低误匹配概率
- 强度判定改为：
  - `strong`：证件号一致 / **氏名完全一致** + 生日一致
  - `medium`：氏名完全一致 + 电话或邮箱一致 / **氏名部分一致** + 生日一致
  - `weak`：仅氏名完全一致 / 氏名部分一致 + 电话或邮箱一致 / 氏名部分一致 + 仅提供了生日（未必一致）
- `backend/api/tests.py`：新增 3 个测试（部分姓名+生日→medium 而非 strong；带连字符/国际区号的电话仍能匹配；部分姓名+电话→weak）

**验收**：`python manage.py test api.tests apps.customers.tests` 全通过（含新增 3 个用例）。

### 2.3 P0-A3：新规受付服务端幂等保护 —— ✅ 已完成

**问题**：`transaction.atomic` 只保证单次请求内的原子性，无法防止前端重复点击、网络重试导致的重复 `POST /api/receptions/`，可能重复创建 Customer / Case。

**实际实现**（与最初设想的方案基本一致，细节见 `docs/CHANGELOG_2026-09-16_p0_followup.md` §3）：
- 把 `api` 首次注册为正式 Django app（新增 `backend/api/apps.py`，`INSTALLED_APPS` 加入 `'api'`），作为横切关注点（Dashboard、Reception 等不属于单一领域 app 的功能）的模型归属地，没有新建额外分层
- `backend/api/models.py`：`ReceptionIdempotencyRecord(request_id unique, response JSONField(null=True), created_at, updated_at)`；`response=None` 表示"处理中"
- `backend/api/views.py` `ReceptionCreateView.post()`：先查/占位再执行，成功后回写 `response`；失败清理占位允许重试；并发同 key 靠数据库唯一约束兜底返回 409
- `frontend/src/pages/ReceptionNewPage.vue`：页面生命周期内固定一个 `request_id`（`crypto.randomUUID()`），每次点击"確定"都带上；收到 409 时给出专门提示
- 测试：`backend/api/tests.py` `ReceptionIdempotencyApiTests`（5 个用例：重复请求不重复创建、不同 key 各自创建、处理中返回 409、失败后允许重试、不带 key 时保持向后兼容）

**范围控制**：这个幂等机制目前只服务于 `/api/receptions/`，没有推广到其它写接口。如果后续其它接口也出现重复提交问题，按同样模式单独评估，不要直接复用同一张表存放不同语义的幂等记录。

### 2.4 P0-A4：User–Employee、模块权限与数据范围 —— ⬜

**需求变化**：2026-09-26 用户明确要求系统未来由多人同时使用，普通用户只能处理自己的内容，管理员按模块授予查看/修改能力。因此旧版“只确认所有登录用户均可访问、不新增权限系统”的计划已经失效。

**实施前先提交小方案确认**：

1. 盘点现有 `User`、`Employee`、认证 API、各模块 queryset 和对象写接口，建立一对一映射及历史账号处理表。
2. 定义最小权限模型：模块动作（查看/新建/修改/归档/导出/设置）+ 数据范围（`own`/`assigned`/`all`）。仅有真实审批业务的其他模块再单独扩展审批权限；个人报销不引入审批。暂不引入多租户或复杂组织树。
3. 明确各模型的 owner/assignee/created_by/updated_by 来源；Customer/Company 的基础搜索与敏感字段权限分开设计。
4. 权限必须覆盖列表、详情、PATCH/DELETE、专用 action、批量操作、导出和文件下载；不能只做菜单隐藏。
5. 增加 A 用户、B 用户、会计管理员、系统管理员和未登录用户的矩阵测试，确保直接请求 ID 也无法越权。
6. 与 P0-A6 AuditLog、P0-A7 历史数据归属一起设计，避免先加权限再重复迁移。

**范围控制**：保留现有 app 边界，优先扩展 authentication/employees 和可复用 permission/filter 基础；不得把所有领域数据搬入认证模块，也不为每个用户建立独立数据库。

**2026-09-27 已确认的方案依据**：

- 账号（2026-09-27 用户确认最终映射；生产按 username 匹配）：`zbry6947@gmail.com` 李 ↔ Employee「李」，唯一系统超级管理员、唯一初始 accounting_admin、受保护账号，会计三项全体权限；`jiao` 焦 ↔ 新建 Employee「焦」，业务管理员，初始 `expense_view_all`（无 change_all/export_all，无其他会计模块）；`zywwind@gmail.com` 周 ↔ Employee「周」，同焦；Employee 3 NAING 无账号；User 4 localdev 为本地开发账号，不关联、不授权。现在不修改任何 `is_superuser`；焦、周降级必须在关联、角色、回归测试、李权限确认、回滚方案都完成后单独批次执行。
- Customer/Company：具有案件业务权限的员工可搜索最小识别信息；详情、敏感字段、文件、修改按 `own`/`assigned`/`all`。
- 会计：`expense_view_all`/`change_all`/`export_all` 初期全部授予李；焦、周只有 `expense_view_all`（可跨用户只读查看 Expense，不能修改或导出他人记录，不开放其他会计模块）；superuser 不自动获得任何业务权限。
- 第一批：只对 Expense 加 `owner`/`created_by`/`updated_by` 并隔离；Income、VehicleUsage、AccountingProject 等只盘点。
- Case：按 `responsible_employee`（assigned）控制，不用 owner；`all` 才可跨担当。
- Document：继承关联 Case 权限；无 Case 时由上传人或明确授权控制。

**P0 方案**：`docs/P0_ACCESS_CONTROL_DESIGN.md` 第 2.1 版（2026-09-27，原则已通过，尚未实施）。Q1～Q11 已由用户决定并写入方案 §4.6、§5、§8.2 等。实施按方案 §11 的批次 1～9 进行：

1. 生产只读核对 + User–Employee 关联 + localdev 部署检查
2. AuditLog + ProtectedAccount + 账号管理保护 + 权限快照；阶段 A 注册李并验证（不强制），阶段 B 单独开启 protected-admin enforcement
3. BusinessAccessPolicy + 角色 + Expense 隔离与余额口径 + 会计其他模块的模块级限制 + 生产禁用调试端点
4. Expense 回填
5. Case/Customer/Company/Document 数据范围 + 受付默认担当
6. 受保护下载（最低权限条件全部满足）
7. 引用核对 + nginx 关闭公开 `/media/`
8. 全矩阵回归 + 李恢复验证 + 回滚演练
9. 焦、周降级（`is_superuser=False`、`is_staff=False`）

每项数据操作（方案 §12 D1～D12）都要用户单独批准。

### 2.5 P1-B1：Case Workspace Action Bar

**目标**：`CaseDetailPage.vue` 顶部增加快捷操作条：対応記録（Timeline 手动追加的入口，已存在，需要提到顶部）、資料受領（对应 Checklist 完成，已有交互，需要有明确入口）、タスク、ファイル、入金、待機にする、案件完了。

**建议改动**：
- 前端：`CaseDetailPage.vue` 新增顶部 `<div class="case-action-bar">`，按钮触发已有的 Dialog（模板已存在：Timeline 新增对话框、Checklist 完成、状态变更对话框），新增的只有"待機にする"（依赖 P1-B3 的 `work_status`）和"入金"（依赖 P2-C1 的会计外键，暂时可以先跳转到会计页面并预填 `case` 参数）
- 不新建独立页面，全部用 Drawer/Dialog，遵循用户"不要为了按钮新建大量页面"的要求

**依赖顺序**：先做 P1-B3（Waiting）才能做"待機にする"按钮；先做 P2-C1（会计外键）才能做真正的"+入金"表单，否则先做"対応記録/資料受領/タスク/ファイル"四个按钮。

### 2.6 P1-B2/B3：统一 Next Action / Waiting 机制

**现状**：`Case.next_action` / `next_action_due_at` 是纯文本+日期，没有状态、没有负责人、没有阻塞原因；`Task`、`Reminder` 是独立模型。

**建议方案（不要一次性大重构，分两步）**：

第一步（低风险，扩展现有字段）：
- `apps/cases/models.py` `Case` 增加：
  - `work_status`（CharField, choices=[active, waiting, completed], default=active）
  - `waiting_reason`（CharField, choices=枚举, blank=True）
  - `waiting_note`（TextField, blank=True）
  - `waiting_since` / `waiting_until`（DateField, null=True）
  - 都是 nullable/有默认值，migration 对旧数据安全
- `apps/cases/status_service.py` 新增 `set_case_waiting(case, reason, note, until, changed_by)` / `clear_case_waiting(case, changed_by)`，内部调用 `record_case_event(EVENT_WAITING_STARTED / EVENT_WAITING_ENDED)`
- `api/views.py` `DashboardSummaryView` 的 `waiting` 统计从"状态映射的占位逻辑"改为 `work_status == 'waiting'`
- 前端：`CaseDetailPage.vue` 顶部状态区显示"顧客資料待ち・5日経過"这类文案（用 `waiting_since` 算天数）

第二步（Next Action 统一，范围更大，需要先跑通第一步再评估）：
- 优先复用 `Reminder` 或新增字段到 `Case`，不要新建第四套模型（用户已在原始需求中强调）
- 这一步在开始前应该先给出一个小范围的技术方案供确认，不要直接大改

### 2.7 P1-B4：今日作业台

- 依赖 P1-B2/B3 落地后，`DashboardSummaryView` 的 `recent_cases` 增加 `assignee` 维度筛选（`?scope=mine` 用 `request.user` 关联到 `Employee` —— 但当前 `Employee` 与 `auth.User` **没有关联**，需要先确认这个关联怎么建立，或者暂时先做"全体"视图，"我的"视图等账号体系明确后再做）
- 这是当前会话不建议直接动手的一项，先确认 Employee↔User 的关联方案

### 2.8 P2 各项

- P2-C1/C2：先补 Accounting 与 Customer/Company/Case 的可选关系，再从各记录工作台展示只读摘要和跳转；不把会计明细复制进 Case。
- P2-C7：分类输入改为可搜索历史分类、可手输、同义词规范化建议、可按本人历史推荐，优先本地规则；推荐必须由用户确认。第一阶段保留 `Expense.category` 自由文本，不改外键、不批量清洗；保留原始输入，不自动重写历史 Expense。
- P2-C8：每条个人报销具有 owner，普通用户仅限本人；现有 Expense 全部归当前用户。保持当前简单登记，不新增提交、审核、批准、支付、入账或退回状态。会计管理员的 `view_all`、`change_all`、`export_all` 分别控制。「精算済み」UI 已于 2026-09-29 废止；`is_reimbursed` 仅作历史兼容字段保留（不删字段/列/数据，不做 migration），不构成报销流程。
- P2-C9：扩展现有 Checklist/Document，完成系统内上传、下载、分类、案件/清单关联、文件元数据（原始名/存储名/MIME/大小/哈希/上传人/上传时间）、替换/归档/删除审计、后端权限和备份恢复规则；不建设 Google Drive 集成，也不迁移现有 Drive 文件。第一阶段不做版本树、版本比较、版本恢复。
- P2-C10：Visa 采用 CSV/XLSX 上传、工作表选择、列映射、预览、逐行校验、幂等生成、ZIP 与错误报告；保留现有模块位置。
- P2-C11：报价、契约、请求、领收分别维护状态和编号，但可共用帐票基础设施及统一导航入口。

具体业务边界和验收以 `docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md` 为准；进入每一项前再补文件级设计，避免提前写死过期方案。

### 2.9 P3 不动产模块

- 新建独立 `real_estate` 领域，不并入 Case 或 Accounting。
- 首屏只录入客户/当事人、物件、房间、管理公司、担当、交易类型和阶段；法定字段按流程逐步强制。
- 先核对宅建业法台账字段、电子显示/打印、保存期限、锁定和更正规则，再确定模型与 migration。
- `LIST.xlsx` 必须先 dry-run，只读取 `工作表1`。保留原值和来源行，不猜测缺失日期或担当；废止列不映射。
- 内部利润分配作为 P3-D5 新功能独立设计，可关联不动产交易，但不读取其他工作表，也不写入法定宅建台账。
- 数据模型、权限方案、迁移脚本和对账报告必须分开评审，不在一个大提交中同时完成。

### 2.10 P0-A8：`/media/` 受保护下载 —— ⬜（只写方案，未经确认不改 nginx）

**现状**：`nginx/default.conf` 的 `location ^~ /sun/media/`、`location ^~ /media/` 直接 `alias` 到媒体目录；`backend/config/urls.py` 另有 `static(settings.MEDIA_URL, ...)`（仅 DEBUG 生效）。结果是已知路径即可不登录下载 `case_documents/` 文件。

**方案必须覆盖**（已写入 `P0_ACCESS_CONTROL_DESIGN.md` §8，推荐 X-Accel-Redirect + nginx `internal`）：

- 禁止 nginx 直接公开 `/media/`、`/sun/media/` 的方式（如改为 `internal` + `X-Accel-Redirect`，或完全由 Django 流式返回），以及对比取舍；
- Django 受保护下载/预览接口：登录校验 + Document→Case 权限继承 + 无 Case 文件的上传人/授权范围；
- 既有文件 URL（数据库中的 `file`/`file_path`、前端硬编码链接、已生成 PDF 链接）的兼容或迁移办法；
- 下载、预览、导出写入 AuditLog；
- Range 请求、大文件、`Content-Disposition` 的 RFC 5987 文件名编码；
- nginx、Django、前端、生产部署各自的回滚方案；
- 未登录、用户 A、用户 B、担当者、管理员的下载测试。

---

## 3. 执行顺序建议

1. ✅ P0-A1、P0-A2、P0-A3（已完成）
2. P0-A4/A6/A7/A8：✅ 本地已实现（2026-09-28）；下一步由用户审查分支，然后按 `DEPLOY.md` 逐项批准 D1～D12
3. P0-A5：补 Dashboard 口径回归测试
4. 继续现有 P1 案件工作台主线；Next Action / Waiting 字段设计仍需先确认
5. 在权限基础可用后，按 P2-C7 → C8 → C9 → C10 → C11 的顺序逐项增强现有模块
6. 最后进入 P3：先确认法定字段和 Excel 含义，再开发不动产模块和执行数据迁移

---

## 4. 每次改动的记录规则（复用 `AI_HANDOFF.md` §13，不重复维护两份规则）

1. 实现代码 + 前端标签/类型 + 测试 + 文档四者一起改，不留其中一处不同步。
2. 新增字段必须 migration；新增/变更 API 必须更新 `AI_HANDOFF.md` §6.1 的 API 表。
3. 本文件（`DEVELOPMENT_PLAN.md`）的任务状态（✅/🚧/⬜）随每次任务完成即时更新，不要等一大批做完再补。
4. 每个批次结束后在 `docs/` 下新增一份 `CHANGELOG_<日期>_<主题>.md`，并在 `docs/README.md` 索引中加一行。
5. 涉及 Customer 合并、历史金额重算、生产数据 migration、批量删除，先停下来找用户确认。

## 5. 2026-10-03 已确认改造批次（待实施）

> 本节为计划，不代表功能已经完成。本轮只更新现有 Markdown，没有修改代码、数据库或生成新的 Markdown 文件。

### 5.1 实施原则

- 先修复会阻断日常操作的单据、Visa 和文件问题，再调整导航与扩展业务主数据。
- 每个阶段分别完成后端、前端、权限、审计、自动化测试和人工验收，不把十二项需求作为一次不可审查的大提交。
- 任何状态迁移、批量更新和 ZIP 下载都必须做对象级权限校验。
- 数据库变更必须先写 migration，并保证已有案件、单据和任务可继续读取。
- 清風功能在取得实际 PSD 和字体并通过可行性验证前，不进入正式实现承诺。

### 5.2 分阶段计划

| 阶段 | 范围 | 主要交付 | 状态 |
|---|---|---|---|
| P1 单据与 Visa | 15.1、15.2、15.3 | 单据自由切换状态与审计、明细输入重构、Visa 单一流程与可靠 PDF 错误处理 | ✅ 代码验收完成，部署前等待真实 Visa 样本打印确认（2026-10-04；未提交、未部署，见 5.9） |
| P2 文件与案件内批量 | 15.6、15.8 | 多文件上传队列、ZIP 下载、单案件必要资料批量更新 | ✅ 代码验收完成（2026-10-05 用户确认；未提交、未部署，见 5.10） |
| P3 工作台与导航 | 15.5、15.7、15.10、15.11 | 导航重组、案件一覧上移、每日计划和内部工作报告 | ✅ 代码验收完成（2026-10-06 用户确认；未提交、未部署，见 5.11） |
| P4 业务主数据 | 15.4、15.12 | 服务价格主数据、委托底价、案件类型与工作流模板 | ✅ 代码验收完成（2026-10-06 用户确认），等待正式服务项目价格和必要资料清单（未提交、未部署，见 5.12） |
| P5 清風模板 | 15.9 | PSD 可行性验证、固定变量区域服务器渲染、视觉验收 | ✅ 代码验收完成，部署前等待真实 Visa/通知书样本打印确认及字体授权确认（2026-10-06 独立审查修正；未提交、未部署，见 5.13） |
| P6 敏感信息与运行优化 | 用户 2026-10-06 指示 | My Number 授权查看、生日和暦、顾客→公司跳转、P4 服务项目暂定价格、Visa PDF 缩小、日本节假日结转、文件「資料内容」命名与 ZIP 上传限制；生产 D5/D11/负责人回填 | ✅ 代码验收完成（2026-10-07：后端全量 540 项 0 失败；公司职员 My Number 入口已补齐；参考资产已恢复，测试的 media 隔离已加上）；未提交、未部署（见 5.14）。生产操作未执行（AI 无服务器权限，步骤见 `DEPLOY.md`） |

### 5.3 P1 验收标准

- 请求书／领受书从任意状态都能切换到任意有效状态；切回草稿后可修改并再次发行。
- 状态失败不会让前端永久处于 loading 或 disabled，刷新前后行为一致。
- 能查看状态变更人、时间和变更前后值，历史发行内容可追溯。
- 明细可以连续快速录入，十行以上仍可清楚对照，错误不会清空其他行。
- Visa 只有一个推荐生成入口，担保人模板被明确使用；生成失败不返回伪成功下载链接。
- 覆盖模板字段、坐标模板、缺字段、损坏模板、下载文件不存在等测试。

### 5.4 P2 验收标准

- 同一选择操作可上传多个文件，逐个显示进度和错误，并可重试失败文件。
- 可下载选中文件或案件全部文件的 ZIP，名称和目录稳定，越权文件不会被打包。
- 案件内必要资料可多选批量更新，支持部分成功结果和审计；不存在跨案件批量入口。

### 5.5 P3 验收标准

- 案件一覧位于案件管理首位；LIST 取込不再作为独立导航项。
- 不动产与会计在“公司内部资料管理”下展示，但 API、权限和数据模型没有混合。
- 每日计划支持案件任务与内部任务、完成划线、备注和结转。
- 每日工作报告在系统内保存，可人工编辑并复制文本，不触发任何外部发送。

### 5.6 P4 验收标准

- 服务价格可配置对客默认报价与委托底价，并明确专业类型；历史单据保存价格快照。
- 新案件类型不再被迫使用签证流程；每种类型绑定明确的工作流模板和必要资料模板。
- 经营管理签转工签后的相关手续可作为关联案件／步骤分别追踪。

### 5.7 P5 前置与验收标准

- 开始编码前必须取得实际 PSD、准确字体文件、姓名／日期图层规则和至少三份期望样例。
- 先做一次服务器端技术验证：PSD 解析、背景保持、姓名日期定位、日文字体、PDF 输出。
- 字体或源文件不满足条件时明确阻止生成，不允许静默使用替代字体。
- 通过不同长度姓名和日期格式的视觉验收后，才替换现有清風生成路径。

**P5 前置调查（2026-10-06，只读，未写生成代码）**

- 仓库中现有模板 `backend/assets/pdf_templates/seifu/合格通知書.pdf`：
  - 由 Photoshop 导出，只有 1 页 A4，内容是一张约 1549×2207 px（约 187 dpi）的位图；
  - 没有文字层、没有嵌入字体，无法从中得到原始图层位置和字体。
- 版面上需要变动的区域不止姓名和日期，还有：通知书编号、許可番号、コース年数（两处）、在籍期間。这些区域在位图里已经留白，部分看起来是用白色矩形覆盖的，背景是否完好需要用 PSD 确认。
- 仓库中没有 PSD；运行环境没有安装 PSD 解析库 `psd-tools`（安装属于新增依赖，需另行确认）。
- 现有字体：Adobe Heiti Std R、Yu Mincho Regular、DengXian Regular。仓库根目录的 `yu-mincho-regular.ttf` 与 `backend/assets/fonts/YuMincho.ttf` 完全相同。哪一种与 PSD 文字层一致、是否有授权，尚未确认。
- 结论：缺少 PSD、准确字体、可变字段规则和期望样例，现在只能做接口和验证方案设计，不能开始正式生成路径。

**前置资料补充与结论（2026-10-06）**

- 用户提供了实际 PSD、PSD 使用的 `MSMINCHO.TTF` 和三份 Photoshop 导出的参考 PDF。PSD 有四个可分离的文字图层（宛名、通知日、通知书编号、許可番号）；隐藏后背景完整。
- 三份参考 PDF 除上述四个区域外背景像素相同。通知书编号可由許可番号派生，不需要重复输入。
- PSD 是 1.5 年课程版本，参考 PDF 是 2 年课程版本。用户决定先按单模板优先实现 2 年课程功能；后续另行提供课程年数可修改的 PSD。
- 字体内部名称与 PSD 都是 `MS-Mincho`。字体文件和含真实值的参考 PDF 放在 Git 忽略的 `backend/media/p5_seifu_input/`，不得提交。

### 5.8 文档更新规则

- 每完成一个阶段，同步更新本计划的状态、`AI_HANDOFF.md` 和相关数据库说明。
- 用户已明确要求只扩展现有 Markdown；本系列工作不新建 CHANGELOG、需求、计划或其他 Markdown。需要记录变更时更新已有相关文档。
- 本条是对本文件第 4.4 节“每批新增 CHANGELOG”规则在本系列工作中的明确例外。

### 5.9 P1 实施结果（2026-10-03～04）

> 仅 P1。P2～P5 未开始。代码在本地工作区，尚未提交、推送或部署；生产库未执行 migration 0021。

- **数据库**：migration `accounting.0021_voucher_history_visa_generations`
  - 新表 `accounting_voucher_status_history`（单据状态履历，单据删除后仍保留）。
  - 新表 `accounting_visa_return_pdf_generations`（Visa PDF 生成记录）。
  - `accounting_visa_return_applications.guarantor_template_id`（可空 FK，SET_NULL）。
  - 只新增表和可空列，不改已有列，旧版本代码可继续运行。
- **请求书／领受书**
  - 请求书（下書き／発行済み／送付済み／入金済み／取消）与领受书（下書き／発行済み／無効）各自在有效状态间任意切换，两者状态互不影响。
  - 只有下書き可编辑、可删除；已发行或无效的单据先切回下書き，修改后再发行。
  - 每次切换写入状态履历：单据种类、ID、变更前后状态、操作者、时间、理由和完整快照。发行为第 N 版。
  - 前端送 `expected_status`，服务器加行锁比对。被他人先改时返回 409，前端显示错误和「変更失敗」标签并刷新列表，按钮不会卡在 loading。
  - 编辑保存时也加锁，打开表单后单据已被发行时返回 409。
- **明细输入**（`VoucherLinesTable`）
  - 宽屏为全宽表格，窄屏（<768px）为同顺序的行卡片。
  - 列顺序：项目／说明・数量・单位・单价・税区分・金额・备注・操作。
  - 键盘操作：Enter 移到下一栏，最后一行的备注栏按 Enter 追加新行；税区分用 ↓ 打开列表并以 Enter 选择；移入栏位时全选已有值。
  - 支持复制上一行、上下移动、删除确认（空行直接删）、实时金额与税额。
  - 行错误只标在该行，不清空其他行；后端的行错误通过 `line_item_row` 对应到行。
  - 编辑对话框不再因 Esc 或点击背景而关闭（防止丢失输入）。
- **Visa**
  - 单一主流程：申請人 → 担保人テンプレート → 必要項目 → プレビュー → PDF 生成。批量导入收进「まとめて作成」。
  - 担保人模板快照由服务器按所选模板重建，并记录模板 ID 和版本；预览按字段显示来源（テンプレート／手入力）。
  - 生成前校验申请人、PDF 氏名栏（英文姓或中文姓）、日期、旅券、担保人三项和 PDF 模板。
  - `visa_return_pdf.py` 删除吞异常的回退路径，按错误码返回可读错误：missing_fields、template_field_mismatch、template_broken、template_missing、font_missing、field_write_failed、flatten_failed、output_invalid、file_missing。
  - 失败时保留输入；只有文件真实保存后才给下载链接。每次生成都记录方式（form／coordinates）、模板版本（文件 SHA-256 前 16 位）和担保人模板版本。
- **代码审查后的修正（2026-10-03）**
  - `guarantor_snapshot` 改为只读，完全由服务器根据担保人模板生成；任何请求组合都无法写入伪造的快照或模板标记。
  - 单选项（性別、婚姻状況、确认项目等）出现以下情况时，返回 `field_write_failed`，不再当作成功：值不在对应表中、找不到可选的选项、写入失败。
  - 平坦化后若仍残留输入栏，返回 `flatten_failed`。
  - 生成时出现预料之外的异常，返回 `generation_failed`：记录生成失败、写审计，详细内容留在日志。
  - 文件保存失败（容量、权限等）返回 `storage_failed`：记录失败、写审计、不留下半成品文件、不给下载链接。
  - 文件无法读取时，下载返回 404 `file_missing`。
  - 请求书 PDF 的数量栏总是附带单位（如「2件」）；备注栏只在填写时打印。输入栏标明「備考（PDF に表示）」。领受书的「摘要」一直都会打印备注，保持不变。
- **旧 Visa PDF 接口废止（2026-10-04，最后一条审查意见）**
  - 旧 `GET /api/accounting/visa-return-applications/{id}/pdf/` 原本会绕过生成记录、直接生成 PDF。现已废止：路由保留，但只返回 410 `legacy_pdf_endpoint_disabled`；不调用生成函数，不生成文件，不建记录；权限检查不变，每次访问写一次审计，用于查找外部调用方。
  - **所有成功生成的 Visa PDF 都必须通过 `VisaReturnPdfGeneration`**，入口统一为 `visa_pdf_generation.generate_and_record`：
    - 单票：`POST .../generate-pdf/`，再从生成记录的下载 URL 取得 PDF；
    - 批量：`POST /api/accounting/visa-imports/{id}/pdf-zip/` 也改用同一服务，ZIP 中放的是已保存并记录的文件；缺项或失败的申请写进 `結果.txt`。
  - 前端删除了未使用的 `downloadVisaReturnApplicationPdf()`，`frontend/src` 中已没有指向 Visa `/pdf/` 的调用。
  - 已无引用的 `visa_return_pdf_response`、`generate_visa_return_pdf` 已删除。
- **验收状态**（对照 5.3）
  - 状态任意切换与再发行、失败不卡死、履历可追溯、连续录入且错误不清空、Visa 单一入口且不返回伪成功下载、六类异常测试：均已由自动测试和合成数据的浏览器 QA 确认。
  - 状态：**代码验收完成，部署前等待真实 Visa 样本打印确认**。全部审查意见已修正。
  - 部署前由用户完成：用真实 Visa 样本生成 PDF 并实际打印，确认版面、勾选标记和中日文字体。
  - P2 待用户确认后再开始。

### 5.10 P2 实施结果（2026-10-04）

> 仅 P2。P3～P5 未开始。代码在本地工作区，未提交、推送或部署。没有模型变化，也没有 migration。

- **多文件上传**（共用组件 `DocumentUploadQueue`，案件详情的「ファイル」抽屉和书类管理都使用它）
  - 可一次选择或拖入多个文件，逐个显示文件名、大小、进度和状态（待机／登録中／成功／失敗），失败时显示原因。
  - 「失敗したファイルだけ再試行」只重新发送可重试的失败文件。文件本身有问题（种类、大小、文件名）时需要重新选择。
  - 每个文件单独调用一次 `POST /api/documents/`：对应一条 Document 记录，并分别做案件权限检查、保存和审计。失败不会清空队列，也不会撤销已成功的文件。
  - 开始前调用 `POST /api/documents/upload-check/`，由服务器检查件数、合计大小和每个文件的问题；整体超限时一个都不上传。
  - 文件名安全检查：路径分隔符、控制字符、Windows 保留名、只有点号、超过 200 字符，都会被拒绝。现有的单文件上传也会做同样的检查。
- **ZIP 一括ダウンロード**（共用组件 `DocumentZipActions`）
  - `POST /api/documents/download-zip/`，参数为 `{case, ids}` 或 `{case, all: true}`，只限同一个案件。
  - ZIP 内按「資料分類/ファイル名」放置。文件名不按所选范围决定，而是先对该案件中用户可见的全部文件（含已归档文件）统一命名，再取出所选文件：
    - 同一文件夹内重名时（不区分大小写），ID 最小的文件保留原名，其余按 ID 顺序改为「名前 (ID n).拡張子」；
    - 改名后若与实际存在的文件名重复，再加「(ID n-2)」等后缀。
  - 因此无论选哪些文件、选多少，同一文件的名字都相同，也不会冲突。（2026-10-05 按审查意见修正：之前是在所选范围内比较 ID，单独下载时名字会变。）
  - 每个文件单独判断下载权限。以下情况不放入 ZIP，原因写在「ダウンロード結果.txt」里：
    - 没有权限；
    - 不可见（不显示文件名）；
    - 属于其他案件；
    - 文件实体不存在。
  - 一个都下载不了时返回 400 `nothing_to_download`；超过上限时返回 `zip_too_many_files` 或 `zip_too_large`。
  - ZIP 写在临时文件里，响应结束后删除，不作为业务文件保存。
  - 审计 `document_zip_download`／`document_zip_refused` 记录：案件、包含件数、排除件数及各原因的件数、合计字节数、文件 ID。
- **案件内必要资料批量操作**
  - `POST /api/cases/{id}/checklist-batch/`，参数为 `{item_ids, changes, versions?}`。
  - 「案件進捗・必要資料」区域的「まとめて操作」：可单项选择、整组全选或解除、取消选择，可「まとめて完了」，也可「まとめて設定…」批量设置状态、受領日、準備者、取得先・手続先和備考（追記／置き換え）。
  - 执行前的确认窗口显示件数和要修改的项目，执行后显示成功和失败件数，并逐项列出失败原因；失败的项目保持选中。
  - 服务器先确认所有 ID 都属于 URL 指定的案件，只要有一个不属于就整体拒绝（不部分执行）。之后每个项目在各自的事务中更新：
    - 页面打开后被别人修改过的项目（版本不一致）返回 `conflict`；
    - 给非资料类项目设置受領日返回 `not_applicable`；
    - 其他项目照常成功，不会被回滚。
  - 每个成功项目写审计 `checklist_item_batch_updated`（含修改前后的值），整批写汇总审计 `checklist_batch_update`；改为完成的项目还会写入案件经过。
- **上限**（可通过 settings 修改；未在 settings.py 中设置时使用以下值）
  - 单个文件：20MB（`DOCUMENT_MAX_UPLOAD_BYTES`）。
  - 一次上传：20 件、合计 200MB（`DOCUMENT_BATCH_MAX_FILES`、`DOCUMENT_BATCH_MAX_TOTAL_BYTES`）。
  - ZIP：100 件、合计 200MB（`DOCUMENT_ZIP_MAX_FILES`、`DOCUMENT_ZIP_MAX_TOTAL_BYTES`）。
  - 必要资料批量：200 件。
- **验收状态**（对照 5.4）
  - 多文件上传（逐个进度、错误、重试）、ZIP（选中／全部、稳定的目录和名称、越权文件不放入）、单案件批量（部分成功、审计、拒绝跨案件）：均已通过自动测试和合成数据的浏览器 QA 确认。
  - 状态：**代码验收完成**（2026-10-05 用户确认）。ZIP 重名规则的审查意见已修正。

### 5.11 P3 实施结果（2026-10-05）

> 仅 P3。P4、P5 未开始；P1、P2 的内容未改动。代码在本地工作区，未提交、未推送、未部署；生产库未执行 `tasks/0003`、`0004`。

**实施前由用户确认的四项决定**（2026-10-05）

1. 计划和报告：只有本人可编辑；拥有全件查看权限（`case_view_all`／`case_change_all`）的人只读；其他人看不到（404）。不新增权限。
2. 计划项关联案件需要该案件的修改权限（与原有案件任务相同）；关联后只显示在本人的计划里，案件详情页不变。
3. 结转默认日期为下一个工作日（周一至周五），可以修改；没有节假日日历，所以不考虑节假日。
4. 报告分草稿和确定：草稿可以重新生成，有手工编辑时须确认后才覆盖；确定后不能再生成，但正文仍可编辑；每人每天一份。

**导航**（只改前端，不合并后端的数据和权限）

- 菜单定义集中在 `frontend/src/utils/navigation.ts`，按权限筛选显示，同一页面只保留一个入口。
- 新菜单结构：

  | 一级菜单 | 包含项 |
  |---|---|
  | 作業台 | 毎日の計画・業務報告・ダッシュボード |
  | 案件管理 | 案件一覧（第一项）・新規受付・顧客・会社 |
  | 社内資料管理 | 会計資料（原会计菜单）・不動産資料・書類管理 |
  | 帳票管理 | 不变 |
  | システム設定 | 案件テンプレート・担当設定、アカウント・事務所設定 |

- 「LIST 取込」不再是独立菜单项，改为不動産一览页上的按钮，仍按原有导入权限显示。
- 「今日の作業台」并入每日计划页右侧的「案件の作業」，`/workbench` 自动跳转到 `/daily-plan`；后端 `/api/workbench/today/` 保持不变。
- Dashboard 只保留统计概览，删除与案件一覧重复的「最近更新された案件」表，并增加到毎日の計画、案件一覧的链接。

**每日计划**（扩展现有 `Task`，不另建任务系统）

- 与原有案件任务的隔离（2026-10-05 审查修正）：`GET /api/tasks/` 默认只返回原有案件任务，加 `plan=1` 才返回计划项。案件的 `task_total_count`、`task_completed_count`、`next_task_title`（次の対応）不计入关联了案件的计划项。有回归测试。
- 新增字段：`work_date`、`priority`、`result_note`、`carried_from`、`created_by`；`case` 改为可空，以支持不关联案件的内部工作；状态增加 `carried_over`（结转完毕）。
- 页面：`/daily-plan`。只读查看其他担当者的计划时，右侧「案件の作業」隐藏。支持新增（关联案件或内部工作）、完成（显示删除线）、补充结果备注、上下移动排序、编辑、删除、单个结转和批量结转；有全件查看权限的人可选择其他担当者，只读查看。
- 结转：在目标日期新建一项，该项的 `carried_from` 指向原项；原项以「结转完毕」状态留在原日期，原日期的痕迹得以保留。

**工作报告**（新表 `daily_work_reports`）

- 页面：`/daily-reports`。可从当天计划生成草稿；正文可编辑、复制、确定。
- 生成时的任务快照固定保存，之后修改任务不会改变已保存的报告。
- 报告只保存在系统内部，不发送邮件、Slack、Teams 或任何外部服务。

**并发与事务**

- 修改、删除、结转、编辑报告、确定报告时，都会核对页面读取时的版本（`updated_at`）；不一致返回 409，不会静默覆盖。
- 排序整体一次完成：只要有一项版本不一致或不属于当天，就整体取消。
- 批量结转逐项处理、允许部分成功，返回每一项的结果。

**审计**（以下单项操作写入可读的对象审计；批量结转和排序另写批次汇总审计）

- 计划项的创建、修改（含修改前后的值）、删除、结转
- 报告的生成、重新生成、编辑、确定

**验收状态**（对照 5.5）

- 案件一覧位于案件管理第一项；LIST 取込不再是独立菜单项。
- 不动产与会计都放在「社内資料管理」下，但各自的 API、权限和数据模型没有合并。
- 每日计划支持关联案件的工作和内部工作，支持完成删除线、备注和结转。
- 工作报告保存在系统内部，可人工编辑并复制文本，不会触发任何外部发送。
- 以上各项均已通过自动测试和合成数据的浏览器 QA 确认。
- 状态：**代码验收完成**（2026-10-06 用户确认）。

### 5.12 P4 实施结果（2026-10-06）

> 仅 P4。P5 未开始；P1～P3 的内容未改动（只在原有帳票保存流程上加了版本确认和服务项目快照）。代码在本地工作区，未提交、未推送、未部署；生产库未执行 `accounting/0022`、`cases/0022～0024`，也未执行角色同步。

**用户确认的决定**（2026-10-06）

1. 委托底价：只有会计管理员和系统管理员可以查看和修改；普通职员、只有案件权限的用户都看不到。系统管理员通过审计日志看到底价的变更记录，属于授权范围。
2. 新規受付中的服务项目只作参考，可以不选，可以多选。
3. 单据上选了服务项目后，名称、数量、单位、单价、税区分都可以修改，但必须保留选择时的原始快照。
4. 第一阶段只接入見積書、請求書和新規受付；契約書、領収書不接入。手工明细继续可用。
5. 案件种别：沿用现有「その他」绑定汎用流程；新增「税理士委託」「会社解散」「就労ビザ社員入社手続」「年金脱退・加入手続」。后两种可以通过 `parent_case` 关联原签证案件，也可以独立创建。
6. 流程阶段按建议（见下表）；任何阶段都可以切到「取下げ」，有案件修改权限的人也可以从取下げ恢复到其他阶段，前后阶段都写审计。
7. 必要资料：每种新种别只建立空模板并完成绑定，不编造资料项目。默认担当规则不变（未指定时为受付者本人）。
8. 首批服务项目暂不提供：本轮不通过 migration 或 fixture 写入任何名称、价格或底价。

**服务价格主数据**（新表 `accounting_service_items`）

- 字段：分类、名称、对客标准价（Decimal，可为空）、价格的税込／税抜、委托底价（Decimal，可为空）、委托专业类型、税区分、单位、启用、内部备注、排序、首次使用时间、创建／更新者和时间。
- 新业务权限：`accounting.use_service_item`（查看、选择）、`accounting.manage_service_item`（登录、修改）、`accounting.view_service_floor_price`（查看、修改底价）。
  - 系统管理员、会计管理员：三个全有。
  - 业务管理员、职员：只有查看（新規受付里选择用）。
- 没有底价权限时，序列化器直接删除 `floor_price` 字段；提交底价返回 400。不按 `is_superuser` 放行。
- 修改必须带 `version`，冲突返回 409。每次新建、修改、停用、启用、删除都写审计，包括底价修改前后的值。
- 搜索只匹配名称和分类，不匹配底价和内部备注。
- 被单据或案件用过（`first_used_at` 不为空）的项目不能物理删除，只能停用。停用后不能再新选，旧单据和旧案件里的内容不变。
- 管理画面：`/vouchers/service-items`「サービス項目・料金」，菜单只对有管理权限的人显示。

**单据快照**（沿用 `line_items` JSON，不建关联表）

- 每行由后端生成 `line_key`，保证单据内唯一；选择了服务项目的行还有 `service_item_id` 和 `service`。
  - `service` 是选择时的名称、分类、标准价、税込／税抜、税区分、单位和专业类型，不含底价。
  - 实际单价、数量、名称等仍是行本身的字段，可以修改。
- 底价单独存放在单据的内部列 `internal_line_costs`，用 `line_key` 对应到行。
  - API 只对底价权限者返回；发行快照、状态履历、PDF 和明细搜索都只读 `line_items`，所以不含底价。
- `line_key`、`service` 和底价都由后端生成，客户端提交的这些内部字段一律忽略。
  - 只有 `line_key` 和服务项目都与已保存的行一致时，才沿用原快照和底价。
  - 否则视为新选择，从启用中的主数据重新生成；交换 `line_key` 不能挪用别的行的底价。
- 发行时（离开下書き），把当时的 `internal_line_costs` 按版本写入新表 `accounting_issued_line_cost_snapshots`。
  - 请求书改回下書き、改价后再发行，旧版本仍可追溯。
  - 只有底价权限者能通过 `GET …/internal-costs/` 读取。
- 编辑保存时锁定该行，并比较 `version`（`updated_at`），冲突返回 409。旧画面不送 `version` 时仍按原方式接受。
- 复制规则：見積書→請求書会复制快照和底价；→契約書、請求書→領収書会去掉服务项目相关字段。
- 旧单据不需要回填；下次修改明细时才补上 `line_key`。

**新規受付**

- 服务项目选择器只显示启用中的项目，价格标注为「標準（参考）」，可多选并填写数量。
- 选择结果作为快照存在 `Case.service_items`（不含底价），之后修改主数据不影响已有案件。
- 没有 `use_service_item` 权限时提交服务项目返回 403。
- 「関連元の案件」可选，只能选自己看得到的案件；不存在和看不到返回同样的提示。
- 关联循环检查（2026-10-06 审查修正）：沿关联元一直追溯到底，不设层数上限。指向自己、子孙（包括超过 20 层的链）都拒绝；已有数据中存在异常循环时也能终止，并拒绝关联。
- 案件仍必须关联担当者（未指定时为本人），不恢复旧的顾客照合流程。

**案件种别与工作流**（新表 `case_workflow_templates`、`case_workflow_stages`）

| 流程 | 适用种别 | 阶段（对应的旧 status，供一览和期限等统计使用） |
|---|---|---|
| 汎用 | その他 | 受付(accepted) → 対応中(preparing_documents) → 完了(completed) |
| 専門家委託 | 税理士委託、会社解散 | 受付 → 資料収集(collecting_documents) → 専門家へ依頼(applied) → 専門家対応中(under_review) → 結果受領(approved) → 完了 |
| 従業員・社会保険手続 | 就労ビザ社員入社手続、年金脱退・加入手続 | 受付 → 資料収集 → 書類作成(preparing_documents) → 窓口提出(applied) → 受理確認(under_review) → 完了 |

所有流程另有「取下げ(withdrawn)」阶段。

- `CaseTypeMaster` 新增：
  - `workflow_template`：为空表示沿用原 13 阶段；
  - `requires_application_category`：新种别和「その他」为 False，案件编号改为「略称-年月-氏名-连番」。
- 案件创建时固定 `workflow_template` 和第一个阶段；之后修改种别的绑定，不影响已有案件。
  - 原有案件的 `workflow_template` 为空，继续使用 13 阶段，不迁移、不回填。
- 段阶变更：`POST /api/cases/{id}/change-stage/`。
  - 需要案件修改权限：看不到返回 404，能看不能改返回 403。
  - 可以切到同一流程的任何启用阶段，包括取下げ和从取下げ恢复。
  - 送 `expected_stage` 时，如果不一致返回 409。
  - 写入 Timeline 和审计（前后阶段）。完了日、取下げ日在进入该阶段时记录，离开时清空。
- 13 阶段的 `change-status` 对流程案件返回 400；「案件を中止」改为切到该流程的取下げ阶段。
- 必要资料：每个新种别和「その他」各有一个空模板（`application_category` 为空）。创建案件时复制当时的项目，之后修改模板不影响已有案件。
- 案件设置的修改需要 `cases.manage_case_settings`，以下变更都写审计（模块 `case_settings`，含前后值）：
  - 种别、流程、阶段的修改；
  - 必要资料模板及其项目的新建、修改、删除、恢复、排序。
  - 流程一旦被案件使用就锁定（2026-10-06 审查修正）：
    - 不能修改流程的名称、系统、启用状态，只能改说明和排序；
    - 不能新增阶段，也不能修改任何阶段的名称、排序、启用状态、对应的旧 status 或删除阶段，即使该阶段还不是任何案件的当前阶段；
    - 要改动时，用「複製」（`POST /api/workflow-templates/{id}/duplicate/`，连同阶段一起复制并写审计）生成新流程，修改后把案件种别重新绑定到新流程；
    - 已有案件继续使用旧流程。
- 画面：
  - 案件详情：流程案件显示该流程的步进条和阶段变更，并显示关联元案件和关联案件（只列出自己看得到的）、受付时的服务项目参考；
  - 案件一覧显示阶段名；
  - 设置页新增「業務フロー」标签，种别编辑可选择流程和申请区分是否必需。

**migration 与回滚**

- `accounting/0022`：新增 `accounting_service_items`、`accounting_issued_line_cost_snapshots` 两张表，见積書和请求书各加 JSON 列 `internal_line_costs`（MySQL 保留表达式默认值）。
- `cases/0022`：新增流程和阶段两张表；`cases` 加可空的 `workflow_template`、`workflow_stage`、`parent_case`，以及 JSON 列 `service_items`；种别表加 `workflow_template`、`requires_application_category`。
- `cases/0023`：为 `requires_application_category` 设置 DB 默认值 1，保证旧代码不报错。
- `cases/0024`：写入上表的流程、阶段、4 个新种别、その他的绑定和空模板。
  - 先按 code、再按名称查找；已存在就复用，不重复建。
  - 可以反向执行：解除绑定，删除空模板、未使用的新种别和流程。被案件使用的种别保留。
- 回滚验证：在独立 QA 库上把 `cases` 回滚到 0021、`accounting` 回滚到 0021，P4 的列和表全部移除，案件数据保留；之后再次正向迁移也成功。
- 回滚的代价：服务项目、底价快照、案件的流程绑定、关联案件、受付服务项目都会丢失。明细行 JSON 里的 `line_key` 和 `service` 会留下，但旧代码会忽略。
- 只回滚代码、不回滚数据库时，旧代码可以照常写入，靠 DB 默认值。流程案件会退回按 13 阶段的 status 显示。

**部署前必须做的事**（不在本轮执行）

1. 执行 `accounting/0022`、`cases/0022～0024`。
2. 先 dry-run 角色同步 `setup_access_roles`，确认只给 5 个 Group 增加上述服务项目权限，再 `--apply`。
3. 由用户提供首批服务项目的正式数据（名称、对客标准价、税込／税抜、委托底价、专业类型、税区分、单位），另行导入。
4. 业务确认新种别的必要资料清单，再到设置页补充。

**验证**

- 后端测试：
  - P4 新增 `accounting/tests_service_items.py` 19 项、`cases/tests_workflows.py` 14 项（含审查修正后的流程锁定、复制与重新绑定、任意层数循环检查）；
  - 全部 472 项通过；`check` 和 `makemigrations --check` 均无问题。
- 前端：单元测试 78 项、`vue-tsc` 和 build 通过。
- 浏览器 QA：在独立 QA 库上用合成数据完成。覆盖：
  - 服务项目页（底价显示、409 冲突）；
  - 見積書选择服务项目、改价后显示「変更：単価」和内部底价；
  - 新規受付（新种别不显示申请区分、关联元案件、两个服务项目）；
  - 案件详情的流程和阶段变更、父案件显示子案件、设置页的业務フロー标签。
- 审查修正后的浏览器 QA：在独立 QA 库确认使用中的流程只显示「複製」和锁定说明，未使用的流程可以编辑，复制出的新流程可以编辑。
- 状态：**代码验收完成**（2026-10-06 用户确认），等待正式服务项目价格和必要资料清单。业务数据（首批服务项目、新种别的必要资料清单）尚未确认，不能视为业务数据验收完成。
- 部署前建议：
  - 以普通职员身份登录，确认页面上不出现底价列、按钮或金额；
  - 由业务确认流程阶段对应的旧 status 在仪表盘中的分组语义（例如「結果受領」计入「許可 / 不許可」）。

### 5.13 P5 单模板实施结果（2026-10-06，含同日独立审查修正）

> 本轮只实现清風 2 年课程单模板，不做多模板或版面编辑器；课程年数可修改的 PSD 到位后再扩展模板版本。没有提交、推送或部署。

**范围与固定内容**

- 用户只能输入三项：宛名、許可番号、通知日。
- 通知书编号由后端用唯一函数 `derive_notice_number` 派生，格式为「許可番号 + 空格 + A」，印在模板原有的「第 … 号」之间。画面、记录 API 和 PDF 都使用这个值，客户端不能指定。
- 固定内容：课程年数 2 年（日文、英文两处）、在籍期間 2027/04/01～2029/03/31、模板 PDF 背景、模板原有的「様」「号」、坐标、字号、MS Mincho 字体、颜色和仿粗体。画面上只读显示，API 拒绝写入。

**输入规则**（后端为准，前端用同样规则提前提示）

- 宛名：
  - NFC 规范化，连续空格合并为一个，最长 40 字；
  - 拒绝控制字符、书式字符（零宽、双向控制等）、私用区、未分配字符和换行；
  - 字体中没有字形的字符拒绝（`unsupported_character`）。
- 宛名的排版：
  - 印在模板「様」之前的固定栏位（x 88.0～159.5pt）；
  - 先把字号从 18.47pt 缩到 12pt，仍放不下就横向压缩到最多 70%；
  - 仍放不下则拒绝（`recipient_name_too_long`），不溢出、不和「様」重叠；
  - 大约能放 8 个全角字，半角字母更少。
- 許可番号：
  - NFKC 规范化（全角转半角），转大写；
  - 只允许 3～12 位英数字，必须含数字，中间可用连字符分隔；
  - 通知书编号必须能放进「号」之前，否则拒绝。
- 通知日：必须是真实日期，范围 2000～2099 年；印成「YYYY年MM月DD日」，月和日补零。
- 保存记录时就会检查字形和排版。字体未配置时不检查，生成时再以字体错误中止。

**生成与下载**

- 「PDF作成」接口：`POST seifu-notice-records/{id}/generate_pdf/`，可附 `request_id`。处理顺序：
  1. 锁定该记录行；
  2. 校验输入、字体、模板和排版；
  3. 在内存中生成 PDF；
  4. 重新打开 PDF，确认只有 1 页、大小正常，且编号、許可番号、宛名、日期都在文本里；
  5. 写入存储，再确认文件存在且大小一致；
  6. 新建生成记录 `SeifuNoticePdfGeneration`，返回 201 和记录 JSON。
- 任何一步失败都不留生成记录，已写入的文件会删除，并写失败审计。输入错误返回 400，模板、字体、生成或存储故障返回 422。
- 重复提交：同一个 `request_id` 再次提交时返回已有记录（200，`replayed=true`），不重复生成；该 ID 属于其他记录时返回 400。
- 下载：`GET seifu-notice-generations/{id}/download/`，只返回状态为成功且文件确实存在的记录；文件不存在时返回 404 `file_missing` 并写审计。
- 预览：`preview_pdf` 只返回经过同样校验的 PDF，不保存文件，也不建记录。
- 旧任意文字接口 `POST seifu-notice-pdf/generate/`：返回 410 `legacy_seifu_endpoint_disabled`，不调用生成函数、不产生文件或记录，只写 `seifu_legacy_endpoint_called` 审计。
- 权限沿用 `accounting.use_seifu`，记录在模块内共享，与原行为一致。不按 `is_superuser` 放行，测试已覆盖普通职员和只有超级用户标志的账号。

**数据与兼容**

- `accounting/0023_seifu_notice_fixed_fields`：记录表新增四个可空列。
- `accounting/0024_seifu_notice_pdf_generations`：新表 `accounting_seifu_notice_pdf_generations`。
- 旧记录不回填，显示为「旧形式」：
  - 修改备注不会清掉旧的 `text_items`（审查前的实现会清掉，已修正）；
  - 补全三项后即可生成。

**字体与部署**

- 字体通过 `SEIFU_MS_MINCHO_FONT_PATH` 配置。开发环境默认使用 Git 忽略的 `backend/media/p5_seifu_input/MSMINCHO.TTF`。
- 字体内部名称不是 MS Mincho、文件损坏或不存在时都会中止，不改用其他字体。
- 新增 `backend/.dockerignore` 排除 `media/` 等目录，PSD、真实样本和字体不会进入镜像。`.env.prod.example` 和 `backend/.env.example` 中增加了字体变量的说明。
- 生产环境的字体放在镜像之外（例如受保护的卷），再通过环境变量指定。

**视觉校准**（PSD 文字图层和三份参考 PDF 在本地只读比对，结果只记录数值，不记录真实内容）

- PSD 的 4 个文字图层都是 MS-Mincho 仿粗体。字号：宛名 18.47pt，编号和許可番号 12.31pt，通知日 14.36pt（审查前实现用的是 10.8pt）。
- 改为保留模板原有的「様」「号」（审查前实现会先盖白再重画，与参考位置不一致）。
- 通知日的「年」「月」「日」按参考中的固定位置排列：三份参考之间误差不超过 0.4pt，我们的输出与参考相差不超过 0.4pt。
- 课程年数改为约 14pt；英文侧的年数位置修正了 3.8pt。
- 仿粗体改用「描边＋填充」，颜色按参考调深。在籍期間与参考的像素差减少到原来的约 1/11。
- 变动区域以外，输出与模板背景 0 像素差异，与参考也是 0 像素差异。
- 仍存在的差异：
  - Photoshop 与 PDF 渲染的抗锯齿、仿粗体算法不同，笔画浓淡会有轻微差异；
  - 参考中的数字字距随内容略有变化（疑为比例字距），我们按固定槽位排列，单个数字最多相差约 1pt；
  - 输出嵌入了完整的 MS Mincho，每个文件约 3.3MB；字体子集化需要新增 `fontTools` 依赖，本轮未加。
- 不能宣称与 Photoshop 输出完全一致；需要用户打印确认。

**验证**

- 后端 P5 测试 20 项（`apps.accounting.tests_seifu_notice`），覆盖：
  - 正常生成、派生编号、各必填项缺失、非法日期和日期范围、不合法的許可番号；
  - 过长、放不下或字体缺字形的宛名，危险字符；
  - 客户端试图覆盖派生值、模板、坐标或字体；
  - 无权限的生成、下载和预览；
  - 模板缺失或损坏，字体缺失、损坏或非 MS Mincho；
  - 绘制失败，输出为空、损坏或缺少印字内容；
  - 存储失败或写入被截断，存储后数据库失败时清理文件；
  - 下载时文件不存在，成功记录的元数据，`request_id` 重复提交；
  - 旧接口 410，旧记录兼容，预览不保存，合成场景（常规、较长、片假名、英文）的排版。
- 后端全量 492 项通过；`check` 和 `makemigrations --check --dry-run` 都无问题。前端单元测试 84 项、`vue-tsc` 和生产构建都通过；`git diff --check` 通过。
- 前端单元测试覆盖：校验、编号派生、本地日期、操作 ID、JSON/blob 错误解析，以及画面上没有坐标、字体或任意文字入口，下载入口只在成功后出现，失败时保留输入并恢复 loading。
- 独立 QA 库上用合成数据做了浏览器验收，确认：
  - 后端排版错误能显示，输入保留，按钮的 loading 恢复；
  - 生成成功（201）后出现下载入口，下载返回 200；
  - 预览返回 200；
  - 旧接口返回 410。
- 验收后已删除 QA 中的记录和文件。

**状态**

- **代码验收完成，部署前等待真实 Visa/通知书样本打印确认及字体授权确认。**
- 部署前需用户完成：
  1. 确认 MS Mincho 允许在服务器上生成 PDF（商用授权）。本实现不对授权作任何判断。
  2. 用真实业务数据打印，与三份 Photoshop 样例对照。
- 已知风险：仓库中已经跟踪了 YuMincho、Adobe Heiti、DengXian 等字体文件（P5 之前提交的，不在本轮范围），其授权也应一并确认。

### 5.14 P6 敏感信息、人员关系、文件规范与运行优化（2026-10-07，代码验收完成）

> 只实现 P6，没有修改 P1～P5 已验收的功能。没有提交、推送或部署。生产数据操作（D5、D11、费用负责人回填）没有执行，原因和步骤见本节末尾及 `DEPLOY.md`。

**1. My Number 授权查看**

- 新权限 `customers.reveal_my_number`（migration `customers/0011`）。`setup_access_roles` 只给 `system_admin`；其他账号用 `grant_business_permission --username … --permission customers.reveal_my_number [--revoke] --apply --yes` 单独授予或收回（命令只接受这一个权限，并写审计）。不看 `is_superuser`。
- 专用接口：`POST /api/customers/{id}/reveal-my-number/`、`POST /api/family-members/{id}/reveal-my-number/`、`POST /api/company-staff/{id}/reveal-my-number/`，返回 `{registered, my_number}`，并带 `Cache-Control: no-store`。
- 判定顺序：
  1. 看不到对象：404（审计 `not_visible`，只记 ID，不记名字）；
  2. 没有表示权限：403 `my_number_permission_required`；
  3. 顾客只能看到基本信息（BASIC，例如没有案件）：403 `my_number_scope_required`。表示权限不会扩大可见范围；
  4. 家族沿用家族行的取得规则（父顾客须能看详细）；关联人物本身不可见时 403；
  5. 无法读取：422 `my_number_unavailable`；
  6. 成功：审计 `my_number_reveal`。
- 拒绝和错误都写审计 `my_number_reveal_denied`，记录操作者、对象、时间、结果、原因和权限。审计、日志、异常和错误文字里都没有明文（测试按字符串检查）。
- 公司职员（2026-10-07 补齐）：使用同一个权限和同一个服务，不新建第二套。
  - 职员行本身沿用现有取得规则：父公司须能看详细，否则 404。
  - 关联了顾客的职员返回该顾客的值；该顾客本身不可见（MINIMAL）时返回 403 `my_number_scope_required`，职员关系不会扩大顾客的可见范围。
  - 未关联顾客的旧式职员返回 `CompanyStaff` 自身的值。
  - 审计目标为 `companies.companystaff`，`extra.linked_customer` 记录是否关联了顾客。
  - 公司详情页的职员行使用同一个画面组件；切换标签页、打开或关闭职员编辑框都会清除明文。
- 一览、详情、搜索、导出（包括公司和职员 API）继续只返回 `has_my_number`。
- 画面 `MyNumberReveal`：
  - 默认显示伏字和「登録済み」；
  - 有权限才显示「表示」，「隠す」后恢复伏字；
  - 值只保存在组件内部，不放 store、localStorage、URL 或日志；
  - 切换对象、切换标签页（el-tab-pane 隐藏时仍留在 DOM 中，所以用 `reset-key` 清除）、离开画面、重新加载都会恢复伏字；
  - 迟到的响应会被丢弃；
  - 不提供复制按钮。

**2. 生日和暦**

- 共用 `utils/wareki.ts`，只改变显示，例如 `1990年5月1日（平成2年5月1日）`。
- 改元日：明治 1868-01-25、大正 1912-07-30、昭和 1926-12-25、平成 1989-01-08、令和 2019-05-01；第一年显示「元年」。
- 空值显示「-」，不存在的日期原样显示，明治之前只显示西暦。
- 用在顾客详情、家族、公司职员。

**3. 顾客详情 → 公司**

- 关联公司按公司合并成一行（代表、职员、案件三种关系合并），点击打开对应的 `/companies/{id}`。
- 顾客详情的标签页保存在 `?tab=` 中，所以返回、刷新、直接打开 URL 都会回到原来的标签页。摘要卡「関連会社」会跳到关联公司栏。
- 后端对每个公司返回 `can_open`（按公司规则判断是否可见）：
  - 不可见的公司只显示名称，电话和邮箱为空，不能点击，并提示「担当範囲外のため会社ページは開けません」；
  - 直接访问该公司的 URL 也返回 404。

**4. P4 服务项目的暂定价格**

- `accounting/0025` 新增 `code`（唯一、可空）、`price_status`（provisional / confirmed，默认 provisional）、`price_confirmed_at`、`price_confirmed_by`。`0026` 设置回滚兼容的 DB 默认值。`0027` 投入 8 项基本服务（税 10%、价格按含税处理），全部为暂定价格：

  | code | 名称 | 对客 | 底价 | 委托 | 单位 |
  |---|---|---|---|---|---|
  | work_visa_application | 就労ビザ申請 | 110,000 | 55,000 | 行政書士 | 件 |
  | permanent_residence | 永住許可申請 | 165,000 | 82,500 | 行政書士 | 件 |
  | company_dissolution | 会社解散手続 | 220,000 | 165,000 | 司法書士 | 件 |
  | tax_accounting | 税理士業務 | 110,000 | 88,000 | 税理士 | 件 |
  | highly_skilled_application | 高度専門職申請 | 165,000 | 82,500 | 行政書士 | 件 |
  | highly_skilled_annual_support | 高度専門職一年サポート | 330,000 | 264,000 | 行政書士 | 年 |
  | business_manager_renewal | 経営・管理更新 | 165,000 | 82,500 | 行政書士 | 件 |
  | translation | 翻訳 | 5,500 | 3,300 | なし | 頁 |

- 投入的幂等性：
  - 先按 code 查找，没有 code 时按「分类＋名称」认领旧项目；
  - 只补空字段，不覆盖已编辑或已确定的价格和状态；
  - 回滚只删除仍为暂定、未被使用、价格仍是初始值的项目。
- 新案件类型的必要资料模板保持为空。
- 「価格を確定」：
  - 需要管理权限和底价权限两者；
  - 画面两次确认，必须带 version，旧版本返回 409；
  - 记录确定人和时间，审计 `service_item_price_confirmed`，被拒绝的操作也写审计；
  - 确定后再修改价格、含税区分、底价、税区分或单位，会回到暂定。
- 普通职员能看到对客价格和「暫定価格」标签，看不到底价。
- 明细和受付的快照保存 `price_status`。之后主数据被确定，旧快照也不变；明细显示「暫定価格から作成」。
- 见积书和请求书在发行时，如果含暂定价格的行，会先返回 400 `provisional_price_confirmation_required`。画面确认后带 `confirm_provisional` 再次提交即可发行（只提醒，不阻止）。审计记录确认过的行号。PDF 不印底价。

**5. Visa PDF 缩小**

- 原因：完整嵌入的 dengxian.ttf（16.4MB）。
- 做法：用已有依赖 PyMuPDF 1.26.5 的 `subset_fonts()` 做字体子集化（`pdf_fonts.py`），没有新增依赖。
- 子集化前后比较每页的尺寸和文字，不一致时报 `font_subset_failed`（422）。子集化前后都运行原有的输出检查。
- 单票、批量 ZIP、新旧接口都经过同一个 `_render_visa_return_pdf`。
- 实测（合成数据）：表单方式 20.47MB → 0.27MB；坐标方式也小于 5MB。测试比较了页数、尺寸、文字和像素，前后一致。
- 生成记录的 `details.stats` 保存子集化前后的大小。
- 模板、坐标和生成记录规则都没有改变。

**6. 日本节假日结转**

- 依赖：`jpholiday==1.0.3`（MIT，离线，固定版本，已写入 requirements）。判定范围 2000～2050 年，范围外只把周末当休息日，并显示提示。
- `tasks/business_days.py`：结转的默认日期跳过周末、祝日、振替休日、国民の休日。`GET /api/tasks/calendar/?date=` 返回日期信息和下一个营业日。
- 用户仍然可以选择休息日，画面会提示「…は祝日（…）です。休日でも結転できます。」。

**7. 文件「資料内容」与命名**

- `documents/0006` 新增 `content_label`、`display_name`；`0007` 设置回滚兼容默认值。
- 原文件名（`file_name`）、资料内容、显示名和 UUID 保存名分开存放。
- 资料内容的两条路径（后端为准）：
  - **新上传画面**（P6 队列，总是发送 `content_label`）：必须填写。拒绝控制字符和书式字符、`\ / : * ? " < > |`、`..`、开头或结尾的「.」、保留名，最长 60 字。发送了但为空或不合法时返回 400。
  - **旧单文件 API 兼容路径**（P6 之前的客户端，不发送 `content_label`）：不返回 400。后端按顺序从「必要资料名 → 标题（去掉与原文件相同的扩展名）→ 原文件名 → 分类名」派生，危险字符替换为空格；都不可用时为「資料」。顾客名仍由后端从案件取得，不推测。
  - 案件既没有顾客也没有公司时，旧路径不设资料内容和显示名，与 P6 之前完全相同（下载用原文件名）；新画面则返回字段错误 `case`。
  - 审计 `document_upload` 的 `extra.content_label_source` 记录来源：`user`、`legacy_derived` 或 `legacy_no_party`。
- 显示名由后端生成 `資料内容-顾客名.原扩展名`：
  - 顾客名从案件取得，没有顾客时用公司名，两者都没有时返回字段错误（`case`），客户端无法指定；
  - 扩展名只采用允许列表中的原扩展名；
  - 同一案件内重名（不区分大小写）时，新文件加上固定后缀 ` (ID n)`，加后缀时锁定案件行。
- 单个下载和 ZIP 都使用显示名。旧文件没有资料内容，继续使用原文件名；补填资料内容后生成显示名。
- 上传 ZIP：
  - 单独的大小上限 `DOCUMENT_ZIP_UPLOAD_MAX_BYTES`，默认 10MB，不超过一般上限；
  - 不解压，作为附件保存；
  - 只读取目录检查：条目数 ≤200、不允许绝对路径或 `..`、不允许嵌套压缩包、压缩比 ≤100、展开后 ≤100MB、无法读取时拒绝。
- 前端事前检查使用 `upload-policy` 的同一组值（包括 ZIP 上限和资料内容长度）。
- 每行输入资料内容（有候选项），可以批量填入未填写的行。有未填写的行时不开始上传，队列和输入都保留；失败的行可以重试。

**8. Migration 与回滚**

- 新增：`accounting/0025～0027`、`customers/0011`、`documents/0006～0007`。都是新增列、权限或数据，My Number 不重新加密。
- 在 QA 库确认过：回滚到 `accounting 0024 / customers 0010 / documents 0005` 后再重新执行 migrate 都能成功，8 项服务项目能重新生成。
- `makemigrations --check` 没有变化。
- 部署时需要 `migrate`，以及 `setup_access_roles --apply --yes`（给 system_admin 加表示权限），依赖中新增 `jpholiday`。

**9. 验证**

- P6 后端测试 48 项：
  - `customers/tests_my_number`（15，其中公司职员 5 项）；
  - `accounting/tests_p6_service_prices`（8）、`tests_p6_visa_size`（5）；
  - `tasks/tests_business_days`（3）；
  - `documents/tests_p6_documents`（12，其中旧单文件 API 兼容 4 项）；
  - `common/tests_media_isolation`（5，测试的 media 隔离）；
  - 另外修改了已有测试的资料内容和发行确认参数。原来失败的 `cases.tests_work` 和 `real_estate.tests` 两项没有修改测试，修正实现后通过。
- 后端全量 540 项通过（0 failures、0 errors，单独运行），`check` 和 `makemigrations --check --dry-run` 无问题。
- 前端单元测试 98 项、`vue-tsc`、构建、`git diff --check` 都通过。
- 独立 QA 库（合成数据）浏览器验收：
  - My Number：表示、隐藏，切换标签页后从 DOM 中清除，刷新恢复伏字，存储和 URL 中没有明文；无权限 403、范围外 404；
  - 生日和暦（顾客、家族、公司职员）；
  - 顾客 → 公司详情，返回后保持标签页；
  - 8 项暂定价格、两次确认、409、确定；
  - 见积发行时的暂定确认（取消不变化，确认后变为提出済み）和「暫定価格から作成」标签；
  - Visa 生成并下载：20.47MB → 0.27MB；
  - 结转：默认跳过祝日，选择祝日时提示，可以结转；
  - 资料内容：未填写时保留队列，批量填入，自动取顾客名，重名加 ID 后缀，下载名；ZIP 过大在事前拦截，损坏 ZIP 被后端拒绝后可重试，loading 恢复。

**全量测试中发现并修正的 P6 回归（2026-10-07）**

1. `real_estate` 文件下载 500：受保护下载的共用函数也用于 `RealEstateFile`（没有 `display_name` 列），P6 的 `download_name` 直接读取这个属性。已改为 `getattr`，不动产文件仍然用原文件名下载。
2. 旧单文件上传 API 返回 400：P6 把 `content_label` 设为一律必填，破坏了旧客户端。已改为上面的两条路径。
3. 文件替换历史：`update()` 中记录 `DocumentReplacement` 的代码被错误地缩进到「有资料内容时」的分支里，没有资料内容的旧文件被替换时不会留下历史。已修正，并补了测试。
4. **测试删除了开发环境的 media 目录（重大）**
   - 根因：P6 的 `tests_p6_visa_size` 没有设置临时 `MEDIA_ROOT`，`tearDown` 中的 `shutil.rmtree(settings.MEDIA_ROOT)` 删除了 `backend/media/`，其中包括 P5 的参考资产（都在 Git 之外）。开发库中带文件的 Document 为 0 件。
   - 恢复：用户同意后，从本机原始来源恢复了 P5 参考资产。恢复前只读比对文件名、字节数和 SHA-256，与事故前记录的文件名和大小一致；恢复后确认 PSD 能读取尺寸、字体可以加载且内部名称为 MS Mincho、3 份 PDF 都是 1 页并能打开。文件仍被 Git 忽略。
   - 隔离措施：
     1. `config/test_runner.py` 的 `IsolatedMediaTestRunner`（`settings.TEST_RUNNER`）在整个测试运行期间把 `MEDIA_ROOT` 换成临时目录。即使个别测试漏写 `override_settings`，也不会保存或删除真实的 media。
     2. `apps/common/test_isolation.py` 的 `safe_rmtree`：只允许删除系统临时目录下的路径；项目 media 及其下级、项目根目录、上级目录、用户主目录、根目录、空路径、临时目录本身都会被拒绝。测试中原有的 `shutil.rmtree` 全部改为使用它（11 个文件）。
     3. 回归测试 `apps/common/tests_media_isolation`：在作为「默认 media」的临时目录里放一个哨兵文件，再运行 P1、P5、P6 的 PDF 测试，确认哨兵仍在。还确认了：把 visa 测试的临时 `MEDIA_ROOT` 去掉后，这个回归测试会失败；按事故当时的写法删除，会被安全检查拒绝。

**10. 剩余风险**

- 清風 PDF 仍嵌入完整 MS Mincho（约 3.3MB），可以复用同样的子集化处理，但不在本轮范围内。
- 服务项目价格是暂定值，正式价格由用户在画面上确定。

**11. 生产操作（D5、D11、费用负责人回填）**

- 没有执行。AI 没有服务器访问权限，生产操作由用户在服务器终端执行。
- 只读确认 → 备份 → dry-run → 报告 → 执行 → 验证的步骤，以及停止条件，写在 `DEPLOY.md` 的「P6 部署与生产数据整理」一节。
- `--expect-count` 使用当次 dry-run 的实际数字，不使用历史值 1335。

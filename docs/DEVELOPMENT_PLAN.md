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
| P2-C1 | Income/Expense 增加 customer/company/case 可选外键 | ⬜ |
| P2-C2 | 从 Case 查看账务、从账务回到 Case | ⬜ |
| P2-C3 | 归档完善（`archived_by`、理由、恢复、审计） | ⬜ |
| P2-C4 | 全局搜索 `/api/search/?q=` | ⬜ |
| P2-C5 | 关联案件创建、公司详情扩展 | ⬜ |
| P2-C6 | 前端路由级 lazy loading | ⬜ |
| P2-C7 | 支出分类手动输入、规范化与本人历史推荐 | ⬜ |
| P2-C8 | 个人报销按 owner 隔离并保持简单登记 | ⬜ | 不新增审核、支付或入账流程 |
| P2-C9 | Checklist/Document 现有系统文件管理 | ⬜ | 不连接或迁移 Google Drive；第一阶段不做完整版本管理 |
| P2-C10 | Visa CSV/XLSX 导入、校验与批量 PDF | ⬜ |
| P2-C11 | 报价/契约/请求/领收帐票分别完善 | ⬜ |

### P3 — 不动产业务模块

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| P3-D1 | 确认租赁/买卖范围、法定台账字段和金额字段含义 | ⬜ | 只确认主表三个金额列；忽略 `强哥` 表 |
| P3-D2 | 新建独立 `real_estate` 模块、列表、详情和简易新规输入 | ⬜ | 不并入 Case/Accounting |
| P3-D3 | 保存期限、年度关闭、锁定、更正、权限和审计 | ⬜ | 上线前再次核对有效法令 |
| P3-D4 | `LIST.xlsx` dry-run、人工确认、正式迁移和对账 | ⬜ | 保留原文件，可重复执行、可回滚 |
| P3-D5 | 独立内部利润分配功能 | ⬜ | 不读取 `强哥` 表，不进入法定台账 |

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
- P2-C8：每条个人报销具有 owner，普通用户仅限本人；现有 Expense 全部归当前用户。保持当前简单登记，不新增提交、审核、批准、支付、入账或退回状态。会计管理员的 `view_all`、`change_all`、`export_all` 分别控制。
- P2-C9：扩展现有 Checklist/Document，完成系统内上传、下载、分类、案件/清单关联、文件元数据（原始名/存储名/MIME/大小/哈希/上传人/上传时间）、替换/归档/删除审计、后端权限和备份恢复规则；不建设 Google Drive 集成，也不迁移现有 Drive 文件。第一阶段不做版本树、版本比较、版本恢复。
- P2-C10：Visa 采用 CSV/XLSX 上传、工作表选择、列映射、预览、逐行校验、幂等生成、ZIP 与错误报告；保留现有模块位置。
- P2-C11：报价、契约、请求、领收分别维护状态和编号，但可共用帐票基础设施及统一导航入口。

具体业务边界和验收以 `docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md` 为准；进入每一项前再补文件级设计，避免提前写死过期方案。

### 2.9 P3 不动产模块

- 新建独立 `real_estate` 领域，不并入 Case 或 Accounting。
- 首屏只录入客户/当事人、物件、房间、管理公司、担当、交易类型和阶段；法定字段按流程逐步强制。
- 先核对宅建业法台账字段、电子显示/打印、保存期限、锁定和更正规则，再确定模型与 migration。
- `LIST.xlsx` 主表迁移必须先 dry-run。保留原值和来源行，不猜测缺失日期、担当或三个相近金额列。`强哥` 工作表已确认无用，不分析、不映射、不迁移。
- 内部利润分配作为 P3-D5 新功能独立设计，可关联不动产交易，但不复用 `强哥` 表数据，也不写入法定宅建台账。
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

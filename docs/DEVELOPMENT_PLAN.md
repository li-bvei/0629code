# SUNRISE 开发计划（当前有效版本）

更新时间：2026-09-16
状态：进行中。与 `docs/AI_HANDOFF.md` 配套使用——本文件回答"接下来按什么顺序改、每一项具体改哪些文件"，`AI_HANDOFF.md` 回答"项目现在是什么状态"。两者冲突时，先看代码/测试/migration 的实际状态，再更新这两份文档。

---

## 0. 现状确认（2026-09-16）

- 本地 `main` 与 `origin/main` 的**已提交历史完全一致**（均指向 `bd09084`）。当前差异全部来自本地未提交的工作区改动，尚未推送，不存在"远端更新未同步"的情况。
- 工作区改动 = 上一轮 intake/workspace 批次（详见 `docs/CHANGELOG_2026-09-06_intake_workspace.md`）+ 本次会话新完成的 P0 修复（见下文与 `docs/CHANGELOG_2026-09-16_p0_followup.md`）。
- 尚未提交（commit）。是否现在提交、分几次提交，等本轮任务告一段落后再决定。
- 验证状态（本次会话内，MySQL 可连接环境下实测）：

```
python manage.py test                    → Ran 86 tests — OK（全通过）
python manage.py makemigrations --check  → No changes detected
npm run build                            → 成功（vue-tsc -b && vite build）
```

---

## 1. 任务清单与状态

标记说明：✅ 已完成并有测试　🚧 进行中/部分完成　⬜ 未开始

### P0 — 恢复可交付性（阻断继续扩展新功能）

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| P0-A1 | 修复"既存会社"绑定 | ✅ | 见 §2.1 |
| P0-A2 | 收紧顾客候选匹配 strong 规则 + 电话规范化 | ✅ | 见 §2.2 |
| P0-A3 | 新规受付服务端幂等保护 | ✅ | 见 §2.3 |
| P0-A4 | Timeline / Case API 的对象访问范围确认与测试 | ⬜ | 见 §2.4 |
| P0-A5 | Dashboard 指标口径固化为文档 + 测试 | 🚧 | 口径已在 `AI_HANDOFF.md` §7 写明，缺显式回归测试 |

### P1 — 案件工作台闭环

| # | 任务 | 状态 |
|---|---|---|
| P1-B1 | Case Workspace Action Bar（対応記録/資料受領/タスク/ファイル/入金/待機/完了） | ⬜ |
| P1-B2 | 统一 Next Action（负责人/期限/状态/完成/snooze/阻塞原因） | ⬜ |
| P1-B3 | Waiting 机制（`work_status`、原因、开始日、预计恢复日） | ⬜ |
| P1-B4 | 今日作业台（我的作业 / 全体，支持直接操作） | ⬜ |
| P1-B5 | Timeline 自动化剩余（文件、入金、支出、PDF、完了、再开） | 🚧 | 已接入：受付创建案件、状态变更、登记状态变更、进度信息变更、Checklist 完成 |
| P1-B6 | Checklist 与资料受领联动 | ⬜ |
| P1-B7 | RemoteSelect 请求竞态 / 错误状态 / 初始值测试 | ⬜ |

### P2 — 数据与财务闭环

| # | 任务 | 状态 |
|---|---|---|
| P2-C1 | Income/Expense 增加 customer/company/case 可选外键 | ⬜ |
| P2-C2 | 从 Case 查看账务、从账务回到 Case | ⬜ |
| P2-C3 | 归档完善（`archived_by`、理由、恢复、审计） | ⬜ |
| P2-C4 | 全局搜索 `/api/search/?q=` | ⬜ |
| P2-C5 | 关联案件创建、公司详情扩展 | ⬜ |
| P2-C6 | 前端路由级 lazy loading | ⬜ |

暂缓（等业务决策，不在本计划范围内推进）：客户 Portal、税务证明剩余 6 份 PDF 字段映射、年金 PDF 被扶养人数据结构、真实数据 Customer 合并、Checklist 模板内容审阅、清風合格通知書业务化、通知/邮件/日历/电子签名。

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

### 2.4 P0-A4：对象访问范围确认 —— ⬜

**背景**：`docs/PROJECT.md` §5 明确"MVP 阶段不设计复杂权限矩阵"，所以这一项**不是新增权限系统**，而是：
1. 确认现状：任何登录用户（`IsAuthenticated`）能否读写任意 Case 的 Timeline / Checklist / 状态变更——预期现状就是"能"，这是当前 MVP 阶段的既定设计，不是 bug。
2. 把这个现状**明确写进文档**（`docs/AI_HANDOFF.md` 或 `docs/CODING_RULES.md`），避免后续 AI 或开发者误以为存在对象级权限而依赖它。
3. 补一条测试，锁定这个已知行为（防止未来无意中引入部分权限检查导致行为不一致、半吊子权限的情况）。

**不要做**：不要在此任务里顺手引入 per-case 权限、角色系统——这属于未来独立评估的范围（`ROADMAP.md` "Out of Scope"）。

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

暂不展开到文件级别；等 P0/P1 收尾后再细化，避免计划文档本身过期。

---

## 3. 执行顺序建议

1. ✅ P0-A1、P0-A2、P0-A3（已完成）
2. P0-A4（访问范围确认+文档+测试）—— 纯确认性质，成本低，建议下一步做
3. P0-A5（Dashboard 口径回归测试补齐）
4. 与用户确认 P1-B2/B3 的技术方案（Next Action / Waiting 字段设计）后再动手，因为涉及新字段和跨模块统一，风险高于 A1-A5
5. P1-B1（Action Bar）在 B3 部分落地后跟进
6. P2 留到 P1 主线走通之后

---

## 4. 每次改动的记录规则（复用 `AI_HANDOFF.md` §13，不重复维护两份规则）

1. 实现代码 + 前端标签/类型 + 测试 + 文档四者一起改，不留其中一处不同步。
2. 新增字段必须 migration；新增/变更 API 必须更新 `AI_HANDOFF.md` §6.1 的 API 表。
3. 本文件（`DEVELOPMENT_PLAN.md`）的任务状态（✅/🚧/⬜）随每次任务完成即时更新，不要等一大批做完再补。
4. 每个批次结束后在 `docs/` 下新增一份 `CHANGELOG_<日期>_<主题>.md`，并在 `docs/README.md` 索引中加一行。
5. 涉及 Customer 合并、历史金额重算、生产数据 migration、批量删除，先停下来找用户确认。

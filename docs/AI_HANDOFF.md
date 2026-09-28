# SUNRISE AI 交接总文档

更新时间：2026-09-28
项目：SUNRISE 日本行政书士事务所内部业务管理系统  
仓库：`/Users/tatsuya/Documents/Projects/0629code`

这份文档是后续 AI 接手本项目时的第一阅读入口。它汇总当前项目定位、实际代码结构、已完成事项、已知缺口、验证结果、文档来源和下一步建议。

## 0. 给下一位 AI 的阅读顺序

1. 先读本文件。
2. 读 `docs/SYSTEM_ARCHITECTURE.md`：全项目唯一的架构约束，不可违反。
3. 再读 `docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md`，确认最新业务要求、模块边界、权限原则和未决问题。
4. 再读 `docs/DEVELOPMENT_PLAN.md`，确认当前任务清单和实施顺序。
5. 查看 `git status` 和当前任务涉及的代码、测试、migration。
6. 需要深入历史背景时，再读 `AI_CONTEXT.md` 和 `AI_TASK.md` 的对应章节。
7. 需要确认产品原则、数据库或部署规则时，读取 `docs/PROJECT.md`、`docs/DATABASE.md`、`docs/CODING_RULES.md`、`docs/DEPLOY.md`。
8. 变更细节见 `docs/CHANGELOG_2026-09-06_intake_workspace.md`、`docs/CHANGELOG_2026-09-16_p0_followup.md` 和后续按日期排列的记录；旧版审查结论见 `docs/PROJECT_AUDIT_2026-09.md`。

文档优先级固定为：AI_HANDOFF.md（当前状态与入口）> SYSTEM_ARCHITECTURE.md（架构约束）> DEVELOPMENT_REQUIREMENTS_2026-09-26.md（业务需求）> DEVELOPMENT_PLAN.md（实施顺序）> DATABASE.md（数据结构）> CHANGELOG（历史）。

代码是“已经实现了什么”的最终依据；本文件和产品文档是“应该如何继续”的依据。若代码、测试、文档冲突，先报告冲突，不要直接删除历史实现。

## 1. 项目定位

这是一个日本行政书士事务所内部使用的 ERP / 案件管理系统，不是通用 SaaS、复杂 OA 或通用财务软件。

核心业务循环：

```text
新规受付 → 顾客识别/复用 → 案件创建 → Checklist → 下一动作/期限
→ 资料与申报进度 → 完成/归档 → 会计与帐票
```

核心原则：

- Case 是业务主线，Customer、Company、Checklist、Timeline、Document、Accounting 围绕 Case 组织。
- Customer 是自然人的唯一身份来源；FamilyMember、CompanyStaff 尽量通过关系关联既有 Customer。
- 当前优先保证事务所内部日常作业闭环，不扩展多租户 SaaS 或客户账号；但 2026-09-26 已确认需要内部多用户权限、数据所有权和审计，这项新要求覆盖早期“暂不设计复杂权限矩阵”的结论。
- 后端已有但前端隐藏的旧模块不要擅自删除：Task、Reminder、Document、Portal 等仍可能被后续恢复或扩展。

## 2. 技术栈与运行环境

| 层 | 技术 |
|---|---|
| 后端 | Django 4.2 + Django REST Framework |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus |
| 数据库 | MySQL 8 |
| PDF | PyMuPDF + ReportLab |
| Excel | openpyxl |
| 部署 | Docker Compose + Gunicorn + Nginx/宝塔反向代理 |
| 生产路径 | `/sun/` |
| 业务时区 | `Asia/Tokyo` |

主要目录：

```text
backend/
  api/                         主 API 路由、Dashboard、Reception
  apps/authentication/         登录、账号、axes
  apps/customers/              Customer、FamilyMember、身份匹配
  apps/companies/              Company、CompanyStaff
  apps/cases/                  Case、状态机、Checklist、模板
  apps/employees/              业务担当者
  apps/timelines/              案件时间线与自动事件
  apps/documents/              案件文件模型/API
  apps/tasks/                  历史 Task 模型/API
  apps/reminders/              Reminder、期限隐藏记录
  apps/accounting/             会计、Excel、PDF、税务证明
frontend/src/
  pages/                       后台页面
  components/                  RemoteSelect 等共享组件
  api/                         Axios API 封装
  router/                      前端路由
docs/                          当前文档与历史记录
```

## 3. 当前工作区与验证状态

2026-09-28 状态：

```text
branch      = codex/p0-access-control（基于 main = de95411，未推送）
commits     = 文档基线 + P0 访问控制 7 个实现切片 + 文档收尾（见 docs/CHANGELOG_2026-09-28_p0_access_control.md）
main / origin/main = de95411（未变）
production  = 未部署；D1～D12 均未执行
```

下一位 AI 必须先执行：

```bash
git status --short --branch
git log --oneline main..HEAD
```

不要使用 `git reset --hard`、`git checkout --` 或批量删除来“清理”工作区。

2026-09-28 验证（分支 `codex/p0-access-control`）：

| 检查 | 结果 | 说明 |
|---|---|---|
| `python manage.py test` | **通过** | Ran 189 tests — OK（原有 97 项全部保留断言；访问控制测试 92 项，含关联绕过与无担当进行中案件测试） |
| `python manage.py makemigrations --check --dry-run` | 无差异 | |
| `python manage.py check` | 0 issues | |
| `npm run build` | 通过 | `vue-tsc -b && vite build` |
| `git diff --check` | 通过 | |
| 预览库冒烟 | 通过 | 独立库 `gyoseishoshi_erp_p0_preview` + 4 个测试账号，用 Django 测试客户端调用真实端点，结果与权限矩阵一致 |
| 浏览器实测 | **未完成（部署前阻断项）** | 预览工具进程无法读取 `backend/.venv`（macOS 权限），未能启动后端预览 |
| `nginx -t` | **未完成（部署前阻断项）** | 本机 Docker 守护进程未运行；在 `DEPLOY.md` 上线第 15 步于容器内执行 |

本地开发库 `gyoseishoshi_erp` 未应用新 migration（避免改动现有数据）。在该库上运行新代码前需先 `migrate`。

前端构建仍提示单个约 1.9MB 的 JS chunk，暂不阻断功能验收，但后续应做路由级拆包（`docs/DEVELOPMENT_PLAN.md` P2-C6）。

## 4. 产品与数据模型现状

### 4.1 核心关系

```text
Customer
 ├─< Case >─ Company
 ├─< FamilyMember >─ Customer（可选，独立身份优先）
 └─< CompanyStaff >─ Company

Case
 ├─< CaseChecklistItem
 ├─< Timeline
 ├─< Document
 ├─< Task（历史模型，前端暂时隐藏）
 ├─< Reminder
 └─< Accounting / TaxRenewal 关联（部分已经存在，尚未全部统一）
```

### 4.2 Case 状态

`Case.status` 仍有 13 个业务状态，不能未经用户确认重新设计或删除。`status_service.py` 负责状态变更、日期校验、警告、强制变更和 Timeline 记录。

`registration_status` 是案件登记状态，当前包括 active / inactive / archived。普通 PUT/PATCH 已设置为只读，必须通过专用 action 变更。

案件编号格式：

```text
{案件種別略称}-{申請区分略称}-{东京时间 YYYYMM}-{客户名}-{4位流水号}
```

完整前缀递增，并通过唯一约束冲突重试保护并发创建。

### 4.3 仍然容易混淆的对象

- `CaseChecklistItem` 是当前前端实际使用的案件步骤/资料清单。
- `Task` 是历史独立任务模型，后端保留，前端入口目前隐藏。
- `Reminder` 与 Case 的 `next_action` / `next_action_due_at` 还没有统一成一个 Action 模型。
- `registration_status=archived` 已存在；后续归档工作主要是补齐 archived_by、理由、恢复和审计，而不是重新创建归档字段。

## 5. 当前前端功能

### 5.1 主要路由

已存在并受登录保护的主要页面：

- `/dashboard`：Dashboard KPI、阶段统计、最近案件、期限列表
- `/reception/new`：三步新规受付
- `/cases`、`/cases/:id`：案件列表与案件工作区基础页面
- `/customers`、`/customers/:id`：顾客与家族/关联数据
- `/companies`、`/companies/:id`：公司与公司职员
- `/employees`：担当者
- `/case-checklists`：案件种别、申请区分、よくある項目、Checklist 模板
- `/timelines`：Timeline
- `/documents`：文件模块基础页面，完整工作流尚未完成
- `/accounting/*`：会计 Dashboard、支出、收入来源、车辆、项目收支
- `/vouchers/*`：請求書/領収書、返签 visa、税务证明、清風通知书和占位页面
- `/settings`：密码修改与 root 账号管理

菜单上已隐藏或标记暂缓的功能：独立 Task、部分 Reminder、客户 Portal、完整文件工作流、部分帳票。

### 5.2 RemoteSelect

当前已添加：

- `RemoteSelect.vue`
- `RemoteCustomerSelect.vue`
- `RemoteCompanySelect.vue`
- `RemoteStaffSelect.vue`

目标是避免默认分页 20 导致第 21 条以后无法选择。后续要补充快速连续搜索时的请求竞态处理、错误提示和初始值加载测试。

## 6. 当前后端 API 能力

### 6.1 本轮新增或修订

| API | 当前状态 |
|---|---|
| `GET /api/dashboard/summary/` | 服务端统计 Case 数量、阶段、期限和最近 10 件案件 |
| `POST /api/customers/match/` | 规则式顾客候选匹配，实际响应为 `{ "candidates": [...] }` |
| `GET /api/customers/?search=` | 顾客、电话、邮箱、地址、证件号、案件号远程搜索 |
| `GET /api/companies/?search=` | 公司名、カナ、代表者、法人番号搜索 |
| `POST /api/receptions/` | 既有顾客复用（`existing_customer_id`）或新顾客创建；既有公司复用（`existing_company_id`，2026-09-16 新增）或新公司创建；并可创建案件、家族、Checklist、Timeline。响应含 `customer_reused` / `company_reused`。支持可选 `request_id`（2026-09-16 新增）做幂等保护：同一 `request_id` 重复提交返回同一结果不重复创建；处理中的重复请求返回 `409` |
| `POST /api/cases/{id}/apply-checklist-template/` | `merge` / `replace` 模式，返回 created 数量 |
| `POST /api/cases/{id}/change-status/` | 案件状态专用变更入口 |
| `POST /api/cases/{id}/change-registration-status/` | 登记状态专用变更入口 |
| `GET /api/documents/{id}/download/`、`/preview/` | 2026-09-28 新增（本地）：受保护下载/预览。父 Case 担当或 `document_download_all`；审计 denied/authorized/started；生产用 X-Accel-Redirect |
| `GET /api/auth/me/` | 2026-09-28 修订：`permissions`/`business_permissions` 只返回显式业务权限（不再是 superuser 的全部权限），新增 `employee_id`、`employee_name`、`is_protected`、`dev_tools_enabled` |
| 所有业务 API | 2026-09-28：统一经 BusinessAccessPolicy 限定范围。范围外 404、可见但不可写 403；顾客/公司列表与搜索对范围外只返回最小识别字段（`access_level`）；Expense summary/dashboard 无全体会计权限时余额为 `null`（`balance_visible`、`expense_scope`） |
| `POST /api/receptions/`、`POST /api/cases/` | 2026-09-28：未指定担当则设为本人；账号未关联 Employee 返回 400；无 `case_change_all` 不能以他人为担当 |
| 开发用端点（demo seed、seed-standard、PDF 坐标/表单调试、numbered_sample） | 2026-09-28：`ENABLE_DEV_TOOLS=False`（生产）时不注册或返回 404 |

### 6.2 会计与帳票

当前主要有：

- 支出、支出分类、收入来源、车辆使用、项目收支；
- 請求書・領収書 PDF；
- 返签 visa 表；
- 税务证明记录与部分正式 PDF；
- 清風合格通知书基础 PDF 添加文字工具，但业务继续开发暂停。

税込/税抜和 10% / 8% / 非課税的计算规则记录在 `AI_CONTEXT.md`，不可在没有回归测试的情况下修改。历史帳票中已经发现过存储金额与当前重算金额可能不一致的旧数据，批量重算必须先获得业务确认。

## 7. 2026-09 intake / workspace 批次实际完成内容

详细变更见 `docs/CHANGELOG_2026-09-06_intake_workspace.md`。本节只保留当前 AI 需要的结论。

### 已完成

- Asia/Tokyo 时区设置与案件编号跨日测试。
- Dashboard 改为服务端聚合，避免只统计第一页。
- 顾客、公司、担当者 RemoteSelect。
- `registration_status` 普通更新只读化。
- 顾客候选匹配 API。
- 新规受付三步流程：识别、业务信息、确认创建。
- 受付事务流程：复用/创建顾客、家族、公司、案件、默认 Checklist、初始 Timeline。
- Checklist 模板 `merge` 幂等与 `replace` 模式。
- Timeline 的 `event_type`、`actor`、`metadata` 字段和自动记录基础服务。
- 支出摘要区分“期间实际残高”和“絞り込み結果 収支”。
- 相关测试文件和 migration 已加入工作区。

### 已实现但不能当作完全闭环的项目

#### 1.（已修复 2026-09-16）既存会社选择未真正绑定

`ReceptionSerializer` 已支持 `existing_company_id`；提供时复用既有 Company 并写入 Case，不再重复创建。详见 `docs/CHANGELOG_2026-09-16_p0_followup.md`。

#### 2.（已修复 2026-09-16）顾客匹配的 strong 规则已收紧

`find_customer_candidates()` 已按"氏名完全一致 + 生日一致 = strong；氏名部分一致 + 生日一致 = medium"重新分级，并将电话比较改为国际区号归一化 + 末尾8位比较。仍是启发式规则，不是完美算法——如果后续发现新的误判案例，继续在 `docs/DEVELOPMENT_PLAN.md` 里补充任务，不要直接改这里而不留记录。

#### 3.（已修复 2026-09-16）新规受付服务端幂等

`POST /api/receptions/` 已支持可选 `request_id`：新增 `api.ReceptionIdempotencyRecord` 模型记录处理状态，重复的 `request_id` 直接返回已保存的结果（不重复创建 Customer/Case），并发的相同 `request_id` 返回 `409`。前端 `ReceptionNewPage.vue` 在页面生命周期内固定发送同一个 `request_id`。这是本项目第一个"幂等键"基础设施，目前只服务于这一个接口，详见 `docs/CHANGELOG_2026-09-16_p0_followup.md` §3。

#### 4. Timeline 事件尚缺少完整测试与对象权限验证

需要确认普通用户能否读取、创建或修改其他案件的 Timeline。还要补 actor、metadata、event_type、状态变更和 Checklist 完了的测试。Timeline 手动记录与自动记录的字段约束也需要写进 API 契约。

#### 5. API 文档与响应契约需要统一

- 顾客匹配 API 返回 `{candidates: [...]}`，不是直接返回候选数组。
- `/api/companies/?search=` 是既有 API 的搜索扩展，不是全新资源。
- 既存会社已由受付 API 的 `existing_company_id` 支持；旧文档若仍写“未支持”，属于过期说明。

#### 6. Dashboard 指标需要固定业务口径

文档必须明确：

- `waiting` 当前只是 status 的临时映射；
- `active` 只统计 active registration status 且未完了的案件；
- `next_7_days` 当前不包含今天；
- `without_next_action` 只判断文本为空，不代表期限也已设置。

## 8. 未完成事项与建议优先级

详细任务清单、每项的具体文件级修改计划和执行顺序见 **`docs/DEVELOPMENT_PLAN.md`**，本节只保留高层结论，避免和该文件重复维护。

### P0：先恢复可交付性

1. ~~修复既存公司绑定或移除误导性 UI~~ —— 已完成（2026-09-16）
2. ~~收紧顾客匹配 strong 规则，修复电话规范化~~ —— 已完成（2026-09-16）
3. ~~为新规受付加入幂等保护~~ —— 已完成（2026-09-16，`docs/DEVELOPMENT_PLAN.md` P0-A3）
4. 建立 User–Employee 关系、模块动作权限和 `own`/`assigned`/`all` 数据范围，并覆盖 API、导出和文件访问（P0-A4）—— **2026-09-28 本地已实现**（分支 `codex/p0-access-control`），生产待 D1～D7
5. 建立独立 AuditLog，以及会计/私有记录的 owner 历史数据归属方案（P0-A6/A7；第一批只做 Expense）—— **本地已实现**，生产回填待 D8
6. ~~在可连接 MySQL 的环境执行全量测试~~ —— 已完成（2026-09-16，最后记录 95 tests 全通过）
7. `/media/` 未鉴权公开风险（P0-A8）—— **本地已修复**（受保护下载 + 仓库内 nginx internal/X-Accel + media 卷移出 Web 根），生产仍公开，待 D9/D10

验收标准：重复受付不会静默创建重复数据（已达成）；选中的公司、顾客、担当者全部准确落到 Case（已达成）；候选匹配不会把明显的部分姓名判成 strong（已达成）；全量测试真正执行并通过（最后记录已达成）。P0 当前还包括 A4 权限、A5 指标补测、A6 审计、A7 历史数据归属、A8 文件受保护下载，不能再按旧版“两项确认任务”理解。

2026-09-27 P0 方案依据（详见 `docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md` §9.5 与 `docs/DEVELOPMENT_PLAN.md` §2.4）：会计 `expense_change_all`/`expense_export_all` 初期只授予李，`expense_view_all` 授予李、焦、周，superuser 不自动获得任何业务权限；Case 按担当 Employee 控制；Document 继承 Case 权限。

**P0 访问控制方案**：`docs/P0_ACCESS_CONTROL_DESIGN.md`（第 2.1 版；**2026-09-28 本地已实现，生产未部署**；实现差异见其 §14，生产执行见 `docs/DEPLOY.md`）。已确认的账号映射（生产按 username 匹配，不按本地 ID）：

| username | Employee | 目标身份 | 初始业务权限要点 |
|---|---|---|---|
| `zbry6947@gmail.com`（李） | 「李」 | 唯一系统超级管理员、唯一初始 accounting_admin、受保护账号 | 全部明确业务权限；expense view/change/export_all；manage_users |
| `jiao`（焦） | 待新建「焦」 | 业务管理员（降级前仍为 superuser/staff） | expense_view_all 有；change_all/export_all 无；其他会计模块无；案件可跨担当查看，只能修改本人担当 |
| `zywwind@gmail.com`（周） | 「周」 | 业务管理员（同上） | 同焦 |
| — | 「NAING」 | 无账号 | 不处理 |
| `localdev` | 不关联 | 本地开发账号 | 生产存在并启用时部署检查失败；现在不修改 |

方案核心：

- **BusinessAccessPolicy**：只读取 `Permission` 表中通过 Group 和直接授权得到的显式权限，完全不读取 `is_superuser`；禁止在业务判定中使用 `has_perm`/`get_all_permissions`/`DjangoModelPermissions`（Django 对 active superuser 自动放行或返回全部权限）。所有 ViewSet、专用 action、导出、下载、Dashboard、图表共用同一策略和规则注册表，并由覆盖测试强制接入。Admin 和服务器维护仍用 `is_superuser`/`is_staff`。
- **受保护账号**：李通过专用表 `authentication_protected_accounts`（FK，由服务器命令管理）标识，不靠姓名，也不硬编码 ID；它的 username 不能经 Web 修改。
- **硬性顺序**：批次 1～8（关联、审计与受保护账号、策略与 Expense 隔离、回填、数据范围、受保护下载、nginx 切换、全矩阵和恢复演练）全部通过后，才在批次 9 单独把焦、周改为 `is_superuser=False`、`is_staff=False`。任何时候都必须保证李能登录并恢复其他账号。
- **/media/**：不采用“任何登录用户可下载”的过渡方案；下载接口必须先完成对象范围、担当或 `document_download_all`、路径安全、审计和四类账号测试，才能切换 nginx。审计动作为 `download_denied`/`download_authorized`/`download_started`，不记录 completed。
- **ProtectedAccount 两阶段启用**（方案 §3.3）：阶段 A 建表和命令，Admin 保护暂不强制，注册李并验证登录、Admin 和恢复命令；阶段 B 显式开启 `PROTECTED_ADMIN_ENFORCEMENT`，Admin 只允许 ProtectedAccount。阶段 B 后保护表为空时，生产部署检查失败，Admin 不退回“允许所有 superuser”，服务器命令仍能注册和恢复李。
- **localdev**：生产发现时先只读报告，批准后只能停用，不自动删除；部署检查先 warning，确认停用后改为 enforce。
- **策略白名单**：受控模型只允许在策略内部、migration、management command、测试和 Admin 中直接查询；ViewSet、Dashboard、导出、图表、余额、copy-expenses 一律经过策略。
- **需用户单独批准的数据操作**：D1～D12，见方案 §12（D4 为阶段 A 注册李，D5 为阶段 B 开启 enforcement，D12 为 localdev 停用）。生产执行顺序以 `docs/DEPLOY.md` 的 21 步为准（D1 在旧系统上只读执行 → 维护模式 → 备份 → `migrate --plan` → `migrate` → D2～D7 → 启动新后端 → …）。
- **受控关联规则**（2026-09-28 稳定化修正）：接收既有 Customer/Company ID 的入口一律执行 `PartyRule.check_link`，包括 Case、受付、家族、公司职员、代表者。对象有其他担当者或**未分配**的进行中案件时返回 403，只有 `customer_link_all` / `company_link_all`（李）可以关联，并写 `cross_scope_link` 审计。
- **未立案顾客**：普通用户只能看到姓名、フリガナ、生年月日、国籍、登记时间、遮罩后的电话和邮箱；只有李能看完整资料。
- **生产诊断**：只保留 `/api/health/`、`/api/readiness/`；其余诊断、调试、seed 都只在开发环境注册。
- 以上结构已在分支 `codex/p0-access-control` 本地实现并有测试；生产数据库尚未应用，账号关联/角色/回填/nginx 切换均未执行。

### P1：完成案件工作台

**2026-09-28 本地已实现**：分支 `codex/p1-case-workspace`（独立 worktree `../0629code-p1`，基于 P0 最新提交 `be0e419`，未推送、未部署）。详见 `docs/CHANGELOG_2026-09-28_p1_case_workspace.md`。要点：

- Case 新增 `work_status`（active/waiting，**与 13 个进捗 status 相互独立**）、`waiting_*`，以及 `next_action_assignee`、`next_action_blocked_reason`、`next_action_completed_at/by`（migration `cases/0018`）；Checklist 新增 `received_at`、`document`（`cases/0019`）。
- 这些字段只能通过 `apps/cases/work_service.py` 修改（`select_for_update` 事务 + Timeline + AuditLog），通用 PATCH 下为只读；接口为 `cases/{id}/next-action/`、`next-action/complete/`、`waiting/start/`、`waiting/end/`、`payment-note/`、`case-checklist-items/{id}/receive/`、`GET /api/workbench/today/`。
- 权限沿用 P0 的 BusinessAccessPolicy：专用动作都按「变更」判定；Next Action 的负责人必须能查看该案件；作业台的全体视图需要 `case_view_all`。
- 入金只写 Timeline（`payment_received`，metadata 中 `accounting_record_created=false`），不创建任何会计数据。
- 后端 213 项测试、前端单元测试 6 项全部通过；前端 build 通过。**浏览器实测尚未完成**（与 P0 同样的阻断项）。

**P2 会计（分支 `codex/p2-accounting`，基于 P1 `dde7e4f`）**：Income/Expense 可以选择关联 Customer/Company/Case（`accounting/0016`）；案件侧显示会计摘要，会计侧可以跳回案件；支出分类支持搜索、手动输入、规范名建议和本人历史推荐，建议不会自动改写数据；报销仍是简单登记，owner 隔离不变。「精算済み」UI 已废止：`is_reimbursed`（精算済み）是历史兼容字段：当前 UI 已废止（新增、编辑、列表、筛选、仪表盘统计均不再显示，前端不再发送），不构成报销流程；模型字段、数据库列和历史数据保持不变，后端 API 暂时保留兼容（省略时新建为默认 False，更新时保留原值）。详见 `docs/CHANGELOG_2026-09-28_p2_accounting.md`。Visa 分支 `codex/p2-visa-import` 从本分支创建，文件分支 `codex/p2-documents` 独立推进。

原计划清单（保留作对照）：

1. Case Workspace Action Bar：対応記録、資料受領、タスク、ファイル、入金、待機、完了。
2. 统一 Next Action：负责人、期限、状态、完成、snooze、阻塞原因。
3. Waiting 机制：`work_status`、原因、开始日、预计恢复日。
4. 今日作业台：我的作业 / 全体作业，并支持直接操作。
5. Timeline 自动化：文件、入金、支出、PDF、完了、再开。
6. Checklist 与文件/资料受领联动。
7. RemoteSelect 请求竞态、错误状态和初始值的测试。

### P2：数据和财务闭环（编号与 `docs/DEVELOPMENT_PLAN.md` 一致）

- P2-C1/C2：Income/Expense 与 Customer、Company、Case 的可选 FK；从 Case 查看账务，从账务回到 Case。
- P2-C3：归档完善：`archived_by`、理由、恢复、审计和删除限制。
- P2-C4/C5：全局搜索、关联案件、公司详情扩展。
- P2-C6：前端路由级 lazy loading，降低 bundle 大小。
- P2-C7：支出分类搜索历史、手动输入、同义词规范化建议、本人历史推荐，保存前用户确认；保留 `Expense.category` 自由文本和原始输入，不改外键、不批量清洗。
- P2-C8：个人报销按 owner 隔离，保持简单登记，不新增审核、支付或入账流程。
- P2-C9：完善现有 Checklist/Document 文件管理（上传、下载、分类、关联、元数据、替换/归档/删除审计、后端鉴权、备份恢复）；不连接或迁移 Google Drive；第一阶段不做完整版本管理。Checklist 模板内容去重与业务审阅也并入此项。
- P2-C10：Visa CSV/XLSX 导入、校验与批量 PDF。
- P2-C11：报价、契约、请求、领收帐票分别完善。

### P3：不动产业务模块

- P3-D1：确认租赁/买卖范围、法定台账字段和 `LIST.xlsx` 主表三个金额列含义（忽略 `强哥` 表）。
- P3-D2：新建独立 `real_estate` 模块、列表、详情和简易新规输入。
- P3-D3：保存期限、年度关闭、锁定、更正、权限和审计。
- P3-D4：`LIST.xlsx` 主表 dry-run、人工确认、正式迁移和对账。
- P3-D5：独立内部利润分配功能，不读取 `强哥` 表，不进入法定台账。

### 明确暂缓或等待业务决策

- 税务证明剩余 6 份 PDF 正式字段映射。
- 年金 PDF 的被扶养人详细信息数据结构。
- 真实生产数据的 family link 回填和重复 Customer 合并。
- 8/9 件案件被归入“その他”的业务分类确认。
- 清風合格通知书后续业务化。
- 客户 Portal、通知、邮件、日历、电子签名。
- Google Drive 迁移、索引或集成（本阶段明确不做）。

## 9. 推荐测试矩阵

### 数据与匹配

- 同名不同生日；
- 姓名带空格、全角半角、连字符；
- 部分姓名不应判 strong；
- 电话带连字符、国家码、末尾 7 位；
- 证件号相同但姓名不同；
- 重复受付、重复 request_id；
- FamilyMember 双向关系与旧式未关联记录。

### 时间与案件号

- JST 23:59 / 00:00；
- 月末、年末、闰年；
- today、逾期、未来 1～7 天；
- 案件编号并发冲突和跨月。

### 工作流与权限

- 非法状态跳转、强制变更理由、完了后再开；
- registration_status 不能通过普通 PATCH 绕过；
- Timeline actor / metadata / visible flag；
- 普通用户、root、未登录用户的对象访问范围；
- Portal 不得读取内部 API 的敏感字段。

### 分页与幂等

- 20、21、100、500 条客户/公司/案件；
- RemoteSelect 快速连续搜索；
- Checklist merge 重复调用；
- replace 对已完成、手动追加、模板来源项目的处理；
- 重复生成 Reminder、重复上传文件。

### 帐票与导出

- 无数据、单条、多税率、非課税、历史旧数据；
- Excel 的期间余额与筛选口径；
- PDF 汇总三行、印紙框、文件名日期和缺失必填项提示。

## 10. 本地运行与部署

### 本地

```bash
cd backend
source .venv/bin/activate
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

另开终端：

```bash
cd frontend
npm run dev -- --port 5174
```

常用验证：

```bash
cd backend
source .venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test

cd ../frontend
npm run build
```

### 生产

- 目录：`/www/wwwroot/0629code`
- env：`.env.prod`
- 前端容器：`127.0.0.1:8081:80`
- 宝塔 `/sun/` 反向代理到 `http://127.0.0.1:8081`，`proxy_pass` 末尾不要加 `/`。
- 不要占用 `8080` 或 `8090`。
- 首次或异常 axes migration 必须先 `showmigrations axes`，必要时使用 `migrate axes --fake-initial`；不要删除 axes 表或执行 `down -v`。

部署细节以 `docs/DEPLOY.md` 为准。

## 11. Migration 注意事项

本轮新增的重要 migration：

```text
backend/apps/timelines/migrations/0003_timeline_actor_timeline_event_type_timeline_metadata.py
backend/api/migrations/0001_initial.py   # api 首次注册为正式 app，含 ReceptionIdempotencyRecord
# 2026-09-28 P0（加法，不写业务数据；详见 docs/DEPLOY.md）
backend/apps/employees/migrations/0002_employee_user.py
backend/apps/authentication/migrations/0001_initial.py      # ProtectedAccount + manage_users/use_diagnostics
backend/apps/audit/migrations/0001_initial.py               # AuditLog
backend/apps/accounting/migrations/0015_expense_owner_and_business_permissions.py
backend/apps/cases/migrations/0017_alter_case_options.py    # 仅 Permission
backend/apps/customers/migrations/0009_alter_customer_options.py
backend/apps/documents/migrations/0003_alter_document_options.py
```

`api` 是本轮（2026-09-16）第一次被加入 `INSTALLED_APPS`。此前它只是路由/序列化器/视图的集合，没有 models、没有 migrations 目录。如果后续要在其它非领域归属的横切功能里加表，可以继续放在这里，但不要把领域数据（Customer/Case 等业务实体）也塞进 `api` app。

项目中还存在早期的 Checklist、Customer 加密、Company、TaxRenewal migration。特别注意 `apps/cases/migrations/0016_apply_change_template_to_case_zhang_jing.py` 会针对一条具体案件写入生产数据，部署前必须备份并只读确认案件号，不能当成普通空 migration 直接忽略。

## 12. 文档地图

| 文档 | 用途 | 使用方式 |
|---|---|---|
| `docs/AI_HANDOFF.md` | 当前唯一 AI 交接入口 | 每次任务先读 |
| `docs/SYSTEM_ARCHITECTURE.md` | 全项目唯一的架构约束（不可改变的约束、模块边界、数据所有权、策略、禁止模式） | 第二个读；任何实现不得违反 |
| `docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md` | 2026-09-26 已确认的完整业务要求、模块边界、权限和验收原则 | 读完交接文档后立即阅读；实施不得与其冲突 |
| `docs/DEVELOPMENT_PLAN.md` | 当前开发计划：任务清单 + 每项的文件级修改计划 + 执行顺序 | 决定"接下来改什么、怎么改"时读 |
| `AI_CONTEXT.md` | 产品、帐票、历史实现细节 | 需要深入背景时查对应章节 |
| `AI_TASK.md` | 历史任务日志和旧规格 | 只读相关历史，不把 Legacy 当现行需求 |
| `docs/PROJECT.md` | 产品定位、模块边界、角色 | 判断是否属于 MVP |
| `docs/DATABASE.md` | 数据模型和关系约定 | 设计 migration 前阅读 |
| `docs/CODING_RULES.md` | 编码、API、AI 协作规则 | 修改代码前阅读 |
| `docs/ROADMAP.md` | 高层 MVP 路线 | 与本文件的当前优先级对照 |
| `docs/DEPLOY.md` | 生产部署和 migration 说明 | 上线前阅读 |
| `docs/CHANGELOG_2026-09-06_intake_workspace.md` | 2026-09-06 批次详细变更列表 | 核对该批次代码 |
| `docs/CHANGELOG_2026-09-16_p0_followup.md` | 2026-09-16 批次详细变更列表 | 核对该批次代码 |
| `docs/CHANGELOG_2026-09-26_requirements.md` | 2026-09-26 需求与交接文档整理记录 | 核对本次文档变更 |
| `docs/CHANGELOG_2026-09-27_requirements_clarification.md` | 2026-09-27 报销、文件管理和利润分配范围修正 | 以此确认最新范围 |
| `docs/CHANGELOG_2026-09-27_p0_decisions_docs.md` | 2026-09-27 P0 方案依据确认与文档冲突修正 | 核对 P0 前提和 `/media/` 安全项 |
| `docs/P0_ACCESS_CONTROL_DESIGN.md` | P0 访问控制设计方案（账号映射、BusinessAccessPolicy、Expense 隔离、AuditLog、受保护下载、批次与回滚、需批准的数据操作） | 实施 P0-A4/A6/A7/A8 前必读；第 2 版，原则已通过，尚未实施 |
| `docs/CHANGELOG_2026-09-27_p0_access_design.md` | 2026-09-27 P0 方案编写记录（第 1 版） | 核对本次文档变更 |
| `docs/CHANGELOG_2026-09-27_p0_access_design_v2.md` | 2026-09-27 P0 方案第 2 版修订记录 | 核对 Q1～Q11 决定与技术修正 |
| `docs/CHANGELOG_2026-09-27_p0_docs_sync.md` | 2026-09-27 需求/DATABASE/README 同步与 ProtectedAccount 两阶段启用 | 核对本次文档变更 |
| `docs/CHANGELOG_2026-09-28_p0_access_control.md` | P0 访问控制本地实现（唯一最终 CHANGELOG） | 审查 P0 实现、migration、测试、部署与回滚 |
| `docs/CHANGELOG_2026-09-28_p1_case_workspace.md` | P1 案件工作台本地实现（P1 阶段唯一 CHANGELOG） | 审查 P1 字段、接口、Timeline/AuditLog、测试 |
| `docs/PROJECT_AUDIT_2026-09.md` | 2026-09 审查报告 | 查看数据与风险背景 |

## 13. AI 修改规则

- 先检查工作区，不覆盖用户已有修改。
- 先确认目标代码和测试，再决定是否新增抽象。
- 新增字段必须 migration；新增 API 必须更新类型、测试和本文件的 API 表。
- 修改业务口径时，同时更新实现、前端标签、测试和文档，不能只改其中一处。
- 涉及 Customer 合并、历史金额重算、生产数据 migration、批量删除时，必须先停下来请求业务确认。
- 不要因为旧文档仍提到 Task、Portal 或 Reminder 就自动恢复它们。
- 完成代码变更后至少运行相关测试、`manage.py check`、`makemigrations --check --dry-run` 和 `npm run build`；若环境阻塞，明确记录阻塞原因。
- 不要把“构建成功”写成“端到端验证通过”。

## 14. 顾客页面 CRM 化改造方案与首轮实现（2026-09-16，历史记录）

> 本章为 2026-09-16 的历史记录，保留作为设计背景。其中关于 Git 状态（落后远端、大量未提交修改）、Phase 0 合并步骤和测试数字的描述只代表当时状态；当前状态以 §3 和 §8 为准。

### 14.1 本次审计边界与结论

本次已完成：

- 刷新 GitHub 远端引用，核对本地/远端提交、工作区差异和潜在冲突；
- 对本地未提交版本执行 Django check、migration 差异检查、91 项全量测试、前端类型检查/生产构建、空白与冲突标记检查；
- 在隔离临时目录验证 `origin/main`，确认前端可构建，但远端 68 项后端测试仍有 2 failure + 2 error；
- 核对本地 14 份项目 Markdown 的相对链接和当前事实漂移；
- 阅读顾客、家族、会社、案件、Timeline 的前后端实现和相关提交历史；
- 对照 Odoo、OrangeHRM、Frappe HR、EspoCRM、Twenty 的人员主档/CRM record page 做法。

本地登录页可打开，但未提供可用测试登录态，访问 `/customers/` 会被重定向到登录页。因此本节的顾客页判断来自代码、API、样式与提交历史，不冒充已完成登录后视觉/交互验收；正式实施前应补一次带真实数据的桌面和窄屏截图审计。

### 14.2 从提交记录推断出的真实产品要求

顾客页不是通用销售 CRM，也不是另一个案件详情页。历史改动已经反复确认以下要求，后续设计必须保留：

1. **一个自然人只有一个 Customer 主档**：家族成员、公司代表、公司职员是关系，不应复制维护姓名、生日、证件和联系方式。
2. **Case 仍是业务主线**：顾客页负责“认识这个人、看清关系、进入案件”，案件进度、Checklist、下一动作的详细操作仍在 Case Workspace。
3. **新规受付是唯一首接入口**：先匹配/复用顾客，再决定是否建案件；不能在多个页面重复造人。
4. **家族成员可以独立立案**：已关联 `family_customer` 的家属必须能进入自己的顾客页并创建案件；配偶/兄弟姐妹反向关系继续自动维护。
5. **减少重复输入和重复档案**：远程搜索、候选匹配、既有公司/顾客复用是基础能力，不得退回一次拉取前 20 条的下拉框。
6. **内部事务所优先**：界面操作词以日文为主，流程适合行政书士事务所；不在此阶段加入销售漏斗、营销自动化、客户账号或复杂多租户。
7. **已有功能优先重组，不先扩表**：第一阶段先把现有 Customer、FamilyMember、Company、Case、Timeline 信息重新编排；确有业务断点时才加模型。

### 14.3 成熟产品中可借鉴、但要本地化的模式

| 来源 | 成熟做法 | 本项目采用方式 |
|---|---|---|
| [Odoo Contacts](https://www.odoo.com/documentation/saas-17.2/applications/essentials/contacts.html) | 联系人顶部用 smart buttons 汇总并跳转机会、任务、会议、单据等关联记录；联系人可归档而非直接删除 | 顾客页顶部显示案件、家族、会社等数量入口；后续采用归档/恢复，不在详情页鼓励硬删除 |
| [Odoo Chatter](https://www.odoo.com/documentation/18.0/applications/productivity/discuss/chatter.html) | 记录变更、内部备注、文件和下一活动，形成可追溯时间线 | 顾客页提供活动摘要/时间线，但先聚合既有关联案件 Timeline，不复制一套新的案件进度 |
| [OrangeHRM Employee Profile](https://help.orangehrm.com/hc/en-us/articles/41367734125977-How-to-access-the-Employee-Management) | 人员档案按 Personal、Contact、Job、Salary、More 分区；敏感区按角色可见，历史单独呈现 | 顾客个人信息按基本、联系方式、在留/证件、内部备注分组；内部人员必须能完整核对业务证件，My Number 单独保护 |
| [Frappe HR Employee](https://docs.frappe.io/hr/employee) | Employee master 是人员单一主档，联系、个人、护照、家族和履历按语义分组 | 保持 Customer 为人物主档，FamilyMember/CompanyStaff 只保存关系属性 |
| [EspoCRM Detail Layout / Stream](https://docs.espocrm.com/administration/layout-manager/) | 详情页用主面板、侧面板、关系面板和 Stream；关联记录不必把全部字段摊在主页面 | 采用“主内容 + 右侧行动/风险栏 + 分页签关系面板”，会社仅显示关系摘要并链接详情 |
| [Twenty Record Pages](https://docs.twenty.com/user-guide/layout/capabilities/record-pages) | Record page 用 Overview、Timeline、Tasks、Notes、Files 等组件组合，首页只放高价值字段 | 顾客页分 Overview / 案件 / 家族・関係 / 活動；文件、账务在真正打通后再出现，不保留“準備中”空卡 |

借鉴重点是信息架构和“记录页”的处理方式，不照搬销售机会、邮件同步、工资等不属于本项目 MVP 的能力。

### 14.4 当前顾客详情页的主要问题

1. **页面是纵向资料堆叠，不是工作入口**：基本信息、每位家族的完整字段、每家公司的完整字段、案件表和“申請書作成 準備中”全部顺序展开，用户需要长距离滚动才能找到当前最重要的案件和风险。
2. **缺少首屏摘要**：看不到当前有效案件、负责人、下一动作、临近到期证件、资料缺失和最近活动。
3. **关联会社过度展开**：顾客页直接显示公司银行账号、法人编号等完整资料；这些内容应留在公司详情页，顾客页只显示关系类型、公司名和案件关联。
4. **My Number 边界不清**：`my_number` 由通用 serializer 返回并在页面直接显示；“数据库已加密”不等于“界面访问已最小化”。在留卡号和护照号不同，它们是事务所日常核对案件所需字段，内部详情页必须完整可见。
5. **关系信息重复**：家族卡片重复展示一整套人物资料，弱化了“Customer 是唯一人物身份来源”的产品原则。
6. **状态展示不一致**：案件表直接展示后端 status code，且使用旧 `case_type` 字段；应统一使用现有日文状态映射与结构化案件种别名称。
7. **选择器仍有分页缺陷**：顾客详情的 `fetchAllCustomers()` 只取默认第一页，家族关联超过 20 人后仍可能找不到目标，违背 RemoteSelect 改造目标。
8. **详情 API 逐渐过重**：单个顾客 retrieve 内嵌全部案件和全部公司完整 serializer，数据增长后难分页、难做按需加载；列表 `cases_count` 也有逐条查询风险。
9. **无活动视角**：案件 Timeline 已存在，但顾客页没有把多个案件的最近记录汇总成“这个人最近发生了什么”。
10. **空占位增加噪音**：“申請書作成 準備中”没有可用动作，应隐藏到能力真正上线。

### 14.5 目标页面结构

桌面端使用“档案头部 + 摘要入口 + 主内容/侧栏”；窄屏自动变为单列。保持当前 SUNRISE 色板和 Element Plus，不重做整套视觉系统。

```text
顾客档案头部
  姓名 / フリガナ / 顾客ID
  在留资格、主申请人/家族标签、最后更新
  [案件を追加] [顧客情報を編集] [その他]

风险与缺失提示
  在留/护照到期、关键资料未确认、旧式未关联家族、重复候选

Smart Summary
  进行中案件 | 历史案件 | 家族 | 关联会社 | 最近活动

主内容（约 2/3）                    侧栏（约 1/3）
  Overview                           当前作业摘要
  案件                               - 最新有效案件
  家族・関係                         - 担当者
  活動                               - 下一动作/期限
                                     - 最近更新时间
```

分页签职责：

- **概要**：只展示高频字段。分为「基本情報」「連絡先」「在留・旅券」「内部メモ」；低频/敏感字段折叠，不把所有字段同时铺开。
- **案件**：进行中案件置顶，完了/归档案件折叠为历史。列使用案件番号、结构化案件种别、日文进度、担当者、下一动作/期限、更新时间；点击一行进入 Case Workspace。
- **家族・関係**：用紧凑关系行展示关系、姓名、生日、独立顾客状态、有效案件数。保留历史决定的“页面内联编辑”，一次只展开一条；不退回大弹窗。提供「顧客ページへ」「案件を作成」「関係を編集」。
- **关联会社**：在家族・関係中以摘要行展示公司名、关系来源（代表者/従業員/案件关联）和有效案件数；不显示银行信息。点击进入 Company Detail。
- **活動**：第一阶段按时间倒序聚合关联案件 Timeline，必须显示案件链接、事件类型、记录者和日期，并支持按案件筛选。是否增加“立案前顾客沟通记录”单独模型，等实际使用确认后再决定。

### 14.6 首屏优先级与交互规则

首屏必须在约 5 秒内回答五个问题：

1. 这是谁，是否可能重复？
2. 现在有没有进行中的案件？
3. 谁在负责？
4. 下一步要做什么、什么时候到期？
5. 有没有证件到期或资料缺失风险？

交互规则：

- 主要按钮固定为「案件を追加」；编辑顾客为次按钮，其余低频操作收进菜单。
- 电话和邮箱可一键复制；外部发送、邮件/LINE 自动化不在本期范围。
- 风险提示使用图标 + 文案 + 日期，不只依赖颜色。
- 空值区分「未確認」「該当なし」「未登録」；第一阶段若数据库还不能区分，先统一显示“未登録”，不要用含义模糊的 `-` 代替业务状态。
- `my_number` 不应出现在普通详情响应中；建议后续使用单独 reveal action + 单一 Django permission + 审计记录，避免引入复杂权限矩阵。
- **2026-09-16 用户明确修正**：在留卡号、护照号在内部顾客/家属/职员详情中必须完整显示，以便核对已输入内容；可提供复制操作，但不能用默认遮罩妨碍业务确认。
- 页面不再显示“準備中”占位卡；没有真实数据和动作的模块直接隐藏。

### 14.7 分阶段实施计划

#### Phase 0：先建立可合并基线（不碰顾客页）

1. 保存当前 50 个工作区变化，按 intake/workspace、P0 修复、文档拆成可回退的提交或安全分支。
2. 合并 `origin/main` 的 VISA 批量录入变更；人工合并 `backend/apps/accounting/tests.py`，保留本地会计契约修复，同时纳入远端新增 VISA 测试。
3. 合并后重新执行 check、migration、全量后端测试和前端 build。测试数预计会由本地 91 项增加，但以实际发现数为准，不硬编码结果。
4. 同步更新 `docs/DEVELOPMENT_PLAN.md` 的远端状态和测试数字；`docs/PROJECT_AUDIT_2026-09.md` 保持历史报告属性，不改写历史结论。

验收：工作区变化有安全落点；`main` 与 `origin/main` 的关系明确；合并版本后端全绿、前端可构建。

#### Phase 1：只重组现有数据，交付顾客 360° 首页

前端重点：

- 将 `CustomerDetailPage.vue` 拆为页面容器和小型展示组件，但只拆清晰边界：ProfileHeader、CustomerSummary、CustomerOverview、CustomerCases、CustomerRelationships、CustomerActivity；
- 使用现有全局 token，做两栏/单栏响应式布局与 tabs；
- 家族选择改用 `RemoteCustomerSelect`，修复第 21 条以后不可选；
- 案件状态、登记状态和案件种别统一复用现有映射，不直接显示 raw code；
- 删除“申請書作成 準備中”，公司改为摘要链接。

后端重点：

- 在顾客详情响应补充轻量 summary：进行中/历史案件数、家族数、公司数、最近活动、最新有效案件摘要；
- 对 `cases_count`、family links、related companies 做 annotation/prefetch，建立查询数测试；
- 公司摘要只返回页面需要的字段，不复用含银行信息的完整 CompanySerializer；
- 保持旧字段/API 兼容，先不删除现有 retrieve 字段，待前端切换完成后再做清理。

验收：不新增业务表也能完成新信息架构；常用动作一跳到达；100+ 顾客时选择器正常；页面不默认泄露公司银行资料。

#### Phase 2：补活动、风险和敏感信息边界

- 增加顾客活动聚合 API，按关联 Case Timeline 倒序分页；
- 将在留期限/护照期限、资料缺失、旧式 FamilyMember 未关联、可能重复客户转成可行动提示；
- My Number 改为默认不返回，设计 reveal permission 和访问审计；在留卡号、护照号继续允许内部人员完整核对；
- 评估立案前沟通是否足够多：只有确认“无 Case 也需要反复记录电话/咨询”后，才新增 CustomerInteraction；否则继续使用 Case Timeline。

验收：活动可追溯、风险可点击处理、普通页面响应不含完整 My Number。

#### Phase 3：等 Case Workspace 闭环后再接入

- 顾客侧栏展示统一 Next Action / Waiting 状态，只读摘要并跳转案件；
- 文件和账务完成 Case 外键闭环后，再增加 Documents / Accounting 摘要入口；
- 顾客归档复用项目统一归档方案，支持恢复、理由和审计；
- 客户 Portal 稳定后，再讨论顾客可见内容，不能直接复用内部顾客详情 API。

### 14.8 预定文件影响范围（实施时再确认）

| 层 | 预计文件 | 目的 |
|---|---|---|
| 前端页面 | `frontend/src/pages/CustomerDetailPage.vue` | 页面容器、数据加载、tabs、主要动作 |
| 前端组件 | `frontend/src/components/customer/*`（实施时才创建） | 只拆复用/复杂区块，避免继续形成 1000 行单文件 |
| 前端 API/类型 | `frontend/src/api/customers.ts`、`frontend/src/types/api.ts` | summary、activity、轻量关系数据契约 |
| 后端序列化 | `backend/apps/customers/serializers.py` | 顾客详情摘要、敏感字段边界、轻量关系序列化 |
| 后端查询/API | `backend/apps/customers/views.py` | annotation、prefetch、活动聚合、分页 |
| 案件/时间线 | `backend/apps/cases/*`、`backend/apps/timelines/*` | 仅在活动聚合或 Next Action 已有能力需要复用时改动 |
| 测试 | `backend/apps/customers/tests.py`、必要的前端组件测试 | 权限、查询数、排序、关系、风险、响应契约 |

第一阶段应尽量不新增 migration；如果敏感信息审计或 CustomerInteraction 最终确认需要新表，必须作为独立任务和独立 migration，不与页面重排混在一个提交。

### 14.9 测试与验收清单

- 同一 Customer 作为本人、家属、公司代表/职员时只显示一个身份主档，多条关系正确汇总；
- 家族超过 20、顾客超过 100 时仍能远程搜索并选择；
- 进行中案件优先、历史案件折叠，状态全部显示日文业务标签；
- 没有案件、只有历史案件、多个进行中案件、没有公司/家族时均有明确空状态；
- 在留期限/护照期限分别覆盖已过期、今天、30/60/90 日内、无日期；
- My Number 的列表和默认详情响应不泄露完整值；在留卡号、护照号在内部详情页完整显示且与输入值一致；
- 关联会社摘要不包含银行账号；
- 顾客详情查询数有上限，不随案件/家族数量线性增加；
- 1280px 桌面、900px、560px 以下均无横向溢出；键盘可切换 tabs，焦点可见，状态不只靠颜色；
- 登录后用真实数据截图验证首屏、家族内联编辑、案件跳转、空状态、证件完整核对和 My Number 非明文边界。

### 14.10 明确不在本轮做的事

- 不把顾客页改成销售 Lead/Opportunity Pipeline；
- 不恢复独立 Task/Reminder 页面来填充客户页；
- 不新增邮件、LINE、日历、电子签名或外部 CRM 集成；
- 不在顾客页复制 Case Checklist、完整公司资料、完整账务明细；
- 不为了“看起来像 CRM”一次性创建通用 Activity、Note、Tag、Follower、Custom Field 等抽象；
- 不在本轮继续扩大到整套视觉系统重做；当前顾客页改造仍需登录态截图和真实业务数据补做视觉验收。

### 14.11 首轮实现记录（2026-09-16）

用户确认本轮需要实际追加/修改功能后，已在**当前本地可通过测试的工作区基线**上完成 Phase 1 主体与 Phase 2 的敏感信息第一步。由于本地 `main` 仍落后 `origin/main` 2 个提交，且 `backend/apps/accounting/tests.py` 存在预判硬冲突，本轮没有直接执行 pull/merge，避免覆盖尚未整理的本地改动；远端同步仍按 14.7 Phase 0 单独处理。

已实现：

- 顾客详情改为 CRM/人员主档式 360° 工作区：档案头部、风险提示、5 个摘要入口、概要/案件/家族・关系/活动 tabs，以及右侧当前作业和数据状态栏；桌面两栏、窄屏单栏。
- 案件按“进行中优先、历史折叠”展示，统一日文状态，使用结构化案件种别、负责人、下一动作和期限；保留一键进入 Case Workspace 和新增案件。
- 家族关系保留页面内联编辑，并改用 `RemoteCustomerSelect`，不再只加载默认第一页；既有顾客与新建人物继续保持互斥，避免重复主档。
- 相关会社改为轻量关系摘要，显示代表者/従業員/案件关联、职位和进行中案件数；顾客 API 与页面不再展开银行账号、法人编号等公司敏感详情。
- 聚合该顾客所有案件最新 10 条 Timeline，显示日期、标题、案件链接、记录者和自动事件标记；当前属于首屏摘要，分页和按案件筛选留待后续。
- 在留期限、护照期限增加到期/90 日内提示。首版曾把在留卡号和护照号只显示末 4 位，后按用户反馈恢复为内部详情页完整可见，见 14.12。
- Customer 列表/详情响应不再返回 My Number 明文，只返回 `has_my_number`；FamilyMember 响应也采用同样边界。编辑框留空时不覆盖数据库中既有 My Number，解决只编辑其他资料时误清空的风险。
- 顾客详情 API 增加轻量 `summary`、`related_cases`、`related_companies`、`recent_activities` 契约；顾客列表案件数使用 annotation，避免逐条 `cases.count()`。
- 删除无实际动作的「申請書作成 準備中」占位区域；电话和邮箱增加一键复制。

主要变更文件：

- `backend/apps/customers/serializers.py`
- `backend/apps/customers/views.py`
- `backend/apps/customers/tests.py`
- `frontend/src/pages/CustomerDetailPage.vue`
- `frontend/src/pages/CustomersPage.vue`
- `frontend/src/types/api.ts`

本轮验证结果：

- 前端：`npm run build` 通过（`vue-tsc -b` + Vite production build）；仅保留既有的大 chunk 警告。
- 后端专项：`python manage.py test apps.customers.tests --verbosity 2`，9/9 通过。
- 后端全量：`python manage.py test --verbosity 1`，95/95 通过。
- 数据库：`python manage.py makemigrations --check --dry-run` 返回 `No changes detected`。
- Django：`python manage.py check` 返回 0 issues。
- 差异格式：`git diff --check` 通过。

已知待办与验收边界：

1. 当前机器没有可用的前台登录凭据，因此还没有完成登录后的真实数据截图、键盘操作和 1280/900/560px 人工视觉验收；发布前必须补做。
2. 活动目前只返回最近 10 条，还没有分页和按案件筛选；若真实顾客活动量证明需要，再按 Phase 2 增加独立 endpoint。
3. My Number 已做到默认响应不返回，但 reveal permission、单独读取动作和访问审计尚未实现；在这些能力完成前，页面只显示“登録済み/未登録”。
4. 顾客详情查询已改为轻量关系数据并复用案件缓存，但尚未写固定查询数上限测试；数据量压测和查询预算仍需补充。
5. 本轮没有创建新业务表或 migration，也没有新增销售漏斗、客户 Portal、邮件/LINE、日历或外部 CRM 集成。
6. 工作区原本已有大量未提交变更，本轮实现也尚未单独提交；合并远端前应先按文件归属整理成安全提交，尤其人工处理 accounting 测试冲突。

### 14.12 第二轮详情页修正（2026-09-16）

用户实际查看首轮结果后提出三项明确修正：家属具体资料不能被压缩掉；在留卡号和护照号必须能够确认已输入的完整值；会社基本信息和案件详情应采用与顾客详情一致的记录工作区。该反馈优先于 14.6 首版遮罩方案，已完成如下实现：

- 顾客本人「在留・旅券」恢复完整在留卡号和护照号，并提供复制；My Number 仍只显示登记状态。
- 配偶、子女及其他家属从单行摘要改为完整资料卡，直接展示姓名/カナ、生日、性别、国籍、电话、邮箱、地址、在留资格、完整在留卡号/期限、完整护照号/期限、扶养状态、My Number 登记状态和关系备注。
- 家属新建表单补充邮箱、护照号码和护照期限，确保新增后不是“能显示但不能录入”。FamilyMember API 从关联 Customer 返回邮箱和护照信息，继续不返回 My Number 明文。
- 会社详情改为统一记录工作区：会社档案头、进行中/历史案件与在职/履历摘要、概要/従業員/案件 tabs、当前案件与数据状态侧栏；従業員资料完整展示在留卡和护照；新增详情页内「会社情報を編集」，代表者使用远程顾客搜索。
- 案件详情保留原有进度ステッパー、必要资料、Timeline 和全部业务弹窗，在其上增加统一档案头、登记/进度/期限状态、4 个摘要入口、当前行动侧栏以及顾客/会社快速跳转，避免视觉统一破坏案件核心操作。

第二轮验证：前端 `npm run build` 通过；客户专项 9/9 通过；后端全量 95/95 通过；`makemigrations --check --dry-run` 无变化；`manage.py check` 0 issues。

### 14.13 家族关系入口修正与后续数据类型讨论（2026-09-16）

用户进一步确认：顾客详情中的配偶、子女等家族人物不一定是本事务所意义上的“客户”，而且家族卡片中的「顧客ページへ」既无必要，在部分数据状态下也无法正常使用。因此已做以下修正：

- 删除家族资料卡中的「顧客ページへ」链接，不再把家族关系强制表达为客户页面入口。
- `family_customer` 已有关联时仅显示中性的「人物情報連携済み」状态；未关联的历史行显示「旧形式データ」。这两个标签只说明资料来源，不代表该人物已经成为业务客户。
- 家族资料卡继续直接展示用于业务确认的完整人物、在留和旅券信息；关系编辑与删除操作保留。
- 当前仍保留后端既有 `FamilyMember.family_customer -> Customer` 数据结构，以避免在数据类型方案尚未讨论清楚前进行 migration 或破坏既有案件/关系数据。

后续讨论重点应放在“人物主档”和“业务客户身份”是否需要拆分：例如独立 Person 主档、Customer/Applicant 角色、FamilyRelationship 关系表，以及 CompanyStaff/Representative 如何复用同一 Person。用户确认数据类型方案之前，不主动进行模型拆分或迁移。

## 15. 2026-09-26 新开发要求与 2026-09-27 修正摘要

详细、具有约束力的需求见 `docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md`。本节只保留接手时必须知道的摘要，不能代替完整文档。

### 15.1 已确认原则

- 尽可能保持当前大结构；各业务模块独立保留，通过关系、摘要和跳转协作，不合并成一个万能模块。
- Case 继续是行政书士案件主线；保留 13 个状态、受付、Checklist、Timeline、Document、Task、Reminder 和 Portal 方向。
- 会计模块独立保留，只做内部细微调整；不得把“精算不常用”理解成删除会计。
- 新增内部多用户权限、记录所有权和 AuditLog。普通用户 A 默认不得查看或修改用户 B 的私有业务数据；跨用户查看、修改和导出分别授权。个人报销不设审批流程。
- 建立 User–Employee 明确关系。前端隐藏不能代替后端 queryset、对象、导出和文件权限。
- 支出分类支持搜索、手动输入和基于本人历史的本地推荐；推荐结果必须由用户确认。
- 个人报销按人员隔离；现有 Expense 已确认全部属于当前用户本人。报销只做简单登记，保持现状，不新增提交、审核、批准、支付或入账流程。授权会计管理员才能跨人员查看/筛选，且 `view_all`、`change_all`、`export_all` 分开。
- 材料管理优先扩展现有 Case Checklist + Document，只完善本系统自己的上传、下载、关联、归档、权限和审计。本阶段不迁移、不索引、不连接 Google Drive；第一阶段不做完整版本管理（版本树/比较/恢复）。
- Visa 返签表保留当前模块位置，主流程改为上传 CSV/XLSX、列映射、预览校验、批量生成 PDF、ZIP 和错误报告。
- 报价书、契约书、请求书、领收书各自保留独立状态和编号，可在统一帐票入口及案件摘要中查看。
- 新增独立 `real_estate` 领域；采用列表总览、单笔工作台和简易新规输入，并满足宅建业法台账、保存期限、锁定和更正审计要求。
- `/Users/tatsuya/Downloads/LIST.xlsx` 的主表作为待迁移源数据；三个相近金额字段含义未确认前不得自动合并。`强哥` 工作表已确认无用，完全忽略。内部利润分配作为新功能独立设计，不复用该表数据，也不写入法定台账。

### 15.2 计划与当前实现的边界

- 以上为已确认需求，尚未实施，不能在界面说明或交接中写成已完成功能。
- 2026-09-26 至 2026-09-27 只更新文档；2026-09-28 在分支 `codex/p0-access-control` 实现了 P0（模型、API、前端、仓库内 nginx/compose、migration、测试），未部署生产。2026-09-27 仅对本地数据库执行了只读查询（User/Employee 清单、is_staff、Group/个别权限数量、Expense 条数和日期范围；不含认证秘密），未写入任何数据，也未修改任何账号。
- 早期文档中“暂不设计复杂权限矩阵”“任何登录用户可访问全部对象”的规划已被本次需求覆盖；实现前仍需设计最小可扩展的权限和历史数据迁移方案。
- 清理残留代码必须先做引用、数据和 Git 历史核对；不得删除整个旧模块或任何 migration。

### 15.3 接手后的第一步

1. 先确认 `git status` 和当前分支，避免覆盖用户修改。
2. 阅读本文件、完整需求文档和开发计划。
3. 开始写代码前，先把本次任务对应的权限、数据所有权、migration、测试和回滚范围写成小方案。
4. 若任务涉及需求文档 §13 的未决问题，必须先向用户确认，不得自行猜测。
5. 每个开发批次结束必须更新本文件；交接文档未更新，不视为完成。

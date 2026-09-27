# SUNRISE 系统架构约束

更新时间：2026-09-27
地位：**全项目唯一的架构约束文档**。任何实现、重构、新模块都不得违反本文件；与本文件冲突的代码或方案必须先报告，不得直接实施。

## 0. 文档优先级（固定）

1. `docs/AI_HANDOFF.md`：当前状态和入口
2. `docs/SYSTEM_ARCHITECTURE.md`（本文件）：不可违反的架构约束
3. `docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md`：业务需求
4. `docs/DEVELOPMENT_PLAN.md`：实施顺序
5. `docs/DATABASE.md`：已实现与计划中的数据结构
6. `docs/CHANGELOG_*.md`：历史记录

代码、migration 和测试是“已经实现了什么”的事实依据；上述文档是“应该如何继续”的依据。`docs/P0_ACCESS_CONTROL_DESIGN.md` 是 P0 的详细设计，从属于本文件。

## 1. 不可改变的约束

1. 保持现有项目大结构（Django `backend/` + Vue `frontend/` + `docs/`，app 按业务领域划分）。
2. 各模块独立，不合并成万能模块、万能页面或万能数据表。
3. Case 是行政书士案件主线，但不吞并其他领域。
4. 会计（`apps/accounting`）独立保留。
5. 报销（Expense）只做简单登记，没有提交、审核、批准、支付、入账流程。
6. 文件只由本系统管理，不连接、不索引、不迁移 Google Drive。
7. Visa 返签表留在 `accounting/vouchers`。
8. 不动产使用独立的 `real_estate` app。
9. 内部利润分配属于不动产的受限子功能。
10. `LIST.xlsx` 的「强哥」工作表完全忽略，不分析、不映射、不迁移。
11. Task、Reminder、Document、Portal 以及所有 migration 不得擅自删除。
12. 普通用户不能修改其他用户的数据。
13. 权限必须在后端执行。
14. superuser 不自动获得业务数据权限。
15. Timeline 记录业务进展，AuditLog 记录系统访问和修改。
16. 前端隐藏按钮不能代替权限控制。

## 2. 项目定位与非目标

**定位**：日本行政书士事务所内部使用的业务管理系统。以案件生命周期为主线，会计、帐票、文件、不动产作为独立领域协作。它是内部多用户系统，同一个数据库，用权限和数据范围隔离不同员工的数据。

**非目标**：多租户 SaaS、客户账号体系、通用 OA、通用财务软件、在线支付、电子签名、邮件或 LINE 自动化、复杂审批流、多层组织树或可编程权限平台、Google Drive 集成、移动 App。

## 3. 模块职责

### 3.1 后端 Django app

| app | 职责 | 状态 |
|---|---|---|
| `apps/authentication` | 登录、账号管理、ProtectedAccount、BusinessAccessPolicy、权限快照 | 已有；P0 扩展 |
| `apps/employees` | 业务担当者（Employee），与 User 一对一 | 已有；P0 增加 `user` |
| `apps/customers` | 自然人主档、家族关系、身份匹配 | 已有 |
| `apps/companies` | 法人主档、公司职员 | 已有 |
| `apps/cases` | 案件、状态机、Checklist 及其模板 | 已有 |
| `apps/timelines` | 案件业务进展记录（只追加） | 已有 |
| `apps/documents` | 系统内案件文件、受保护下载 | 已有；P0 增加受保护下载 |
| `apps/tasks`、`apps/reminders` | 历史任务、提醒（前端部分隐藏，保留） | 已有 |
| `apps/accounting` | 支出（Expense）、收入、车辆、项目收支、帐票、Visa、税务证明、清風 | 已有 |
| `apps/audit` | 系统 AuditLog | P0 新增 |
| `api` | 路由聚合、Dashboard、Reception 等横切接口，以及横切表（幂等记录） | 已有 |
| `api/portal` | 客户 Portal API（未实现，保留） | 占位 |
| `real_estate` | 不动产交易、法定台账、内部利润分配（受限） | P3 新增 |

### 3.2 前端模块（`frontend/src`）

- `pages/`：按领域划分的页面（Dashboard、Reception、Cases、Customers、Companies、Employees、Documents、accounting/*、Vouchers、Settings）。
- `api/`：与后端资源一一对应的 Axios 封装。
- `components/`：可复用组件（如 RemoteSelect）。
- `stores/`：登录状态和当前用户的业务权限，只用于显示和隐藏。
- 前端只负责展示和交互，任何可见性判断都不能作为安全依据。

## 4. 模块依赖方向

```text
authentication / audit      ← 所有业务模块都可以依赖（权限策略、审计写入）
employees                   ← cases、accounting、real_estate
customers / companies       ← cases、accounting、real_estate（只引用主档，不复制）
cases                       ← timelines、documents、tasks、reminders（子资源）
cases（只读摘要）            ← accounting、real_estate 可通过可选 FK 关联
api                         → 聚合各模块，不被领域模块依赖
```

- 领域模块之间只能通过 FK、只读摘要或 service 函数协作，不能直接改写对方的内部状态。
- `authentication` 和 `audit` 不能反向依赖业务模块的具体模型：策略规则表集中在 `apps/authentication/access_rules.py`，模型在函数内部延迟导入，避免循环依赖。
- 前端页面不能跨领域直接调用另一个领域的写接口来“顺便”修改数据。

## 5. 数据所有权

| 领域对象 | 所有权依据 | 普通用户 | 跨人员 |
|---|---|---|---|
| Case 及子资源（Checklist、Timeline、Document、Task、Reminder） | `Case.responsible_employee`（担当），不用 owner | 只能查看、修改自己担当的 | `case_view_all` 查看；`case_change_all` 修改（含无担当案件） |
| Customer / Company | 通过关联 Case 的担当推导；主档共享 | 可做防重复的最小搜索；详情限本人担当范围 | `customer_view_all` 查看非敏感详情；敏感证件需 `view_sensitive_identity` |
| Expense（报销） | `owner`（后端强制写入） | 只能查看、修改自己的 | `expense_view_all` / `expense_change_all` / `expense_export_all` 三项分开 |
| 会计其他模块（收入、车辆、项目、帐票、Visa、税务、清風） | 模块级权限（P0 不做记录级 owner） | 需要对应的 `use_*` 模块权限 | 同左 |
| Document | 继承父 Case | 下载限本人担当 | `document_download_all` |
| RealEstate（P3） | 独立规则，P3 设计 | — | 内部利润分配仅限明确授权者 |

## 6. BusinessAccessPolicy

- 实现位置：`apps/authentication/access_policy.py`（策略）+ `access_rules.py`（每个资源的规则）。
- **只读取显式授权**：权限来自 `Permission` 表中通过 Group 和直接授权获得的记录，**从不读取 `is_superuser`**。
- 禁止在业务判定中使用 `User.has_perm()`、`has_perms()`、`get_all_permissions()`、`DjangoModelPermissions`。原因：Django 对 active superuser 自动放行，或返回全部权限。
- 所有业务入口都经过同一个策略：DRF ViewSet（通过 Mixin）、专用 action、函数视图、导出、下载、Dashboard、图表、余额计算、跨资源引用。
- 先缩小 queryset，再做对象检查：范围外返回 404，范围内但缺少动作权限返回 403。
- Django Admin 和服务器维护使用 `is_superuser`/`is_staff`；开启 `PROTECTED_ADMIN_ENFORCEMENT` 后，Admin 还要求是 ProtectedAccount。
- 防遗漏：覆盖测试（每个 ViewSet 都必须声明 `access_resource` 或 `access_exempt`）+ 静态约束测试（禁止绕过策略；白名单只包括策略内部、migration、management command、测试、Admin、模型定义）。

## 7. Timeline 与 AuditLog

| | Timeline | AuditLog |
|---|---|---|
| 目的 | 案件业务进展（受付、状态变更、资料受领、对应记录） | 系统访问和修改（登录、权限变更、跨用户查看、导出、下载、拒绝） |
| 归属 | `apps/timelines`，挂在 Case 下 | `apps/audit`，独立 |
| 可见性 | 案件担当者，可选择对 Portal 可见 | 初期只有受保护账号（李）可见 |
| 修改 | 只追加 | 没有任何写入、修改、删除 API；Admin 只读 |
| 混用 | 禁止把审计写进 Timeline，也禁止把业务进展写进 AuditLog | 同左 |

## 8. 文件存储和受保护下载

- 文件实体存放在 `MEDIA_ROOT`（Docker 为 `media_volume`），元数据存放在 `Document`。
- **没有任何公开的静态媒体 URL**：nginx 不直接暴露 `/media/`，只保留 `internal` 的 `/_protected_media/`。
- 下载和预览流程：
  - 入口：`GET /api/documents/{id}/download/`、`.../preview/`；
  - 权限：BusinessAccessPolicy 判定；
  - 路径：realpath 校验必须位于 `MEDIA_ROOT/case_documents/` 内，不拼接用户输入或文件名；
  - 审计：先写 AuditLog，再返回；
  - 发送：生产由 nginx 按 X-Accel-Redirect 发送（支持 Range），开发用 FileResponse。
- 审计动作为 `download_denied`、`download_authorized`、`download_started`，不记录 completed。
- 第一阶段不做完整版本管理；不连接 Google Drive。

## 9. API、service、ViewSet 的职责边界

- **ViewSet / 视图**：解析请求，声明 `access_resource`，调用 service，返回响应。不写权限判断逻辑，不直接用 `Model.objects` 读取受控模型。
- **access_rules / BusinessAccessPolicy**：唯一的权限和数据范围来源。
- **service**（如 `status_service.py`、`audit.services`）：业务规则、事务和 Timeline/AuditLog 写入。
- **serializer**：字段契约和校验；敏感字段遮罩按策略传入的上下文决定，不自行判断权限。
- **导出和渲染函数**（如 `excel.py`、`pdf.py`）：只接收已经缩小范围的 queryset 或数据，不自行查询受控模型。
- API 围绕资源命名，内部 API 与 Portal API 分开，列表保持分页。

## 10. migration 与历史数据

- schema 变更必须写 migration；**migration 不写入业务数据回填**（例外：Permission 行由 Django 自动生成）。
- 历史数据变更（关联账号、回填 owner、分配 Group、停用账号）一律使用管理命令，必须满足：
  - 默认 dry-run；
  - 显式 `--apply`；
  - 按 username 定位账号，不按数据库 ID；
  - 提供 `--expect-count` 或打印差异后再确认；
  - 输出 ID 清单；
  - 写 AuditLog；
  - 可以按清单回滚。
- 生产数据操作（`P0_ACCESS_CONTROL_DESIGN.md` §12 的 D1～D12）必须由用户单独批准。
- 不删除 migration；不删除账号、文件或历史数据（删除需要单独批准，并提供恢复办法）。
- `apps/cases/migrations/0016_...zhang_jing.py` 含有针对具体数据的写入，部署前必须备份并确认。

## 11. 禁止出现的架构模式

- 在 ViewSet 或视图中零散写 `if user.is_superuser` / `has_perm` 来做业务判定。
- 用前端隐藏按钮或菜单代替后端权限。
- 把多个领域合并成一张带 `type` 字段的万能表或一个万能流程（例如把报价、契约、请求、领收合并）。
- 把审计写进 Timeline，或把业务进展写进 AuditLog。
- 公开静态媒体 URL，或根据用户输入拼接文件路径。
- 在 migration 中回填生产业务数据。
- 按显示姓名或硬编码数据库 ID 识别特权账号。
- 为 Expense 引入审批状态机。
- 在 Case 中复制会计明细、完整公司资料或不动产数据。
- 生产环境开放演示数据生成、seed 或调试端点。
- 为了“统一”而重写或合并现有模块。

## 12. P0～P3 实施顺序

- **P0**：权限和数据归属基础。包括 User–Employee、ProtectedAccount、BusinessAccessPolicy、AuditLog、Expense 隔离、Case/Customer/Company/Document 数据范围、受保护下载、禁用危险端点、快照和恢复、权限矩阵测试。详见 `P0_ACCESS_CONTROL_DESIGN.md`。
- **P1**：案件工作台（Action Bar、Next Action、Waiting、今日作业台、Timeline 自动化、Checklist/Document 联动、RemoteSelect 测试）。
- **P2**：现有模块增强（会计与案件关联、归档、全局搜索、lazy loading、分类推荐、报销保持简单登记、Document 文件管理、Visa CSV/XLSX、报价/契约/请求/领收）。
- **P3**：不动产 `real_estate`（法定台账、保存期限、`LIST.xlsx` 主表迁移、内部利润分配）。

不得为了赶 P2/P3 而跳过 P0。

## 13. 新模块进入项目的判断标准

1. **是否是新的业务领域？** 如果只是现有领域的扩展，应放进现有 app（例如材料管理扩展 Checklist + Document，不新建 `materials`）。
2. **是否有独立的生命周期、状态和权限？** 有，才考虑新 app（例如不动产）。
3. **数据所有权是否明确？** 必须在本文件 §5 登记所有权依据，并在 `access_rules.py` 登记规则。
4. **与 Case 的关系**：只能通过可选 FK 和只读摘要，不能让 Case 吞并它。
5. **审计**：列出需要写 AuditLog 的操作。
6. **文件**：如需存储文件，必须使用受保护下载，不得开放公开 URL。
7. **历史数据**：如需导入，必须提供 dry-run、逐行结果、可重复执行和回滚。
8. **文档**：新增模块时同步更新本文件、`DATABASE.md`、`DEVELOPMENT_PLAN.md` 和 `AI_HANDOFF.md`。

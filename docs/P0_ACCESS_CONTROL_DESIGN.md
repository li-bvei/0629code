# P0 访问控制设计方案（User–Employee / BusinessAccessPolicy / Expense 隔离 / AuditLog / 受保护文件下载）

更新时间：2026-09-27（第 2.1 版：在第 2 版基础上增加 ProtectedAccount 两阶段启用、localdev 两阶段检查、策略白名单、全文状态标记）
状态：**方案原则已通过；本版为修订稿，尚未实施**
对应任务：`docs/DEVELOPMENT_PLAN.md` P0-A4、P0-A6、P0-A7、P0-A8
上位需求：`docs/DEVELOPMENT_REQUIREMENTS_2026-09-26.md` §4.4、§5.3、§9、§10

> 本文件只描述设计与实施顺序。编写本文件时没有修改代码、数据库、nginx 或任何账号，没有创建 migration。
> 所有数据操作（生产只读核对、建立关联、创建 Employee、注册受保护账号、分配 Group、回填 Expense、切换 nginx、降级或停用账号）都列在 §12，每一项都要在对应批次由用户单独批准后执行。

**状态标记（全文通用）**：

- 【已实现】当前代码或数据库中已经存在（只出现在 §1 现状盘点）。
- 【已确认·未实现】用户已确认的设计，当前代码和数据库中**不存在**。除 §1 外，本文件描述的 BusinessAccessPolicy、ProtectedAccount、Employee.user、Expense owner、AuditLog、Group、权限、受保护下载、部署检查全部属于此类。
- 【待批准数据操作】§12 的 D1～D12，未经用户逐项批准不得执行。

---

## 1. 现状盘点（2026-09-27 只读核对）【已实现·现状】

### 1.1 账号与员工（**本地库** `gyoseishoshi_erp@127.0.0.1`，不代表生产）

| User ID（本地） | username | 姓名 | is_active | is_staff | is_superuser | Group | 个别权限 |
|---|---|---|---|---|---|---|---|
| 1 | zbry6947@gmail.com | 李 | ✅ | ✅ | ✅ | 无 | 0 |
| 2 | jiao | 焦 | ✅ | ✅ | ✅ | 无 | 0 |
| 3 | zywwind@gmail.com | 周 | ✅ | ✅ | ✅ | 无 | 0 |
| 4 | localdev | — | ✅ | ✅ | ✅ | 无 | 0 |

| Employee ID（本地） | 姓名 | is_active | 关联 User |
|---|---|---|---|
| 1 | 李 | ✅ | 无（模型无字段） |
| 2 | 周 | ✅ | 无 |
| 3 | NAING | ✅ | 无 |

- 系统中没有任何 Django Group，也没有个别权限分配。
- 本地 Expense 1,300 条（2023-12-12 ～ 2026-07-31），**只作为本地统计，不代表生产数量**。
- 生产映射一律按 **username + 业务身份** 匹配，不按本地 ID 映射（Q1）。

### 1.2 后端访问控制现状

- DRF 全局只有 `IsAuthenticated`，没有对象级、数据范围或模块权限。
- 唯一的自定义权限是 `IsSuperUser`，只用于账号管理 `SystemUserViewSet`。
- `SystemUserUpdateSerializer` 只保护“最后一个 superuser 不能降级”。**任一 superuser（焦、周、localdev）现在都可以降级、停用李，或修改李的用户名。**
- `GET /api/auth/me/` 使用 `user.get_all_permissions()`，对 superuser 会返回系统中的全部权限。
- Django Admin 对所有 `is_staff` 用户开放；目前 4 个账号都是 `is_staff=True`。
- 调试、诊断和演示端点对任意登录用户开放：`accounting/zei-pdf-position-debug/*`、`accounting/visa-position-debug/*`、`accounting/visa-form-field*`、`accounting/tax-renewal-pdf-diagnostics/*`、`accounting/seifu-notice-pdf/*`（模板调试部分）、`case-checklist-demo/seed/`、`*/seed-standard/`。

### 1.3 Expense 的全部读取路径

| 位置 | 用途 | 现状 |
|---|---|---|
| `ExpenseViewSet` CRUD | 支出记录 | `Expense.objects.all()` |
| `ExpenseViewSet.excel` | Excel 导出 | 期首余额来自全表 |
| `ExpenseViewSet.summary` | 汇总、余额 | 余额来自全表 |
| `compute_period_balance_context()` | 期首余额、期间收支 | `IncomeSource` 全表 − `Expense` 全表 |
| `build_expense_chart()` | 会计 Dashboard 图表 | 全表聚合 |
| `dashboard`（`accounting/dashboard/`） | 会计首页 | 全表合计、最近记录 |
| `AccountingProjectViewSet.copy_expenses` | 复制到项目 | 按请求中的 ID 取数，**可以引用他人记录** |
| `AccountingProjectExpense.source_expense` | 项目支出来源 | 可间接暴露 |
| Django Admin | 后台 | 全部 |

### 1.4 Case / Customer / Document 现状

- `Case.responsible_employee`（FK → Employee，可空）是现有担当字段。受付接口 `responsible_employee` 为可选，目前可以生成无担当案件。
- 子资源 `CaseChecklistItem`、`Timeline`、`Document`、`Task`、`Reminder`、`TaxRenewalVoucherRecord.case` 都只按 `?case=` 过滤，没有权限判断。
- Customer/Company 没有担当或所有者字段。搜索和 match 返回完整序列化数据（My Number 已只返回 `has_my_number`）。
- `Document.case` 为必填（CASCADE）。`DocumentSerializer.file`/`file_url` 返回 `/media/case_documents/<原始文件名>`；前端目前没有渲染下载链接。
- `media_volume` 挂载到 backend `/app/media`，并以只读方式挂载到 frontend nginx。`nginx/default.conf` 中的 `/media/`、`/sun/media/` 直接 alias，**不经过鉴权**（P0-A8）。
- 其它 PDF 都是即时生成、流式返回，不写入 `MEDIA_ROOT`。它们是否在内容中嵌入了 `/media/` URL，在批次 7 前核对（§8.4）。

---

## 2. 账号映射与角色（用户确认）【已确认·未实现】

| username（生产按此匹配） | Employee | 目标身份 | 初始业务权限 |
|---|---|---|---|
| `zbry6947@gmail.com`（李） | 「李」 | **唯一**系统超级管理员；**唯一**初始 `accounting_admin`；受保护账号 | 全部明确业务权限：`expense_view_all`、`expense_change_all`、`expense_export_all`、全部会计/帐票/Visa/税务模块、`manage_users`、`case_*_all`、敏感字段和文件、审计查看、诊断 |
| `jiao`（焦） | 待新建「焦」 | 业务管理员（降级批次前仍为 superuser/staff） | `expense_view_all` ✅；`expense_change_all` ❌；`expense_export_all` ❌；其他会计模块 ❌；Case/Customer 可跨担当查看，只能修改本人担当的 |
| `zywwind@gmail.com`（周） | 现有「周」 | 业务管理员（同上） | 同焦 |
| —（NAING） | 现有「NAING」 | 无账号 | 不处理；仍可作为案件担当被选择 |
| `localdev` | 不关联 | 本地开发账号 | 不授予任何生产业务权限；生产部署检查先 warning、确认停用后改为强制失败（§2.2） |

### 2.1 角色 = Group（权限只通过 Group 或直接授权获得）

| Group | 成员（初始） | 权限 |
|---|---|---|
| `business_admin` | 焦、周、李 | `cases.use_cases`、`cases.case_view_all`、`customers.customer_view_all`（不含敏感字段）、`documents.document_view_all`（只看元数据，不含下载） |
| `expense_viewer` | 焦、周 | `accounting.use_expense`、`accounting.expense_view_all` |
| `staff` | （以后的普通员工） | `cases.use_cases`、`accounting.use_expense` |
| `accounting_admin` | 李 | `accounting.use_expense` + `expense_view_all`/`change_all`/`export_all` + 全部 `accounting.use_*` 模块 |
| `system_admin` | 李 | `authentication.manage_users`、`audit.view_auditlog`、`system.use_diagnostics`、`cases.case_change_all`、`customers.view_sensitive_identity`、`documents.document_download_all` |

- Group 按模块拆分，一个人可以同时属于多个 Group。以后给某人开放某个会计模块时，只需增加对应的 `use_*` 权限，不改动其他模块。
- 业务管理员的 view_all **不包含**：My Number 明文、越权查看敏感证件、越权下载文件、任何导出。
- Expense 不设审批、支付、入账权限。

### 2.2 localdev【已确认·未实现】

- 只允许存在于本地开发环境，不关联 Employee，不授予任何生产业务权限；本方案不修改该账号。
- 生产发现 localdev 时的处理（D12）：
  1. 先只读报告（是否存在、`is_active`、最后登录时间）；
  2. 经用户批准后**只能停用**（`is_active=False`），不自动删除；
  3. 删除账号是另一项未来的数据操作，需要再次单独批准。
- 部署检查 `check_access_config` 对 localdev 分两阶段：
  - **阶段 1（初始）**：生产中存在并启用的 localdev 只输出 **warning**，不阻断部署；
  - **阶段 2**：用户确认生产的 localdev 已不存在或已停用后，将配置 `LOCALDEV_CHECK_MODE` 从 `warn` 改为 `enforce`，此后存在并启用即部署失败。
  - 切换到阶段 2 本身是一次配置变更，记录在交接文档中。

---

## 3. 李的受保护身份【已确认·未实现】

### 3.1 稳定标识

**不使用显示姓名，也不在代码中硬编码数据库 ID。** 采用专用关联表：

```text
authentication_protected_accounts
  user_id     OneToOne → auth.User（PROTECT）
  reason      Char（例："唯一系统超级管理员"）
  created_at  DateTime
```

- 表中的行只能用服务器命令 `protect_account --username <u> --apply` 创建或删除。API 和 Admin 都只读，任何 Web 端操作都不能增删。
- 关联以 FK 保存，与用户名、显示姓名无关，**不在代码或配置中固定任何数据库 ID**。生产库 ID 与本地不同也没有影响，因为执行命令时按 username 解析到当前库的用户。
- 部署检查 `check_access_config` 的要求和启用时机见 §3.3。

### 3.2 受保护账号规则

- 除受保护账号本人外，任何人都不能停用、降级它，不能修改它的用户名或 `is_staff`，不能重置它的密码，也不能把它移出 `system_admin` 或 `accounting_admin`。违反时返回 400/403，并写 `result=denied` 的 AuditLog。
- “最后一个 superuser 不能降级”的保护继续保留。
- **用户名变更规则**：受保护账号的 username 不能通过 Web API 修改，本人也不行（防止会话被劫持后改名）。确需改名时，使用服务器命令 `rename_protected_account --from <old> --to <new>`：先打印差异并要求确认，再写 AuditLog。受保护关联靠 FK 自动保留，不需要改配置。
- 恢复手段（break-glass，只在服务器命令行执行）：

```bash
docker compose exec backend python manage.py changepassword zbry6947@gmail.com
docker compose exec backend python manage.py axes_reset_username zbry6947@gmail.com
docker compose exec backend python manage.py restore_access_snapshot <snapshot.json> --user zbry6947@gmail.com
docker compose exec backend python manage.py protect_account --username zbry6947@gmail.com --apply
```

这些命令只依赖服务器 shell，不经过 Web，也不受 protected-admin enforcement 的限制，**任何阶段都可用**。

### 3.3 两阶段启用（避免保护表为空时锁死后台）

配置开关 `PROTECTED_ADMIN_ENFORCEMENT`（默认 `False`）。

**阶段 A：建表，但不强制**

1. 部署 ProtectedAccount 表、管理命令（`protect_account`、`rename_protected_account`）、账号管理 API 的受保护账号规则（§3.2）。
2. `PROTECTED_ADMIN_ENFORCEMENT=False`：Django Admin 的准入**保持现状**（`is_staff`）。
3. 经批准（D4）后，先导出权限快照并备份账号相关表，再用服务器命令把李注册为 ProtectedAccount。
4. 验证：李能登录前台、进入 Django Admin；在服务器上演练 `changepassword`（可在测试库上做）、`axes_reset_username`、`restore_access_snapshot --dry-run`。
5. 部署检查在阶段 A 的行为：生产中 ProtectedAccount 为空时输出 **warning** 并提示运行 `protect_account`。这是注册李之前唯一允许的状态，注册完成后即进入阶段 B 的检查标准。

**阶段 B：显式开启强制**

1. 经批准（D5）后，把配置改为 `PROTECTED_ADMIN_ENFORCEMENT=True` 并重新部署。
2. Django Admin 的 `has_permission` 改为：`is_active` + `is_staff` + 属于 ProtectedAccount。焦、周即使仍是 superuser，也无法进入 Admin。
3. 再次验证李的前台登录、Admin 登录和服务器恢复命令。
4. 回滚：把开关改回 `False` 并重新部署即可，不涉及数据变更。

**ProtectedAccount 为空时（阶段 B 或之后）**：

- 生产部署检查 `check_access_config` **失败**（非零退出码），阻止部署继续。
- Admin 准入**不会**退回为“允许所有 superuser”：enforcement 开启且表为空时，Admin 拒绝所有人，同时在日志和错误页提示使用服务器命令恢复。
- 服务器管理命令（`protect_account`、`changepassword`、`restore_access_snapshot`）始终可用，用于重新注册和恢复李。
- 部署检查的完整条件：至少存在一个 ProtectedAccount，且该账号 `is_active=True`、`is_superuser=True`，并显式持有 `manage_users`（后一项从批次 3 开始检查，批次 2 时权限体系尚未建立）。

---

## 4. BusinessAccessPolicy（统一业务权限策略）【已确认·未实现】

### 4.1 为什么不能用 Django 默认权限 API

Django 4.2 源码行为（已核对）：

- `User.has_perm()`：`if self.is_active and self.is_superuser: return True`，直接放行。
- `ModelBackend._get_permissions()`（`get_user_permissions`、`get_group_permissions`、`get_all_permissions` 都经过它）：`if user_obj.is_superuser: perms = Permission.objects.all()`，对 superuser 返回全部权限。
- DRF 的 `DjangoModelPermissions` 内部调用 `has_perms()`，行为相同。

因此在业务判定中**禁止使用** `has_perm`、`has_perms`、`get_all_permissions`、`get_group_permissions`、`get_user_permissions`、`DjangoModelPermissions`。

### 4.2 策略核心

新文件 `backend/apps/authentication/access_policy.py`：

```python
class BusinessAccessPolicy:
    def __init__(self, user):
        self.user = user
        self.employee = get_user_employee(user)        # user.employee 或 None
        self.codes = self._load_explicit_codes()       # 每个请求加载一次

    def _load_explicit_codes(self):
        if not (self.user and self.user.is_authenticated and self.user.is_active):
            return frozenset()
        rows = (Permission.objects
                .filter(Q(user=self.user) | Q(group__user=self.user))  # 只读显式授权
                .values_list('content_type__app_label', 'codename')
                .distinct())
        return frozenset(f'{a}.{c}' for a, c in rows)
        # 注意：完全不读取 is_superuser

    def has(self, code) -> bool
    def scope(self, resource, action, queryset) -> QuerySet   # 列表、导出、聚合
    def check_object(self, resource, action, obj) -> Decision # allow / not_found / forbidden
    def check_create(self, resource, data) -> Decision        # 创建时的归属校验
    def audit_context(self) -> dict                           # via_permission 等
```

- **资源规则注册表**：`access_rules.py` 中每个资源一条规则，例如 `ExpenseRule`、`CaseRule`、`CaseChildRule(parent='case')`、`CustomerRule`、`CompanyRule`、`DocumentRule`，以及会计其它模块的 `ModuleOnlyRule('accounting.use_income')` 等。每条规则只定义三件事：`scope_q(policy, action)`、`object_decision(policy, action, obj)`、`module_code`。
- 所有判断集中在这两个文件里，**ViewSet 中不写任何零散的权限判断**。
- **每个请求只建一次**：`request.business_policy` 由中间件或 DRF `initial()` 懒加载，同一请求内复用缓存，权限查询只执行一次。

### 4.3 接入方式（全部路径使用同一策略）

| 接入点 | 方式 |
|---|---|
| DRF ViewSet | `BusinessScopedViewSetMixin`：在类上声明 `access_resource='expense'`；`get_queryset()` 自动调用 `policy.scope(resource, 'view'/'change')`；`check_object_permissions()` 调用 `check_object`；`perform_create()` 调用 `check_create`，并由后端写入 owner、created_by 等 |
| 专用 action | 通过 `@business_action(resource, action='change'/'export'/…)` 装饰器声明动作类型，由 Mixin 统一判定 |
| 函数视图（dashboard、诊断等） | `@require_business(resource, action)` 装饰器 + `policy.scope(...)` 取数 |
| 导出（Excel） | action 类型为 `export`，规则决定范围（Expense 需要 `expense_export_all` 才能导出他人数据） |
| 下载/预览 | `DocumentRule` 的 `download` 动作 |
| Dashboard/图表/余额 | 通过 `policy.scope('expense','view', Expense.objects.all())` 取数，不直接写 `Expense.objects` |
| 跨资源引用（copy-expenses） | 引用的 ID 集合必须是 `policy.scope(...)` 结果的子集，否则整批 400 |
| `me` API | `business_permissions` 返回 `policy.codes`，不再使用 `get_all_permissions()` |

### 4.4 防遗漏机制（测试层强制）

- **覆盖测试**：遍历 `api.urls` 和 `apps.accounting.urls` 注册的所有 ViewSet 和函数视图，断言每个都声明了 `access_resource`，或显式声明了 `access_exempt='原因'`（如登录、CSRF）。新增接口时如果忘记声明，测试失败。
- **静态约束测试**：扫描后端 Python 文件：
  - 全项目禁止在业务判定中出现 `.has_perm(`、`.has_perms(`、`get_all_permissions(`、`DjangoModelPermissions`。例外只有 Django Admin 自身的内部实现，这部分不属于业务代码。
  - 对**受控模型**（P0 为 `Expense`；批次 5 起加入 `Case` 及其子资源、`Customer`、`Company`、`Document`），禁止在白名单以外直接使用 `<Model>.objects`、`<Model>._default_manager`。

**受控模型直接查询白名单**（必须逐项写出文件和理由，新增条目需在交接文档中记录）：

| 文件或路径 | 理由 |
|---|---|
| `apps/authentication/access_policy.py`、`apps/authentication/access_rules.py` | 策略内部的查询服务，本身就是范围判定的实现 |
| `apps/*/migrations/*.py` | schema 和数据迁移不经过请求上下文 |
| `apps/*/management/commands/*.py` | 服务器命令（回填、关联、快照等），自带 dry-run 和批准流程，并写 AuditLog |
| `apps/*/tests*.py`、`apps/*/tests/`、测试工厂 | 测试数据构造和断言 |
| `apps/*/admin.py` | Django Admin 的受控实现；Admin 准入由 is_staff/ProtectedAccount 控制，不属于业务 API |
| `apps/*/models.py`、模型的 Manager/QuerySet 定义 | 模型自身定义，不含业务读取入口 |

**明确不得进入白名单**：所有 ViewSet 和函数视图、Dashboard（`api/views.py`、`accounting/dashboard`）、Excel 和其他导出（`accounting/excel.py` 的调用方）、图表（`build_expense_chart`）、余额（`compute_period_balance_context`）、`copy_expenses`。这些地方的取数只能通过 `policy.scope(...)`，或接收由它产生的 queryset。像 `excel.py` 这类只负责渲染、接收 queryset 参数的函数，不得自行查询受控模型。
- **必测用例**：“只有 superuser、没有任何业务 Group 的账号”读取 Expense 列表、详情、excel、summary、dashboard、图表，结果均为空或 403/404；访问会计其他模块返回 403；访问 Case 返回 403。

### 4.5 与系统层权限的分工

| 场景 | 依据 |
|---|---|
| 业务数据：API、导出、下载、Dashboard、图表、专用 action | **只看 BusinessAccessPolicy**，不看 `is_superuser` |
| Django Admin | `is_staff`/`is_superuser`；批次 2 阶段 B 显式开启 `PROTECTED_ADMIN_ENFORCEMENT` 后，还要求是 ProtectedAccount（§3.3）。这样降级前焦、周也无法用 Admin 绕过 API，且不改动他们的账号标志 |
| 服务器维护命令 | 服务器 shell 权限 |
| 账号管理 API | `is_superuser` **且** 策略 `authentication.manage_users` **且**满足受保护账号规则 |
| 诊断端点 | 非生产环境开关 + `is_superuser` + `system.use_diagnostics`（§4.6） |

### 4.6 调试、演示、诊断端点（Q10）

- 新增 `settings.APP_ENV`（`development`/`staging`/`production`）和 `ENABLE_DEV_TOOLS`（生产强制为 False）。
- **生产完全禁用**（不注册路由，返回 404）：`case-checklist-demo/seed/`、`seed_demo_data` 相关入口，以及 PDF 坐标调试和预览类工具（`zei-pdf-position-debug/*`、`visa-position-debug/*`、`visa-form-field-mapping`、`tax-renewal-pdf-diagnostics/numbered_sample`）、`*/seed-standard/`（标准主数据导入改为服务器命令）。
- **必须保留的诊断功能**：先在批次 3 盘点，由用户确认清单。保留项要求 `is_superuser` + `system.use_diagnostics`，并写 AuditLog `diagnostic_run`；优先只在非生产环境开放。
- 前端静态调试页（`/visa-form-field-mapping.html`、`/zei-pdf-position-debug.html`）在生产的 nginx 中移除，与批次 7 一起处理。

---

## 5. 各模块数据范围规则【已确认·未实现】

动作分为 `view`、`change`（含删除、专用写 action）、`create`、`export`、`download`。**先缩小 queryset，再做对象检查**：范围外的对象返回 404（不泄露存在性）；范围内但缺少动作权限返回 403。

### 5.1 Expense

| 动作 | 仅 `use_expense` | + `expense_view_all`（焦、周） | + `expense_change_all`（李） | + `expense_export_all`（李） |
|---|---|---|---|---|
| view（list/retrieve/summary/图表/dashboard） | owner=自己 | 全部（他人只读），可按 owner 筛选 | 全部 | — |
| create | owner 由后端强制设为自己，**忽略前端传入的 owner** | 同左 | 同左（P0 不支持代他人新建） | — |
| change/delete | 仅自己 | 仅自己（他人记录 403） | 全部，并写审计 | — |
| export（excel） | 仅自己 | 仅自己（没有 export_all 时不能导出他人） | — | 全部，并写审计 |
| copy-expenses | 仅自己的 ID | 仅自己的 ID（复制属于写入项目，他人记录不行） | 全部 | — |

- `owner=NULL`（回填前的历史记录）只对 `expense_view_all` 持有者可见，只有 `expense_change_all` 持有者可以修改。
- `created_by`/`updated_by` 由后端在 create/update 时写入，前端提交的值一律忽略。
- **余额口径（Q2）**：只有同时持有 `expense_view_all` 和 `accounting.use_income`（即完整会计权限，初期只有李）的用户才显示“期首余额/实际残高”，并按全部数据计算。其他人的 summary 中余额类字段返回 `null`，只显示“我的支出合计”（或 view_all 时的“筛选结果支出合计”），Excel 也不输出期首余额和残高行。前端标签不得把个人合计写成公司余额。焦、周可以查看全部 Expense，但没有 Income 权限，所以同样不显示余额。

### 5.2 会计其它模块（Q3）

IncomeSource、VehicleUsage、AccountingProject（含 Income/Expense）、AccountingVoucher（請求書/領収書）、VisaReturnApplication/Template、TaxRenewal*、SeifuNotice*、ExpenseCategory 的写操作：各自使用独立的 `accounting.use_*` 模块权限（`ModuleOnlyRule`）。**初期只有李拥有全部**，焦、周没有，以后逐个模块单独授权。P0 期间这些模块不做记录级 owner 隔离。ExpenseCategory 的读取对 `use_expense` 开放（分类选择需要）。

### 5.3 Case 及其子资源

- `assigned` = `case.responsible_employee_id == policy.employee.id`。
- 需要 `cases.use_cases` 才能进入案件模块。
- view：assigned，或持有 `case_view_all`（焦、周、李）。
- change：assigned，或持有 `case_change_all`（只有李）。
- **担当为空（Q4）**：view 需要 `case_view_all`；change 只有 `case_change_all`（李）可以。
- **新规受付和新建案件（Q4）**：如果请求没有提供 `responsible_employee` 且提交账号已关联 Employee，后端默认设为本人。如果没有提供且提交账号**未关联** Employee，返回 400“担当者を選択してください”，不再静默生成无担当案件。这是对 `POST /api/receptions/` 和 `POST /api/cases/` 的行为变更，需要同步更新现有测试和前端提示。
- 更换担当：需要 `case_change_all`，或操作人是当前担当；写 AuditLog `case_reassign`。
- 子资源的读写一律继承父 Case。创建子资源时，目标 Case 必须在 change 范围内。
- 专用 action（change-status、change-registration-status、progress-info、regenerate-case-number、apply-checklist-template、generate-reminders）一律视为 change。
- `/api/dashboard/summary/`、`/deadlines/` 按 view 范围统计。

### 5.4 Customer / Company

- **防重复搜索（Q5）**：`GET customers/?search=`、`POST customers/match/`、`GET companies/?search=`，持有 `use_cases` 即可调用。对不在本人详情范围内的记录，使用**最小识别序列化器**：
  - Customer：id、姓名、フリガナ、生年月日、国籍、是否存在进行中案件、当前担当者名；
  - Company：id、名称、カナ、法人番号；
  - **不得包含**证件号码、地址、电话、邮箱、My Number、文件、会计信息。
- **详情范围**：Customer 的 assigned = 存在本人担当的关联 Case；Company 同理（关联 Case，或代表者、职员属于本人范围）。持有 `customer_view_all` 时可以查看全部非敏感详情。
- **证件遮罩（Q6）**：本人 assigned 范围内完整显示在留卡号和护照号。越出范围（包括业务管理员通过 view_all 查看时）遮罩为末 4 位，除非持有 `view_sensitive_identity`（只有李）。My Number 在任何普通接口都不返回明文，只返回 `has_my_number`。
- **只受付、尚未立案的顾客（Q7）**：持有 `use_cases` 的员工只能看非敏感基础信息（证件号遮罩，不显示地址和联系方式以外的敏感项，具体字段与遮罩规则在批次 5 列出后由用户确认）。完整敏感详情只有李（`view_sensitive_identity` + `customer_view_all`）能看。P1 再增加 Customer `created_by` 或明确的管理关系。
- 写入 Customer/Company：assigned 范围，或持有 `case_change_all`（李）。只受付未立案的顾客只有李可以修改，P1 引入 created_by 后再放开。

### 5.5 Document

- view（元数据列表）：父 Case 在 view 范围内。业务管理员通过 `document_view_all` 可以看到全部文件的元数据。
- **download/preview（Q8）**：父 Case 在本人 assigned 范围内，或持有 `document_download_all`（只有李）。越出本人担当范围的下载一律按敏感操作处理，必须持有 `document_download_all`，并写 AuditLog。
- 上传、替换、删除：父 Case 在 change 范围内，写 AuditLog。
- 无 Case 的文件：当前模型不允许，P0 不改变。

---

## 6. User–Employee 关联【已确认·未实现】

- Schema：在 `Employee` 上增加 `user = OneToOneField(AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='employee')`。只加可空列，回滚时删除该列。
- 数据操作用管理命令 `link_user_employee`，**不写进 migration**：
  - `--plan`：只读，按 username 列出生产的 User、Employee 和建议映射；
  - `--apply --map zbry6947@gmail.com:李 --map zywwind@gmail.com:周 --create-employee jiao:焦`：显示差异，要求确认后执行，并写 AuditLog。
- Employee 按**姓名 + 用户确认**匹配。同名多条、找不到，或已关联其他 User 时，命令拒绝执行。
- `me` 增加 `employee_id`、`employee_name`、`business_permissions`（来自策略），这些字段只用于前端显示和隐藏，不作为安全依据。

---

## 7. AuditLog【已确认·未实现】

### 7.1 位置与保护

- 新建独立 app `apps/audit`，表名 `audit_logs`，与 Timeline 分开。
- **不提供任何公开的写入、修改、删除 API**。只能由服务端 `audit.record(...)` 写入。
- Admin 只读（`has_add/change/delete_permission` 返回 False）。初期**只有李**能查看，条件是受保护账号 + `audit.view_auditlog`。
- 与业务写操作放在同一事务；下载类操作先写审计，再返回响应。
- 暂不设置自动删除。

### 7.2 字段

`id`、`occurred_at`、`user`（SET_NULL）、`username_snapshot`、`employee`（SET_NULL）、`ip`、`user_agent`（截断到 300）、`request_id`（索引）、`module`、`action`（索引）、`object_type`/`object_id`/`object_repr`（不含敏感值）、`result`（success/denied/error）、`changes`（安全差异摘要，敏感字段只记“已变更”）、`reason`、`via_permission`、`extra`（JSON：条数、过滤条件、文件大小、mode 等）。

### 7.3 动作

| 类别 | action |
|---|---|
| 认证 | `login_success`、`login_failed`、`logout` |
| 账号 | `user_create`、`user_update`（含 is_superuser/is_staff/is_active 变化）、`password_reset`、`group_change`、`roles_setup`、`user_employee_link`、`protected_account_change`、`access_snapshot_export`、`access_snapshot_restore` |
| 会计 | `expense_view_all`（结果包含他人记录时，每个请求一条）、`expense_change_other`、`expense_export`、`expense_owner_backfill` |
| 案件 | `case_reassign`、`case_change_other` |
| 文件 | `download_denied`、`download_authorized`、`download_started`、`download_error`（`extra.mode` 取 download 或 preview）；`document_upload`、`document_replace`、`document_delete` |
| 敏感 | `sensitive_identity_view`（越出范围查看证件时） |
| 系统 | `diagnostic_run`；一般拒绝记为 `access_denied` |

**下载日志语义（X-Accel-Redirect）**：

- `download_denied`：对象不在范围内或缺少权限（记录请求的 document_id 和原因）。
- `download_authorized`：权限判定通过（包含 `via_permission`）。
- `download_started`：路径校验通过、文件存在，Django 已返回 `X-Accel-Redirect`（生产）或已开始流式返回 `FileResponse`（开发）。**这只表示已把文件交给 nginx 或开始发送**。
- **不记录 `download_completed`**：Django 无法确认客户端是否完整收到。如需佐证，nginx 可在 internal location 的 access log 中记录 `$request_id`、`$status`、`$body_bytes_sent`，作为运维旁证，不写入 AuditLog。
- Range 分段请求：只在首个请求（没有 Range 头或 `bytes=0-`）时写 authorized/started，后续分段不重复记录。

---

## 8. `/media/` 受保护下载（P0-A8，已确认的当前风险）【已确认·未实现】

### 8.1 方案

采用 **X-Accel-Redirect**：Django 完成鉴权和审计后，nginx 通过 `internal` location 发送文件，由 nginx 原生处理 Range 和大文件。本地开发（`DEBUG=True`，没有 nginx）回退到 `FileResponse`，开关为 `PROTECTED_MEDIA_X_ACCEL`。

### 8.2 最低上线条件（Q11：不采用“任何登录用户可下载”的过渡方案）

关闭公开 `/media/` 之前，下载接口必须**全部**完成：

1. Document 对象查询：只通过 `policy.scope('document','view')` 获取，范围外返回 404；
2. 权限：父 Case 在本人担当范围内，或持有 `document_download_all`，否则 403；
3. 路径安全校验（§8.3）；
4. 审计：denied、authorized、started；
5. 测试：未登录、用户 A、用户 B、管理员（李）、业务管理员全部通过。

以上全部通过后，才允许切换 nginx。

### 8.3 路径安全

- **不接受任何来自请求的路径或文件名参数**，只接受 `document_id`。
- 使用存储后端解析实际路径：`real = os.path.realpath(document.file.path)`，并校验 `real` 以 `realpath(MEDIA_ROOT/'case_documents') + os.sep` 开头、文件确实存在、是普通文件（不是符号链接指向外部）。
- X-Accel 路径由**校验后的相对路径**生成：`'/_protected_media/' + urllib.parse.quote(relpath(real, MEDIA_ROOT))`。**不直接拼接 `file_name` 或 `file.name`。**
- 响应头：
  - `Content-Type`：已存 MIME，未知时用 `application/octet-stream`；
  - `X-Content-Type-Options: nosniff`；
  - `Cache-Control: private, no-store`；
  - `Content-Disposition`：按 RFC 6266/5987 输出 `filename="<ASCII 回退>"; filename*=UTF-8''<percent-encoded>`；
  - preview 只对 PDF、PNG、JPEG 使用 `inline`，其他类型强制 `attachment`。

### 8.4 切换前的引用核对（批次 7 前完成，只读）

1. **API**：确认 `file`、`file_url` 的所有消费者（已知前端没有渲染链接）。
2. **前端**：`grep` 所有 `/media/` 和 `file_url` 的用法。
3. **历史数据**：只读扫描 Timeline `content`/`metadata`、案件和顾客备注、帐票 `note`/`line_items` 等文本和 JSON 字段中是否含 `/media/`。
4. **PDF**：已生成的 PDF 都是流式返回、不落盘；核对模板和生成代码中有没有写入 `/media/` 链接。
5. **生产 media_volume**：只读统计文件数、目录分布、`case_documents/` 以外的内容，以及数据库中找不到对应 Document 的“孤儿文件”（只报告，不删除）。

核对结果写入交接文档，再确定兼容方式：有引用的改为受保护接口 URL；没有引用的直接切换。

### 8.5 nginx 变更（批次 7；**本次不修改**）

```nginx
# 删除 location ^~ /media/ 与 location ^~ /sun/media/ 两块
location ^~ /_protected_media/ {
    internal;
    alias /usr/share/nginx/html/media/;
}
# 同时移除生产中的调试静态页 location（§4.6）
```

### 8.6 部署与回滚

| 步骤 | 内容 | 回滚 |
|---|---|---|
| 1 | 后端：download/preview 接口达到 §8.2 全部条件；`file_url` 改为返回受保护接口 URL | 回退后端镜像 |
| 2 | 前端：下载、预览按钮使用新接口 | 回退前端镜像 |
| 3 | 生产只读核对 §8.4；测试矩阵 §10.3 通过 | — |
| 4 | nginx：删除公开块、加入 internal，重建 frontend 容器 | 恢复旧 `default.conf`，或回退到上一镜像 tag |
| 5 | 验证：未登录访问 `/media/…`、`/sun/media/…`、`/_protected_media/…` 均返回 404；授权下载和 Range 正常 | 同步骤 4 |

---

## 9. Expense owner 与回填【已确认·未实现】

### 9.1 Schema（批次 3）

在 `accounting_expenses` 增加 `owner`（PROTECT）、`created_by`、`updated_by`（SET_NULL），均为 `null=True`。只加列，不写数据。`is_reimbursed`、`is_exported` 不变。新增 Expense 的 owner 由后端强制设为请求用户。

### 9.2 生产回填流程（批次 4，每一步都要执行）

1. **只读统计**：`owner IS NULL` 条数、ID 范围、日期范围、金额合计、已有 owner 的条数。
2. **备份**：`mysqldump` `accounting_expenses`，文件名带时间戳，保存到服务器备份目录。
3. **dry-run**：`backfill_expense_owner --dry-run --username zbry6947@gmail.com`。
4. **明确显示目标**：输出目标 username、User ID（生产）、显示姓名、关联 Employee（姓名和 ID）。如果目标账号没有关联 Employee 或不是受保护账号，命令中止。
5. **expect-count**：`--apply --expect-count N`，N 必须与实时统计一致，否则中止。
6. **输出 ID 清单**：写成 CSV（`expense_owner_backfill_<timestamp>.csv`，包含 id、原 owner、新 owner）。
7. **用户确认**：dry-run 结果交给用户，批准后才执行 apply。执行时在单个事务中只更新 `owner IS NULL` 的行（owner 和 created_by 设为李，updated_by 保持为空），并写 AuditLog。
8. **回滚**：`backfill_expense_owner --rollback <csv>`，只把清单中的 ID 恢复为原值（NULL），同样先 dry-run 并确认。

`owner` 改为 NOT NULL 放到以后单独评估。

### 9.3 不在第一批的会计模型

IncomeSource、VehicleUsage、AccountingProject、帐票、Visa、税务证明、清風：只盘点，不加 owner，不迁移；访问控制只到模块级（§5.2）。

---

## 10. 测试矩阵【已确认·未实现】

测试账号在测试库中创建：`anon`、`li`（受保护 + 李的全部 Group）、`jiao_like`（business_admin + expense_viewer，担当 Case X）、`staff_a`（staff，担当 Case A，拥有 Expense a）、`staff_b`（staff，担当 Case B，拥有 Expense b）、`su_only`（superuser + staff，**没有任何业务 Group**）、`unlinked`（有 `use_cases` 但没有关联 Employee）。

### 10.1 Expense

| 场景 | anon | staff_a | staff_b | jiao_like | su_only | li |
|---|---|---|---|---|---|---|
| list | 401/403 | 仅 a | 仅 b | 全部（只读） | **403 或空** | 全部 |
| retrieve 他人记录 | 401/403 | 404 | 404 | 200 | **404/403** | 200 |
| update/delete 他人记录 | 401/403 | 404 | 404 | **403** | 404/403 | 200 + 审计 |
| create 时伪造 owner | — | owner=staff_a | — | owner=jiao_like | — | owner=li |
| excel | 401/403 | 仅 a | 仅 b | **仅自己** | 403 | 全部 + 审计 |
| summary 余额字段 | — | null | null | null | 403 | 有值 |
| dashboard/图表 | 401/403 | 仅 a | 仅 b | 全部（只读），无余额 | 403 | 全部 |
| copy-expenses 引用他人 ID | — | 400 | 400 | 400 | 403 | 200 |
| owner=NULL 历史记录 | — | 不可见 | 不可见 | 可见，不能改 | 不可见 | 可见，可改 |
| Income/Vehicle/Project/帐票/Visa/税务 | 401/403 | 403 | 403 | 403 | **403** | 200 |

### 10.2 Case / 受付

| 场景 | staff_a | staff_b | jiao_like | su_only | li |
|---|---|---|---|---|---|
| 查看 Case A | 200 | 404 | 200 | 403 | 200 |
| 修改 Case A / 专用 action | 200 | 404 | 403 | 403 | 200 + 审计 |
| 查看无担当 Case | 404 | 404 | 200 | 403 | 200 |
| 修改无担当 Case | 404 | 404 | 403 | 403 | 200 |
| 子资源读写 | 同父 Case | 同父 Case | 同父 Case | 403 | 同父 Case |
| 受付不带担当（已关联 Employee） | 担当=本人 | — | 担当=本人 | — | 担当=李 |
| 受付不带担当（`unlinked`） | 400 | | | | |

### 10.3 Document 下载（切换 nginx 前必须通过）

| 场景 | anon | staff_a | staff_b | jiao_like | li |
|---|---|---|---|---|---|
| 下载 Case A 文件 | 401/403 | 200 + authorized/started | 404 + denied | 403 + denied | 200 + 审计 |
| 预览 PDF / 其他类型 | — | inline / attachment | — | — | — |
| Range `bytes=100-` | — | 206（X-Accel 由 nginx 处理），不重复审计 | — | — | 206 |
| 日文文件名 | — | `filename*` 正确 | — | — | — |
| 路径穿越、符号链接、文件不存在 | — | 拒绝 / download_error | — | — | — |
| 切换后 `/media/…`、`/sun/media/…`、`/_protected_media/…` | 404 | 404 | 404 | 404 | 404 |

### 10.4 Customer / Company

- 搜索和 match：staff_b 搜到 Case A 的顾客时只拿到 Q5 字段；响应中不含证件、地址、联系方式、My Number。
- 详情：staff_b 访问 Case A 的顾客返回 404；jiao_like 看到证件遮罩；staff_a 和 li 看到完整值。
- 只受付未立案的顾客：staff_a 只看到基础信息；li 看到完整信息。
- 任何响应都不含 My Number 明文。

### 10.5 账号、系统与策略本身

- **su_only 读取 Expense（列表、详情、excel、summary、dashboard、图表）全部为空或 403/404。**
- su_only 不能使用账号管理（没有 `manage_users`）。
- 焦、周（降级前为 superuser）不能停用、降级、改名、重置李，也不能把李移出 Group；阶段 B 开启后，Admin 拒绝焦、周。
- 阶段 A：enforcement 关闭时，Admin 准入保持现状；ProtectedAccount 为空时部署检查只报 warning。
- 阶段 B：ProtectedAccount 为空时部署检查失败，Admin 拒绝所有人（不退回“允许所有 superuser”）；服务器命令 `protect_account` 仍能恢复李。
- li 可以登录、管理账号、恢复其他账号；受保护账号改名只能通过服务器命令。
- `check_access_config`：
  - `ENABLE_DEV_TOOLS=True` 时以非零码退出；
  - 阶段 B 起缺少有效的受保护账号时以非零码退出；
  - localdev 在 `warn` 模式下只输出 warning，在 `enforce` 模式下存在并启用时以非零码退出。
- 生产中调试、演示端点返回 404；保留的诊断功能只有 li 能用，并写审计。
- 覆盖测试和静态约束测试（§4.4）通过。
- AuditLog 没有写入、修改、删除 API；Admin 只读，只有 li 可见。
- 回归：现有 95 项测试保持通过（测试夹具补上 Group 和 Employee，不降低断言）；`check`、`makemigrations --check`、`npm run build` 通过。

---

## 11. 实施批次（最终顺序）

每批都包含独立的代码、migration 或命令、测试和文档更新。表中的“数据操作”列只做概括，完整清单见 §12。

| 批次 | 内容 | Schema | 数据操作 | 回滚 |
|---|---|---|---|---|
| 0 | 本方案（第 2 版） | — | — | — |
| 1 | 生产只读核对（账号、Expense 数量、media 概况）；`Employee.user` 字段；`link_user_employee`；`me` 增加字段；`check_access_config`（localdev 为 warn 模式） | +1 列 | D1、D2、D3（发现 localdev 时另走 D12） | 解除关联、删列 |
| 2 | `apps/audit` + request-id 中间件 + 认证和账号审计；ProtectedAccount 表、命令和账号管理受保护规则；权限快照和恢复命令。**阶段 A**：enforcement 关闭，注册李并验证；**阶段 B**：单独开启 protected-admin enforcement 并再次验证 | 2 张新表 | D4（阶段 A）、D5（阶段 B） | 阶段 B 关闭开关；阶段 A 回退代码、删表 |
| 3 | BusinessAccessPolicy + 规则注册表 + Mixin/装饰器 + 覆盖测试；权限 codename + `setup_access_roles`；Expense owner 三列 + 全路径隔离 + 余额口径；会计其他模块的模块级限制；生产禁用调试和演示端点 | +3 列、Permission 行 | D6、D7 | 移出 Group、删列、回退代码 |
| 4 | Expense 回填（§9.2） | — | D8 | 按 CSV 回滚 |
| 5 | Case/子资源/Dashboard/Customer/Company/Document 数据范围；最小识别序列化器与证件遮罩；受付默认担当和未关联时 400 | — | — | 回退代码 |
| 6 | 受保护 download/preview（满足 §8.2 全部条件）+ 前端按钮 + `file_url` 切换 | — | — | 回退镜像 |
| 7 | §8.4 引用核对 → nginx 关闭公开 `/media/`，移除生产调试静态页 | — | D9、D10 | 恢复旧 conf |
| 8 | 全矩阵回归；李的登录、账号管理和恢复验证；在测试库演练快照恢复 | — | — | — |
| 9 | 焦、周 `is_superuser=False`、`is_staff=False` | — | D11 | `restore_access_snapshot` |

- 批次 1～8 期间**不修改任何账号的 `is_superuser`/`is_staff`**。
- 批次 9 只有在批次 8 全部通过后才执行。
- P0-A5（Dashboard 口径回归测试）可以穿插进行。

---

## 12. 需要用户单独批准的数据操作【待批准数据操作】

| # | 批次 | 操作 | 执行前提供给用户 | 回滚 |
|---|---|---|---|---|
| D1 | 1 | 在**生产库**执行只读核对（User、Employee、Group、Expense 统计、media 文件统计） | 要执行的只读命令清单 | 不适用（只读） |
| D2 | 1 | 关联 `zbry6947@gmail.com` ↔ Employee「李」、`zywwind@gmail.com` ↔ Employee「周」 | `--plan` 输出（生产 ID、姓名） | 解除关联 |
| D3 | 1 | 新建 Employee「焦」并关联 `jiao` | 同上 | 解除关联并删除该 Employee（前提是尚未被案件引用） |
| D4 | 2（阶段 A） | 首次导出权限快照并 mysqldump 账号相关表，然后把 `zbry6947@gmail.com` 注册为 ProtectedAccount | 快照保存位置 + `protect_account` 的 dry-run 输出（username、生产 ID、姓名） | 服务器命令删除标记；快照可恢复 |
| D5 | 2（阶段 B） | 把配置改为 `PROTECTED_ADMIN_ENFORCEMENT=True` 并重新部署 | 阶段 A 验证报告（李能登录、进 Admin、恢复命令可用） | 把开关改回 False 并重新部署 |
| D6 | 3 | `setup_access_roles --apply`：创建 Group 和权限 | dry-run 列出 Group 和权限 | 删除 Group |
| D7 | 3 | 分配成员：李 → business_admin、accounting_admin、system_admin；焦、周 → business_admin、expense_viewer | 分配前后差异 + 快照 | `restore_access_snapshot` |
| D8 | 4 | Expense owner 回填（§9.2 的 8 个步骤） | 目标 username 和 Employee、实时条数、ID 清单 | `--rollback <csv>` |
| D9 | 7 | 生产 §8.4 引用核对的结果与兼容处理（如需改写引用，另行批准） | 核对报告 | — |
| D10 | 7 | 切换生产 nginx（关闭公开 `/media/`） | 测试矩阵结果、切换时间 | 恢复旧 conf 或镜像 |
| D11 | 9 | 焦、周：`is_superuser=False`、`is_staff=False` | 批次 8 全部通过的报告 + 快照 | `restore_access_snapshot` |
| D12 | 1 之后（D1 发现时） | 生产存在 `localdev`：先只读报告；批准后**只能停用**（`is_active=False`），不自动删除；删除账号是未来另一项需再次批准的数据操作。确认已停用或不存在后，另行把 `LOCALDEV_CHECK_MODE` 改为 `enforce` | D1 报告（存在与否、is_active、最后登录） | 重新启用 |

本方案中的任何命令都默认 dry-run，只有显式 `--apply`，并附带用户批准记录，才会执行写操作。

---

## 13. 明确不在本方案范围内

- 不修改 Case 13 个状态；不拆分 Person/Customer。
- 不为 Income、VehicleUsage、AccountingProject 等添加 owner 或迁移数据。
- 不实现 Expense 审批、支付、入账。
- 不实现 My Number reveal（`reveal_my_number` 不在 P0 创建）。
- 不实现临时代理、部门范围、多租户。
- 不连接、不索引、不迁移 Google Drive；不移动 `media_volume` 中的文件，不删除孤儿文件。
- 本方案阶段不修改代码、nginx、数据库或账号。

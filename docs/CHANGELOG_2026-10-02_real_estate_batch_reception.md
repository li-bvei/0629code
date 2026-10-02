# 2026-10-02：不动产批量变更、支出类别联想、新规受付直接输入（本地实现）

依据：`docs/CHANGE_REQUEST_2026-10-02_real_estate_batch_reception.md`。
分支：`codex/p3-real-estate-collaborative-ledger`（已提交 `9b81b77` 并于 2026-10-02 推送到 `origin/codex/p3-real-estate-collaborative-ledger`；未合并到 `main`、未部署；生产 D1～D12 未执行；未修改生产库和正式预览库）。

## 1. 不动产：搜索补齐与批量变更

### 行为

- 列表筛选新增「取引日（开始/结束）」和「振込状态」；关键词继续覆盖编号、当事者、物件、房间号、备考。不按 Employee、账号或担当 ID 搜索。
- 列表新增多选（跨页保留）、「絞り込み結果をすべて選択」、「選択解除」、「一括変更」、「完了にする」。仅对持有批量权限的用户显示。
- 批量变更只允许三个字段：段階、担当者（自由文本）、取引日。只变更勾选的字段；清空担当者/取引日必须显式勾选「空欄にする」。
- 提交前显示对象件数、筛选条件摘要、变更内容，并做最终确认。一次确认只发送一个请求。
- 只对利用中的记录生效；归档记录不能被选中，混入时整批中止。归档/恢复仍只用原有专用 action。
- 不修改法定台账。变更取引日时，若该记录的台账已锁定，结果中提示件数，由用户在各记录中另行做台账更正。

### API

| API | 说明 |
|---|---|
| `GET /api/real-estate/transactions/?transaction_date_from=&transaction_date_to=&transfer_status=` | 新增筛选参数；日期格式错误返回 400 |
| `POST /api/real-estate/transactions/bulk-preview/` | 固定对象，不写入。body 二选一：`{filters}`（按当前筛选，强制只含利用中）或 `{selection: {mode:'ids', items:[{id, updated_at}]}}`（列表中手动勾选的记录，`updated_at` 是列表显示时的值）。返回 `selection_token`（签名、15 分钟有效，固化操作者・对象 ID・**每条记录的版本 `updated_at`**・条件摘要）、`count`、`filter_summary`、`mode` |
| `POST /api/real-estate/transactions/bulk-update/` | body `{selection_token, changes, clear_fields, expected_count}`。**只接受 token，不接受直接传 ID**（传 `selection` 返回 400）。返回 `{batch_id, matched, updated, unchanged, locked_ledger_count}` |

一致性规则（`apps/real_estate/bulk_service.py`）：

- 整个批次在一个数据库事务内，对象行 `select_for_update` 后再比对版本。任何一条不存在、已归档、**版本与 token 中固化的 `updated_at` 不同**、校验失败，或件数与 `expected_count` 不一致，整批不写入。
- 并发保护（2026-10-02 补强）：单条编辑、其他批量修改、归档、恢复都会推进 `updated_at`，所以预览之后任一目标记录被修改、归档、恢复、删除，提交都返回 409。手动勾选的记录在 `bulk-preview` 时就用「列表显示时的 `updated_at`」比对，画面已过期则在预览阶段 409。成功执行后同一 token 不能重放（版本已变）。前端收到 409 会关闭对话框、清除选择并重新读取列表。
- 状态冲突（件数变化、归档、ID 不存在、版本变化）返回 409；请求格式错误（空变更、未知字段、重复 ID、缺少版本、直接传 ID、token 过期/篡改/他人签发）返回 400；无权限返回 403。
- 每条记录用单条编辑同一个 serializer 校验，并执行规则的 `prepare_update`（写 `updated_by`）。值未变化的记录不更新、不写履历。
- 上限 2000 条/批。

### 权限

- 新增 `real_estate.bulk_change_real_estate`（`real_estate/0005_bulk_change_permission`，只有 Permission 行）。
- 批量操作需要同时持有 `use_real_estate`、`change_real_estate`、`bulk_change_real_estate`。
- 角色定义中只有 `system_admin`（李）拥有；`business_admin`、`staff` 没有，原有协同单条查看/新建/编辑不变。
- 不读取 `is_superuser`；不按担当文字或 Employee 限制对象。

### 履历与审计

- 每条变更记录写一条 `transaction_updated`（`extra.bulk=true`、`extra.batch_id`），记录页面的操作履历显示为「〇〇が段階を「契約」から「完了」に変更しました（一括変更）」，含真实操作者和前后值。
- 每个批次另写一条汇总 `transaction_bulk_updated`（件数、变更字段、筛选摘要、`via_permission`）。普通页面不显示字段 ID、JSON、权限名。

## 2. 支出：地点等文字 → 类别建议，类别沉淀为主档

### 行为

- `Expense.category` 仍是自由文本。建议只显示为候选，用户点「採用」后才填入；手输类别始终可以保存，保存时不改写。
- 新表 `accounting_expense_category_rules`（模型 `ExpenseCategorySuggestionRule`）：`pattern`、`pattern_key`（规范化后的匹配键）、`match_field`（place / expense_target / note）、`expense_category`（FK）、`priority`、`is_active`、`source`（seed / manual / user_confirmed）、`owner`（空＝全事务所规则；有值＝仅该用户本人）、`created_by`/`updated_by`、时间戳。同一范围内 `match_field` + `pattern_key` 唯一（本人规则按 `owner` 唯一约束；全事务所规则由 serializer 和提升操作检查）。
- 建议只使用「全事务所规则 ＋ 本人规则」，本人规则排在前面；其他用户记忆的规则不参与建议。
- 匹配方式：输入文字（NFKC・小写・去空白后）包含规则文字即命中；按优先度、文字长度排序，同一类别只出一次，最多 3 条。停用的规则或停用的类别不建议。
- 初始规则（migration `accounting/0020`）：場所包含「駐車場」「停车场」「parking」→ 既有类别「停车费」（`0002` 已有，不新建「駐車場代」等重复主档）。
- 保存支出时，把确认使用的类别沉淀为 `ExpenseCategory` 主档：已有同名或仅表记不同（全半角、空白等）的主档则复用；否则新建并写审计 `expense_category_auto_created`。已停用的同名主档不会被重新启用。
- 「この場所とカテゴリの対応を記憶する」复选框默认不勾选；勾选保存时才新增一条 `user_confirmed` 的**本人规则**（`owner`＝本人，审计 `expense_category_rule_remembered`），只出现在本人的建议里。本人同一场所已有规则时不覆盖；已有同场所同类别的全事务所规则时不重复创建。
- 管理员（`manage_expense_category`）可在规则管理中把本人规则提升为全事务所规则（`POST .../{id}/promote/`，审计 `expense_category_rule_promoted`）；已有同文字的全事务所规则时拒绝。普通更新不能改变规则范围。
- 个人历史推荐范围不变，仍只读本人支出。全事务所共享的只有类别名和管理员确认过的规则；具体场所名不会自动进入公共建议。

### API 与权限

| API | 说明 |
|---|---|
| `GET /api/accounting/expenses/category-suggestions/` | 响应新增 `place_recommendations`（`name`、`match_field`、`pattern`、`reason`、`requires_confirmation`）；原有键不变 |
| `POST/PATCH /api/accounting/expenses/` | 新增可选只写字段 `remember_place_category`（布尔） |
| `/api/accounting/expense-category-rules/` | 规则的列表（含各用户的本人规则，可用 `?scope=office|personal` 筛选）・新增（恒为全事务所规则）・修改・删除，以及 `POST {id}/promote/`。**全部动作（含列表）需要 `accounting.manage_expense_category`**；写审计 `expense_category_rule_created/updated/deleted/promoted` |

- 持有 `use_expense` 的普通用户：可得到建议、保存时沉淀类别、显式记忆一条只对本人生效的场所规则；不能列出、修改、删除、提升规则。
- 前端：`ExpenseFormFields.vue` 显示建议与记忆复选框；`ExpenseCategoryListPage.vue` 对有管理权限的用户显示规则管理卡片。

## 3. 新规受付：直接输入

- `/reception/new` 改为两步：业务信息输入 → 确认并创建。删除照合表单、照合结果、候选选择、「新規登録」守门逻辑；页面不再调用 `customers/match`，不再发送 `existing_customer_id`。
- 页面直接输入：新顾客（氏名、生年月日必填）、案件种别、申请区分、担当者、受任日、可选公司和家族。
- 账号未关联 Employee 时：页面顶部提示，担当者变为必填，不再显示「未选择则自己担当」。后端规则不变（不创建未分配案件）。
- 后端 `POST /api/receptions/`：未关联 Employee 且未选担当时，400 响应从 `{"responsible_employee": [...]}` 改为 `{"case": {"responsible_employee": ["担当者を選択してください。"]}}`，与请求结构一致。
- 前端把 400/403 的响应体按字段展开：页面顶部列出「項目名：理由」，对应输入项下方也显示；409 仍提示处理中。不再把所有 400 显示成同一句失败文案。
- 后端继续兼容 `existing_customer_id`/`existing_company_id` 和 `POST /api/customers/match/`，其测试保留。是否删除另行确认。

## 4. migration 与部署注意

| migration | 内容 | 回滚 |
|---|---|---|
| `real_estate/0005_bulk_change_permission` | 只改 Meta.permissions（新增一个 Permission 行） | 反向无数据影响 |
| `accounting/0020_expense_category_rules` | 新建规则表；类别「停车费」存在时写入 3 条全事务所初始规则。**migration 不创建、不启用类别**：类别不存在则不写规则，类别停用则只写规则（停用的类别不会被建议） | 反向删除规则表；不动支出记录 |

- 部署后需执行 `setup_access_roles --apply --yes`，`system_admin` 才会得到 `bulk_change_real_estate`。
- 上线前检查（migrate 之后）：`python manage.py check_expense_category_rules`。只读；报告类别「停车费」是否存在且有效、3 条全事务所初始规则是否存在/有效/指向该类别、是否存在「駐車場代」之类的别名类别、本人规则件数；有问题时非 0 退出。
  - 类别或规则缺失：`--apply --yes --username <执行者>` 只补登记缺失的「停车费」和初始规则（写审计 `expense_category_seed_repaired`），不创建别名类别，不改动已有类别和规则。
  - 类别被停用：命令只报告，不自动启用（即使加 `--apply`）；由管理员在支出类别页面启用，或在不需要该建议时停用初始规则。
- 新表只被新代码使用；旧代码在新表结构上运行不受影响。
- 本次未执行任何生产操作。

## 5. 验证结果（2026-10-02，本地）

| 检查 | 结果 |
|---|---|
| `python manage.py test` | 见 `AI_HANDOFF.md` §3 的最新记录 |
| `python manage.py check` / `makemigrations --check --dry-run` | 0 issues / No changes detected |
| `npm run test:unit` | 33 项通过（新增 `apiErrors`、`reception`、`realEstateBulk`、`expenseCategory`） |
| `npm run build` | 通过（`vue-tsc -b && vite build`） |
| `git diff --check` | 通过 |
| 浏览器验收 | 通过，见下 |

浏览器验收使用新建的独立本地库 `gyoseishoshi_erp_batch_qa_20261002`（全部 migration＋合成数据 25 条不动产记录、3 个测试账号；无真实数据；测试账号密码未写入仓库）。后端 `127.0.0.1:8051`、前端 `localhost:5231`，验收后已停止。

- 李角色（无 superuser）：筛选段階＝契約 → 「絞り込み結果をすべて選択」得到跨页 22 件 → 「完了にする」→ 对话框显示件数和条件 → 最终确认 → 只发出 1 个 `bulk-update` 请求（200）；22 件变为完了，其余 3 件不变；记录履历显示操作者和「契約→完了（一括変更）」。
- 普通职员：列表不显示批量操作；直接调用 `bulk-preview`/`bulk-update` 返回 403；单条 PATCH 仍为 200。
- 支出：場所输入「新宿駐車場」显示建议「停车费（場所に「駐車場」を含む）」，类别栏保持为空；点「採用」后填入；手输其他类别后建议仍只作为候选，并出现默认未勾选的记忆复选框。
- 新规受付（未关联 Employee 的账号）：页面无照合步骤；漏选担当者时该项显示「担当者を選択してください。」；填入无效邮箱提交后，页面顶部和邮箱项显示后端原文「メール：有効なメールアドレスを入力してください。」（Network 为 400）；更正后用同一 `request_id` 提交成功（201）并进入案件页面。

未做：预览工具进程仍无法读取 `backend/.venv`（macOS 权限），QA 后端改用命令行启动；`nginx -t` 和 Docker 验证本次未重跑。

## 5.1 上线前补强与第二轮 QA（2026-10-02）

补强内容：批量修改的版本确认（见 §1）、停车费类别上线前检查（见 §4）、`CHANGE_REQUEST` 标记为已实施的设计记录。

验证：后端全量测试、`check`、`makemigrations --check --dry-run`、前端单元测试、`npm run build`、`git diff --check` 全部通过（件数见 `AI_HANDOFF.md` §3）。

第二轮 QA 使用新建的独立库 `gyoseishoshi_erp_real_estate_qa_20261002_batch`：由既有 QA 库 `gyoseishoshi_erp_real_estate_qa_20261001`（`LIST.xlsx` 的 `工作表1` 36 条）本地复制而来，再执行本批 migration，并新增 4 个验收专用账号。既有 QA 库只做了只读导出，记录数、账号、migration 状态均未变；既有账号密码未改。两个库都保留。没有从生产库取数据。含台账数据的页面没有截图；本文件不记录任何真实姓名、金额或 Excel 内容。

| 场景 | 结果 |
|---|---|
| 李：列表跨页手动勾选（第 1 页 20 件＋第 2 页 2 件） | 显示「22 件を選択中」，翻页后保留 |
| 李：手动选择后、确认前另有单条编辑 | 页面提示「選択後に他の操作で変更された記録があります…」，`bulk-update` 409，22 件均未变，选择被清除 |
| 李：按筛选全选 → 「完了にする」（页面操作） | 36 件为对象，35 件变更、1 件原本已是完了；`bulk-update` 200 |
| 李：手动选择（跨页 5 件）批量担当者 | 200，5 件变更 |
| 李：按筛选全选批量取引日 | 200，36 件变更 |
| 李：预览后单条编辑 / 预览后归档 / 归档后恢复再提交旧 token | 均 409，无任何记录被改 |
| 李：用过期画面的 `updated_at` 做预览；不经 token 直接传 ID | 409；400 |
| 李：记录履历 | 三次批量各一条，操作者为李的 Employee 名，分别显示段階・担当者・取引日的前后值并标注（一括変更） |
| 普通不动产授权用户 | 可见全部 36 件；单条编辑 200；`bulk-preview`（筛选・ID 两种）和 `bulk-update` 403；归档 403；页面无批量栏和勾选列 |
| 支出：职员 A 勾选记忆后保存 | 本人建议中出现该类别（本人规则）；停车规则仍为全事务所规则 |
| 支出：职员 B、李 输入同一场所 | 提升前无建议；类别名本身作为主档可选 |
| 支出：职员 A 调用规则列表・提升 | 403 |
| 支出：李在类别页面点「事務所共通にする」 | 确认后该规则变为全事务所规则，非本人也得到建议 |
| 新规受付（未关联 Employee） | 页面只有「業務情報 → 確認して作成」两步，无照合文字，未调用照合 API；漏选担当者时担当者项显示「担当者を選択してください。」；直接调用 API 得到 400 `{"case": {"responsible_employee": [...]}}` 且未创建案件；选择有效担当者后 201 并进入案件页面 |
| `check_expense_category_rules`（QA 库） | 类别有效、3 条规则有效、退出码 0 |

说明：受付页面对「未关联 Employee 且未选担当者」先做前端必填校验，所以这一情形在页面上看到的是前端的同一句提示；后端 400 的结构由 API 测试和直接调用确认，页面把后端 400 映射到字段的逻辑由前端单元测试和上一轮的邮箱格式错误验收确认。

## 5.2 发布前固定检查（2026-10-02，提交 `21e5331`）

| 检查 | 结果 |
|---|---|
| 旧代码兼容性（`backend/scripts/rollback_compat/run.sh … --recreate`，专用临时库） | 通过：旧基线 `de95411` 建旧表结构 → 最新代码 migrate（待执行 102 项，含 `accounting/0020`、`real_estate/0004`・`0005`）→ 阻止旧代码写入的 NOT NULL 列 0、旧代码缺失列 0、旧代码写入失败 0、新代码读取更新 24 项失败 0 |
| 同一库上的 `check_expense_category_rules`（与生产相同的「旧结构升级」路径） | 类别「停车费」有效、3 条初始规则有效，退出码 0 |
| Docker 隔离环境（`git archive` 副本、临时 `.env.prod`、compose 项目 `sunrise_batchval`、端口 `127.0.0.1:18082`、mysql:8.0、`APP_ENV=production`） | 镜像构建成功；全新库 migrate 111 项全部应用，`migrate --check` 0；`check` 0 issues；`setup_access_roles --apply` 后只有 `system_admin` 含 `bulk_change_real_estate`；`check_access_config` 仅阶段 A 警告；`nginx -t` 成功；`release.sh verify-config`・`verify-http` 全部 OK（`/media/`・`/sun/media/`・`/_protected_media/` 为 404）；health/readiness 正常；未登录访问业务 API 403；开发端点 404 |

隔离容器已停止，镜像（`sunrise-backend:batchval`）和隔离卷保留；未影响任何预览库或 QA 库。生产未执行任何操作。

## 6. 业务选择（2026-10-02 已由用户确认）

确认结果：

1. 批量权限只给李，保持不变；其他人有月末批量需求时再单独授权。
2. 停车类别正式名称保留「停车费」，不新建日文重复类别。
3. 保持必须关联 Employee 的规则；没有 Employee 的账号先由管理员关联；不做「未分配案件」。
4. 类别主档全事务所共享；「记住场所→类别」的规则默认仅本人可见，管理员可提升为全事务所规则（已按此实现，见 §2）。
5. 旧顾客照合 API 暂时保留，本次不删除。

以下为确认前的原始记录：

1. **批量权限范围**：当前只有 `system_admin`（李）。是否授予其他普通用户，需事务所确认后单独授权。
2. **停车类别的正式名称**：初始规则沿用既有主档「停车费」。若要改成日文名称，应改该主档的名称（规则跟随主档），不要另建。
3. **未关联 Employee 的账号**：现在必须选择有效担当者；没有 `case_change_all` 的未关联账号无法登记，需管理员先关联 Employee。是否允许「未分配案件」属于权限模型变更，未实施。
4. **用户记忆的场所规则是全事务所共享的**（已解决：确认后改为默认仅本人可见，管理员可提升）：最初实现中规则文字（场所名）会作为其他人输入相同场所时的建议理由显示。
5. **旧的顾客照合 API**（`customers/match`、受付的 `existing_customer_id`）：本次保留，是否删除另开任务。
6. **契约变更**：`POST /api/receptions/` 担当者缺失的 400 响应结构已改变（见 §3）。仓库内只有受付页面使用。

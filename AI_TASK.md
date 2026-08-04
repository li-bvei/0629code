# AI Task

## Current Task

2026-08-04 顧客・会社・案件一批 bug 修复 + 新功能（对应 Task #37-43，详见 `AI_CONTEXT.md` 「4C. 顧客・会社・案件本轮修复与新增」）：

1. 全项目 select/option value-vs-code 审计，修复 `CustomerDetailPage.vue`（性别）+ `ReceptionNewPage.vue`（性别+家族関係，新規受付主表单，影响面更大）两处真实 bug，其余约 8 处核对无问题。
2. 修复 `CaseDetailPage.vue` 必須事項进度条与「X/Y 完了」文字口径不一致（改成统一读后端 `required_items_progress_percent`）。
3. `CaseDetailPage.vue` 新增「案件基本情報」编辑入口（案件種別/申請区分/顧客/会社/担当者，diff 提交 + Timeline 记录），不含日期/番号字段（用户确认不需要）。
4. `CompanyStaff` 新增可选 `customer` 外键，可直接从既有顧客选人自动带出字段；新增序列化器级"同一顧客不能同时在职于两家公司"校验；従業員列表离职员工变灰排最下面（用户明确选定的方案），保留硬删除。
5. 新增 `ResidenceStatusMaster` 后端管理表（含约 30 项官方在留資格种子数据 + `get_or_create` 种子函数），四个消费端（`CustomerDetailPage.vue`/`ReceptionNewPage.vue`/`CustomersPage.vue`/`CompanyDetailPage.vue`）改为动态拉取 + `filterable` 关键字搜索，删除原硬编码的 17 项常量数组。设置页新增「在留資格」管理 tab。
6. 修复 `.search-row` 在 560-900px 缩放区间的 CSS grid 溢出死区（全站共用一条规则）。**未能复现**用户描述的"操作按钮完全覆盖内容"具体场景，如果之后能复现需再单独定位。
7. 侧边栏新增折叠为图标模式（`AdminLayout.vue` + `el-menu :collapse`），`localStorage` 持久化。

**未实施、待用户确认**：Checklistテンプレート内容清理（去重 + よくある項目扩充候选清单）——已排查完成并整理出具体修改清单，但用户要求先审阅内容再动手，跟以上 7 项分开处理，不在本轮范围内。

验证：`manage.py check`、`npm run build`（全部改动合并后一起跑）均通过；浏览器人工验证覆盖性别提交、进度条一致性、案件基本情報编辑、会社従業員关联顧客、在留資格四端下拉、侧边栏折叠展开+刷新持久化。

状态：

```text
已完成（Checklistテンプレート内容清理待用户审阅后另行处理）
```

## Previous Task Notes（项目记忆刷新 2026-08-03）

2026-08-03 项目记忆刷新：重新读取当前仓库、全部 Markdown、今天的提交 `157a986`，并以实际代码为准统一项目状态。

本轮确认并更新：

- 生产前端正确端口为 `8081`，宝塔 `/sun/` 已代理到 `127.0.0.1:8081`；`8080` 是 Java / `jsvc`，`8090` 是另一个项目 `sunrise-diagnosis-web`。仓库 `docker-compose.yml` 与 `docs/DEPLOY.md` 已同步改为 `8081`。
- 记录生产库的 django-axes 初始迁移兼容问题：如果 `axes_accessattempt` 已存在但 `axes.0001_initial` 未记录，先核对 `showmigrations axes`，再用 `migrate axes --fake-initial`，不删除表、不直接普通 `--fake`。
- 当前案件前端以 `CaseChecklistItem` 为实际步骤/必要资料机制；独立 Task 后端保留，但菜单和案件详情 CRUD 已下线。
- 案件・担当設定管理当前只保留案件種別、申請区分、よくある項目与 Checklistテンプレート；案件進捗、取得場所、準備者区分旧设置已隐藏，担当者走独立 `/employees` 页面。
- 新規受付以顾客创建为核心，案件可选；顾客列表不再直接新建顾客，会社列表仍保留新建公司。
- 系统安全现状：マイナンバー Fernet 加密、django-axes 防爆破、`/settings` 修改密码和 root 账号管理已完成。
- 清風合格通知書的基础 PDF 添加文字工具实际已存在，但业务继续开发暂停；修正文档中“待开发”与“已存在”并存的歧义。
- `AI_CONTEXT.md`、`docs/PROJECT.md`、`docs/DATABASE.md`、`docs/ROADMAP.md`、`docs/DEPLOY.md` 已按上述现状对齐。

状态：

```text
已完成（仅更新配置与项目记忆/文档，不改业务逻辑，不生成 migration）
```

## Previous Task Notes（請求書・領収書汇总显示与边框）

用户反馈帳票管理的請求書・領収書部分，汇总数字（小計/10%対象額/消費税10%/非課税対象額/合計，最多可到7行）太复杂，要求简化成只有小計/消費税/合計三行；同时反馈PDF明细表左边框在汇总行那里断掉了，需要接上。两个都改了：

- **汇总简化**：`build_invoice_summary_rows()`（`backend/apps/accounting/pdf.py`）只保留小計/消費税/合計三行，不再按10%/8%/非課税逐条展开。**只是显示层简化，`voucher_calculations.py` 的分税区分计算逻辑完全没动**——`summary['subtotal']`/`summary['tax_total']`/`summary['total']` 本来就是合并后的数字，直接用。前端 `AccountingVouchersPage.vue` 的 `.voucher-total-box` 同步做了一样的精简（`taxSummary` 的 reduce 也只算这三个字段了），删掉了不再用的 `.voucher-nowrap-label` 死代码。
- **左边框断裂修复**：根因是汇总行最左侧是个 `border:False` 的空白占位 cell（领収書的"収入印紙"章印框故意叠在这块空白区域上）。第一次尝试直接把这个cell的border改成True，结果领収書的収入印紙框里多出好几条不该有的横线，跟章印框边框打架——生成PDF渲染成图检查才发现，撤回了。改成**保持border:False不变，画一条单独的竖线**（新增`connect_summary_left_border()`）把表格左边框从汇总区顶部一直连到表格底部，请求書、領収書两处都调用了，两边视觉都验证过没问题。

**验证时顺带发现一个真实的历史数据问题（本轮没有处理）**：部分较早的 `AccountingVoucher`（如id 10、11）存的 `total_amount` 等字段跟按当前逻辑对`line_items`现算出来的数字不一致（同一份PDF上方"合計"和下方明细表"合計"两个数字不一样），怀疑是`tax_category`计算逻辑/migration 0012引入之前的旧记录没有重新save()过。已记录在`AI_CONTEXT.md`「請求書・領収書注意事项」小节，需要用户确认后再决定是否批量重算——因为会改动可能已经发给客户的历史单据金额，不能擅自处理。

验证：`manage.py check`、`npm run build`都过了；用真实数据生成了3张PDF（2张請求書+1张領収書）转成图片逐张核对（先发现領収書収入印紙框的问题、改完再验证一遍确认没有了）；浏览器里打开编辑弹窗核对了.voucher-total-box的数字跟PDF一致。

**后续追加要求**：用户又提出小計/消費税/合計的标签要合并单元格、右对齐，独占一行占5列（請求書6列布局里除了金額那一列之外全部合并）。这个改动**只做了請求書**，領収書故意没跟着改——因为領収書如果也合并加框，每行的上下边框会横穿収入印紙章印框内部，正是之前撤回过的那个bug。`build_invoice_summary_rows()`加了`merge_label`参数区分两种模式：請求書用`merge_label=True`（合并、右对齐、正常加框，不再需要额外画连接线），領収書保持`merge_label=False`（原来的空白占位+独立标签+连接线方案）。两种都生成PDF转图片验证过。

状态：

```text
已完成（历史数据不一致问题留给用户决策，未处理）
```

## Previous Task Notes（支出記録Excel帳面残高修正）

用户验证「支出記録」Excel时发现：筛5月份（支出44835）后，账面残高框根本没跟着筛选变，还是显示系统当前月（8月，没数据，全是0）。确认后改成**跟着导出时选的対象期間走**，残高公式=期首残高（对象期間开始前的全部历史累计）+期間収入-期間支出（都限定在対象期間内，且故意不看カテゴリ/支払方法等明细专用筛选，只按日期）。汇总框标签同步改名：今月入金→期間収入，前月繰越残高→期首残高（残高不变）。用真实数据验证过：筛5月得到期首残高2564／期間収入150000／残高107729，跟用户自己核对的账目一致；不筛日期（全部历史）残高还是-308430，跟上一版结果一致。`compute_period_balance_context(params)`替换了原来按系统当前日期算的`compute_monthly_balance_context()`。

紧接着用户追问「支出記録页面上面那个帳面残高是不是也要修」——确认是同一个根因：`ExpenseViewSet.summary()`（页面上対象件数/支出合計/帳面残高三个卡片的数据源）原来的 `balance` 是纯"当前筛选范围内收入-支出"，没有期初余额，而且支出侧还会被カテゴリ等窄筛选影响。改成跟 Excel 共用同一个 `compute_period_balance_context()`：`balance` 用期首残高口径，`target_count`/`total_expense`（対象件数/支出合計两个卡片）保持窄口径不变（跟表格实际显示的行对应）。删掉了不再用的 `build_income_source_queryset_for_expense_summary()`。前端 `ExpenseListPage.vue` 没有改，因为 API 返回字段名没变。

详见 `AI_CONTEXT.md` 「支出記録 Excel 导出」和「帳面残高已改成期首残高口径」两小节，含一条「已知坑」提醒以后别再默认按系统当前日期算累计余额。

验证：`manage.py check` 通过；`npm run build` 通过（无前端改动）；用 test client 直接调 `/api/accounting/expenses/excel/` 和 `/api/accounting/expenses/summary/`，分别测了「筛5月」「不筛日期」「筛5月+カテゴリ筛选」三种场景——Excel 的 workbook 逐格核对过数值，summary 接口确认了 balance=107729 不受カテゴリ筛选影响、但 target_count/total_expense 会正确收窄，都跟手算结果吻合。

状态：

```text
已完成
```

## Previous Task Notes（Excel导出重做，第一版）

用户反馈「支出記録」Excel导出（`GET /accounting/expenses/excel/`，`backend/apps/accounting/excel.py` 的 `build_expenses_excel()`）需要重做。调查确认：只有支出記録的导出是后端生成的富报表（图表/汇总框/出力条件/精算列），収入来源、用車記録目前只是前端把当前筛选数据平铺成表格，没有这些东西——跟用户确认后，本轮**只改支出記録这一份报表**，収入来源/用車記録不动。改动内容：

- **去掉明细图表**：`build_expenses_excel()` 里原来按分类画的 `PieChart`（连同隐藏的 `ChartData` sheet）整段删掉，不再有右侧的分类/精算済み细分图表。
- **顶部汇总框重做**：原来的「支出合計/対象件数/平均支出額」三个框，换成「今月入金/前月繰越残高/残高」。口径（跟用户确认过）：全部按**自然月滚动结算**，与当前筛选的日期区间无关，永远按系统当前日期所在月算——前月繰越残高=截止上月月底的全部收入-全部支出累计差额；今月入金=当月（1号到今天）収入来源合计；残高=前月繰越残高+今月入金-今月支出。新增 `views.py` 的 `compute_monthly_balance_context()` 做这个计算。
- **精算相关内容整体去掉**：支出明細表去掉「精算済み」列，出力条件去掉「精算済み」这一行说明。
- **出力条件精简**：`ExpenseViewSet.build_excel_filter_summary()` 只保留「対象期間」「支出カテゴリ」两项，去掉「支払方法」「キーワード」。跟用户确认过「筛选需要增加」的意思是——excel的明细表本来就有 `auto_filter`（Excel原生的列筛选下拉），所以不需要在出力条件里额外用文字说明这些筛选条件，直接在表格里筛就行。
- **新增収入明細（本月）**：仿照支出明細样式新加一张表，只列当月的収入来源（日付/対象/金額/備考），放在支出明細前面。

后端改动文件：`backend/apps/accounting/excel.py`（`build_expenses_excel()`/`expenses_excel_response()` 签名都新增了 `incomes`/`previous_balance`/`monthly_expense_total` 参数）、`backend/apps/accounting/views.py`（新增 `compute_monthly_balance_context()`，`build_excel_filter_summary()` 精简，`excel()` action 接入新参数）。前端`downloadAccountingExpensesExcel()`调用方式没变，不用改前端。

验证：`manage.py check` 通过；用 Django shell + test client 直接调用 `/api/accounting/expenses/excel/`，加载生成的 workbook 逐格核对了新的汇总框数值、出力条件、収入明細/支出明細表结构，并临时插入一条本月収入验证「今月入金」「残高」联动计算正确、収入明細表正确插入一行（之后清理了测试数据）；`npm run build` 通过（本轮无前端代码改动）。

状态：

```text
已完成
```

## Previous Task Notes（系统安全与账号管理）

用户看了后台链接后反馈"这个后台基本无用"，提出三个明确要求：把 my_number 加密、后台加防爆破（错3次锁）、把新加用户账号的功能搬到前端设置页且只有 root 能加。三件事都已实现，详见 `AI_CONTEXT.md` 第 4B 节，这里只记结论：

- **my_number 加密**：新增 `apps/common/crypto.py`+`apps/common/fields.py`（`EncryptedCharField`，Fernet 对称加密），应用到 `Customer.my_number`/`FamilyMember.my_number`/`CompanyStaff.my_number`。生成了新 migration（`customers/migrations/0005`+`0006`、`companies/migrations/0006`+`0007`，一个改字段类型一个把已有明文行重新加密），本地已跑过并验证密文/解密都正确。代价：`my_number` 从两个 admin 的 `search_fields` 里删了（Fernet 密文不支持部分匹配搜索）。生产 `.env.prod` 需要新增 `FIELD_ENCRYPTION_KEY`（一次性生成，之后不能改）。
- **登录防爆破**：接入 `django-axes`，`AXES_FAILURE_LIMIT=3`、按用户名锁 1 小时自动解锁，`/admin/login` 和 `/api/auth/login/` 都自动生效（因为 axes 挂在认证后端上）。`login_view` 额外做了锁定预检查，避免锁定期间误报"密码错误"。
- **前端账号管理**：`/settings` 从占位页换成真页面 `SettingsPage.vue`，所有人可见「パスワードを変更」（要校验旧密码），只有 `is_superuser` 能看到「アカウント管理」（建号/强制重置密码/启用停用，不能硬删除、不能整体替换）。后端新增 `apps/authentication/serializers.py`+`permissions.py`，`SystemUserViewSet` 按 action 区分权限。新建账号不给 `is_staff`，只是纯登录账号。`Employee` 和 `auth.User` 目前没有关联。

验证：`manage.py check`（通过）、`makemigrations --check --dry-run`（无遗漏）、`npm run build`（通过）、Django test client 分别以 root/普通用户测试了权限边界、真实浏览器里用临时注入的本地 session cookie（不是走登录表单输密码）验证了 UI 两种身份下的显示和新建账号流程。

状态：

```text
已完成
```

## Previous Task Notes（customer intake redesign）

用户观察到"顧客管理/会社管理"这块设计别扭——顧客一覧「新規顧客」弹窗建不了家族信息，家族信息只能事后去顾客详情页一条条弹窗补；而新規受付虽然能一次填完顾客+家族+公司，却强制要求同时开案件，三条创建路径互相不协调。参照 CRM 的 Lead-first 模型（Salesforce/HubSpot 的 Lead→Contact，法律行业 Clio Grow 的 Intake Form→Matter），把"顾客第一次联系我们"这个自然事件对应的新規受付，改造成唯一的顾客创建入口，案件变成其中可选的一步；顧客詳細页的家族信息交互也从弹窗改成页面内联编辑，呼应用户"应该是顾客来找我了，我才开始记录"的直觉。

本次改动范围:

- **新規受付的案件変成可选**（`ReceptionNewPage.vue` + `backend/api/serializers.py`）：`ReceptionSerializer.case` 改成 `required=False`，`ReceptionCaseSerializer` 新增校验（案件種別/申請区分要么都填要么都不填），`create()` 只在真有案件数据时才建 `Case`+Timeline，`customer` 依然必填。前端去掉案件字段的必填校验，加了"不确定就先留空"的提示，提交后按有没有案件分别跳转案件详情/顾客详情。
- **顧客一覧的「新規顧客」退休**（`CustomersPage.vue`）：删掉创建按钮和创建逻辑，弹窗变成纯编辑用途，页头按钮改成跳转「新規受付へ」。**`CompaniesPage.vue` 特意没动**——`ReceptionSerializer` 里公司是可选的，顾客是必填的，如果把「新規会社」也删了，"给已有顾客单独补一个公司"这种场景会彻底没有入口（顾客详情页的关联会社板块是纯展示），所以保留。
- **顧客詳細页家族信息弹窗改内联编辑**（`CustomerDetailPage.vue`）：点"家族を追加"或某条记录的"編集"，会在列表前面就地展开一个编辑表单（`familyEditTarget` 控制，同时只能展开一个），不再弹窗。删除、新增案件等其他操作没变。

明确没动:

- `Case.status` 13 个枚举值本身、`backend/apps/cases/status_service.py` 全部业务规则。
- `Customer`/`Company`/`FamilyMember` 的后端 model/serializer/viewset 完全没改——这轮只是前端调整了"从哪个入口创建"和"用弹窗还是内联编辑"，后端 CRUD 接口本身一个字段都没动。
- `frontend/src/pages/CompaniesPage.vue`——特意不动，原因见上面「顧客・会社の新規登録フロー」小节。
- `frontend/src/pages/CustomerDetailPage.vue` 的「案件を追加」流程、`frontend/src/pages/CompanyDetailPage.vue` 全部——都是针对已存在的顾客/公司的后续操作，跟这轮改的"怎么创建新顾客"无关，原样保留。
- 案件类型分类问题（8/9 案件落在「その他」兜底类型）——仍然**特意跳过**，需要用户另外决策。

本轮**没有生成 migration**——`ReceptionSerializer` 的改动是序列化器层面的校验逻辑调整，不涉及模型字段变化。

验证:

```bash
cd backend && .venv/bin/python manage.py check
cd frontend && npm run build
```

两者均通过。未做登录态下的浏览器人工验证——本地测试账号需要在登录表单里输入密码，属于不能代做的操作，只做了代码走查 + TypeScript 构建校验。建议用户本地手动登录后重点测：新規受付不填案件情報时能否顺利只建顾客并跳转到顾客详情、顧客一覧确认"新規顧客"按钮已经变成"新規受付へ"、顧客詳細页加/编家族信息是否是就地展开而不是弹窗、会社一覧的「新規会社」是否还在正常工作。

状态:

```text
已完成（未做登录态人工验证）
```

## Previous Task Notes

（上一轮）内部code 去摆设、新規受付案件種別 bug 修复（会导致提交 500 的真 bug）、新建「よくある項目」`ChecklistItemPreset` 对照表（约 51 条种子数据，取材出入国在留管理庁官网，事項名自动补全时选中即带出分类/取得場所/準備者/必要内容）、顧客通知文案按準備者分组显示。这些结论全部保留，未被本轮改动。

（更早一轮）案件詳細页「現在の進捗」卡片重做：常显区只留状态+最新進捗日，弹窗按选中状态动态出字段，新增「過去の項目を修正」补录入口，タスク功能整体下线（后端保留），顧客通知文案精简，`caseStatusOptions` 改成业务顺序，「案件進捗」摆设设置下线。

（更更早一轮）项目 Markdown 记录整理更新，范围覆盖 `AI_CONTEXT.md`/`AI_TASK.md`/`docs/PROJECT.md`/`docs/ROADMAP.md`，本次不修改代码、不生成 migration，已完成。

案件・担当設定管理改造已完成并作为当前系统现状保留。

费用功能、材料上传、文件管理、独立 Reminder 功能暂时不做；不要删除后端已有模型和 API，只在前端暂时隐藏不需要的入口。

「清風合格通知書 / PDF 添加文字」功能状态保持:

```text
待开发 / 暂停处理
```

后续不要继续围绕清風合格通知書开发，除非用户重新明确要求。

## Legacy Task Specification（历史记录，不作为当前实现依据）

以下内容记录早期 Task 功能设计，当前前端已经下线独立 Task。后续判断当前产品状态时，以 `AI_CONTEXT.md` 的「案件业务模块现状」和本文件顶部 Current Task 为准；除非用户明确要求恢复 Task，不按以下旧规格继续开发。

## 1. 当时目标

案件模块主要保留:

- 案件一览
- 案件详情
- 客户
- 公司
- タスク
- 担当者管理
- 进度记录

案件详情重点展示:

- 案件基本信息
- 当前状态
- 当前阶段 / 进度
- 次のタスク
- タスク一覧
- 进度记录

暂时隐藏:

- 材料上传
- 文件管理
- 费用管理
- 独立 Reminder 功能
- 时间提醒、通知、邮件、日历、定时任务

## 2. 菜单

案件業務菜单:

- 案件一覧
- 顧客管理
- 会社管理
- 担当者管理
- タスク一覧

担当者管理:

- 页面: `frontend/src/pages/EmployeesPage.vue`
- 路由: `/employees`
- 使用现有 `/api/employees/`

## 3. Task 定位

Task / タスク 是案件内的工作步骤备忘录。

示例:

1. 开具税务证明
2. 开具年金证明
3. 整理申请资料
4. 客户确认
5. 提交入管局
6. 等待审查结果

每个 Task 记录:

- 做什么
- 谁负责
- 计划什么时候完成
- 当前状态
- 实际完成日期
- 备注
- 在案件中的步骤顺序

不做:

- `remind_at`
- 自动通知
- 邮件提醒
- 重复提醒
- 日历同步
- 后台定时任务

前端文案:

- タスク
- タスク追加
- タスク一覧
- 次のタスク

不要再显示中文「工作任务」。

## 4. Task 字段

现有 `Task` model 已复用，并补充字段:

- `case`
- `title`
- `description`
- `responsible_employee`
- `status`
- `sort_order`
- `due_date`
- `completed_at`
- `created_at`
- `updated_at`

说明:

- `due_date` 作为旧字段保留，前端和 API 别名显示为 `planned_completion_date`。
- 新增字段已生成并应用 migration: `tasks.0002_alter_task_options_task_completed_at_and_more`。
- 旧状态会迁移:
  - `todo` -> `pending`
  - `done` -> `completed`
  - `未対応` -> `pending`
  - `対応中` -> `in_progress`
  - `完了` -> `completed`
  - `保留` -> `paused`

## 5. Task 状态

前端显示:

- `pending`: 未开始
- `in_progress`: 进行中
- `completed`: 已完成
- `paused`: 暂缓
- `cancelled`: 取消

规则:

- 状态改为 `completed` 时，如果 `completed_at` 为空，自动写入当前日期。
- 状态从 `completed` 改回其他状态时，可以清空 `completed_at`。
- `planned_completion_date` 只是计划完成日期，不触发提醒。
- 没有填写日期也可以保存。

## 6. 案件详情 Task

案件详情显示「タスク一覧」。

列表字段:

- 步骤
- タスク名
- 担当者
- ステータス
- 予定完了日
- 完了日
- 備考
- 操作

操作:

- タスク追加
- 編集
- 完了
- 保留
- 削除
- 上移
- 下移

要求:

- 一个案件可以添加任意数量 Task。
- 按 `sort_order` 排序。
- 已完成 / 取消任务显示删除线并排在未完成任务后。
- 可以快速点击「完成」。
- 新增 / 编辑使用 Dialog，不跳转单独页面。

## 7. 担当者管理

担当者就是现有 `Employee`。

功能:

- 担当者一覧
- 新規追加
- 編集
- 有効 / 無効切换
- 検索

显示:

- 氏名
- メール
- 電話
- 有効状態
- 更新日時
- 操作

Task 新增 / 编辑:

- 字段名称为「担当者」。
- 数据来源为有效 `Employee`。
- 下拉显示 `Employee.name`。
- 允许为空，显示「未指定」。
- 已停用负责人不出现在新建 Task 的可选列表。
- 已有 Task 仍显示原负责人姓名。
- 提供「担当者管理」快捷入口跳转 `/employees`。

## 8. 案件列表

案件列表增加:

- 任务进度: `已完成数量 / 总数量`
- 次のタスク: 第一条未完成、未取消 Task 的标题和负责人

后端 `CaseSerializer` 返回:

- `task_total_count`
- `task_completed_count`
- `next_task_title`
- `next_task_responsible_employee_name`

## 9. 验证命令

后端:

```bash
cd backend
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
```

前端:

```bash
cd frontend
npm run build
```

## 10. 案件番号规则

最终格式:

```text
{案件種別略称}-{申請区分略称}-{YYYYMM}-{顧客名}-{4位流水番号}
```

说明:

- 案件種別略称来自 `CaseTypeMaster.number_abbreviation`。
- 申請区分略称来自 `CaseApplicationCategory.number_abbreviation`。
- YYYYMM 使用创建时 `timezone.now()` 的东京时间年月。
- 流水号按完整前缀递增: 案件種別略称 + 申請区分略称 + 年月 + 顧客名。
- 旧案件番号不自动重算。
- 案件详情提供受控操作「案件番号を再生成」，确认后写入 Timeline「案件番号変更」。

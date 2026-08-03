# AI Context

## 1. 项目基本信息

### 项目名称

SUNRISE 事务所业务管理系统。

### 技术栈

- Backend: Django + Django REST Framework
- Frontend: Vue 3 + Vite + Element Plus
- Database: MySQL
- PDF: PyMuPDF (`fitz`) + ReportLab
- Deployment: Docker Compose
- Production path: `/sun/`
- Production env file: `.env.prod`

### 本地运行方式

Backend:

```bash
cd backend
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Frontend:

```bash
cd frontend
npm run dev
```

常用验证:

```bash
cd backend
.venv/bin/python manage.py check

cd frontend
npm run build
```

### 服务器部署方式

- Docker Compose 部署。
- 服务器项目目录约定使用 `/www/wwwroot/0629code`。
- 生产 env 文件使用 `.env.prod`。
- 部署命令示例:

```bash
docker compose --env-file .env.prod build
docker compose --env-file .env.prod up -d
docker compose --env-file .env.prod exec backend python manage.py migrate
docker compose --env-file .env.prod exec backend python manage.py collectstatic --noinput
```

### 重要路径

- Backend root: `backend/`
- Django settings: `backend/config/settings.py`
- Accounting app: `backend/apps/accounting/`
- Frontend root: `frontend/`
- Frontend pages: `frontend/src/pages/`
- Frontend accounting pages: `frontend/src/pages/accounting/`
- Router: `frontend/src/router/index.ts`
- Main layout/menu: `frontend/src/layouts/AdminLayout.vue`
- API client: `frontend/src/api/accounting.ts`
- Shared accounting types: `frontend/src/types/accounting.ts`
- Nginx config: `nginx/default.conf`
- Docker Compose: `docker-compose.yml`
- Deployment doc: `docs/DEPLOY.md`

### 案件・担当設定管理

当前统一入口:

- Menu: 案件業務 -> 案件・担当設定管理
- Route: `/case-checklists`
- Page: `frontend/src/pages/CaseChecklistTemplatesPage.vue`

案件関連設定 tabs（现状，2026-08 起）:

- 案件種別: `CaseTypeMaster`
- 申請区分: `CaseApplicationCategory`
- よくある項目: `ChecklistItemPreset`（新，见 4A 章节详述，替换了原「取得場所・準備者区分」tab）

Checklistテンプレート构建器（同一页面，tabs 下方，非 tab 形式）:

- `CaseChecklistTemplate` / `CaseChecklistTemplateItem`

页面里没有独立的「担当者管理」tab 或卡片——担当者复用现有 `employees.Employee`，管理入口是页面下方一个跳转按钮，指向独立页面 `frontend/src/pages/EmployeesPage.vue`（`/employees`）。

已隐藏/下线的旧 tab（后端模型/API 保留，仅前端不再展示）:

- 案件進捗: `CaseStatusSetting`（跟 `Case.status` 无关联，纯摆设）
- 取得場所: `AcquisitionPlacePreset`
- 準備者区分: `ResponsiblePartyPreset`（这两个从未被 Checklist 项目表单真正读取过，已被「よくある項目」`ChecklistItemPreset` 取代）

案件番号生成:

- 新建案件使用 `Case.case_type_master` 与 `Case.application_category`。
- 最终格式: `{案件種別略称}-{申請区分略称}-{YYYYMM}-{顧客名}-{4位流水番号}`。
- YYYYMM 来源为创建时 `timezone.now()` 的东京时间年月。
- 流水号按完整前缀递增。
- 旧 `Case.case_type` 字符串字段保留用于历史显示兼容。
- 现有案件番号不自动重算。
- 案件详情提供受控操作「案件番号を再生成」，会创建 Timeline「案件番号変更」。

### 当前重要目录结构

```text
backend/
  apps/accounting/
    models.py
    serializers.py
    views.py
    urls.py
    pdf.py
    visa_return_pdf.py
    visa_form_fields.py
    visa_position_debug.py
    seifu_notice_pdf.py
    migrations/
  assets/
    fonts/
    images/
    pdf_templates/
      seifu/
      tax/
      zei/
      visa_return/

frontend/
  src/
    pages/
      AccountingVouchersPage.vue
      TaxRenewalVouchersPage.vue
      VisaReturnApplicationsPage.vue
      SeifuNoticePdfTextPage.vue
      VoucherPlaceholderPage.vue
    api/accounting.ts
    types/accounting.ts
    router/index.ts
    layouts/AdminLayout.vue
  public/
    visa-position-debug.html
    visa-form-field-mapping.html
```

## 2. 帳票模块现状

### 路由和菜单

帳票管理是一级菜单，和会計管理同级。当前子菜单包括:

- `/vouchers/invoices` - 請求書・領収書
- `/vouchers/visa-return` - 返签 visa 表
- `/vouchers/tax-renewal` - 税务证明更新用
- `/vouchers/seifu-notice` - 清風合格通知書
- `/vouchers/estimates` - 見積書，占位
- `/vouchers/contracts` - 契約書，占位
- `/vouchers/certificates` - 証明書，占位
- `/vouchers/others` - その他帳票，占位

`/vouchers` 会重定向到 `/vouchers/invoices`。

### 請求書・領収書功能

状态: 已存在。

前端:

- `frontend/src/pages/AccountingVouchersPage.vue`
- API: `frontend/src/api/accounting.ts`
- Types: `frontend/src/types/accounting.ts`

后端:

- Model: `AccountingVoucher`
- Serializer: `AccountingVoucherSerializer`
- ViewSet: `AccountingVoucherViewSet`
- API:
  - `/api/accounting/vouchers/`
  - `/api/accounting/vouchers/{id}/pdf/`
- PDF code: `backend/apps/accounting/pdf.py`

### 金额和税区分计算规则

当前规则非常敏感，不能改错:

- 用户输入的明细单价 / 金额仍然是 **税込金额**。
- 每条明细独立保存税区分，稳定 code:
  - `tax_10` -> `10％`
  - `tax_8` -> `8％`
  - `non_taxable` -> `非課税`
- 新增明细默认 `tax_10`。
- `total_amount` = 税込合计。
- `amount` = 税抜金额。
- `tax_amount` = 消費税。
- 税抜金额按每条明细的税区分从税込金额反算，再分别累计:

```text
10％明细:
tax_excluded = round_half_up(line_total / 1.10)
tax_amount = line_total - tax_excluded

8％明细:
tax_excluded = round_half_up(line_total / 1.08)
tax_amount = line_total - tax_excluded

非課税明细:
tax_excluded = line_total
tax_amount = 0
```

注意:

- 不要把用户输入金额当税抜再乘税率。
- 不要二次加税。
- PDF 明细中的单价和金额显示为税込。
- PDF 明细表头统一使用 `単価（税込）` 和 `金額（税込）`，括号不应被单独换行。
- **PDF 汇总显示（已简化）**: 只显示 小計、消費税、合計 三行。原来还会按税区分逐条展开 10％対象額/消費税10％/8％対象額/消費税8％/非課税対象額，用户反馈"这样计入太复杂"，改成只显示合并后的三个数字。**注意：只是显示层简化，`voucher_calculations.py` 内部仍然按 10％/8％/非課税 分组计算，`subtotal_10`/`tax_10`/`subtotal_8`/`tax_8`/`subtotal_non_taxable` 这些字段都还在、还在算，只是不再单独打印出来**——`summary['subtotal']`/`summary['tax_total']`/`summary['total']` 本来就已经是合并后的三个数，直接拿来用即可，没有改计算逻辑本身。前端 `AccountingVouchersPage.vue` 的 `.voucher-total-box` 同步做了一样的简化（`taxSummary` 的 reduce 也精简成只算 subtotal/tax_total/total 三个字段）。
- 当前没有請求書专用 Excel 输出入口；不要凭空新增。

**PDF 明细表左边框断裂问题（已修复，后来又做了一版样式调整）**：`build_invoice_summary_rows()` 里汇总行的最左侧是一个跨列的空白占位 cell，一直是 `border: False`（这样领収書的「収入印紙」章印框才能干净地叠在这块空白区域上，不被表格横线打断）。这导致汇总行区域完全不画框，从视觉上看就是"明细表的左边框到汇总行这里断掉了"。第一版修复：保持这个 cell `border: False` 不变，改为在 `draw_table()` 调用之后单独画一条 `c.line()` 竖线，从汇总区域顶部一直连到表格底部，补上那一段本来缺失的左边框。封装成了 `connect_summary_left_border()`。

用户后续又要求把小計/消費税/合計的标签单元格跟这块空白区域合并成一个整体、右对齐的带框单元格（不要空白+窄标签这种割裂视觉）。**这个改动只应用在請求書上，领収書没有动**——原因是如果给领収書也这样合并加框，每一行（小計/消費税/合計）自己的上下边框会横穿过「収入印紙」章印框内部，重现了最早试过一次并撤回的那个 bug（章印框里多出好几条不该有的横线）。所以 `build_invoice_summary_rows()` 新增了 `merge_label` 参数：
- `merge_label=True`（`build_invoice_pdf` 用这个）：不再有独立的空白占位 cell，标签文字（小計/消費税/合計）直接放进一个 `span=leading_blank_span+1`（請求書是 6 列里的前 5 列）的合并单元格里，右对齐，正常画框——这时候每行本身的框线就是连续的，不需要再额外画连接线，所以 `build_invoice_pdf` 里也把 `connect_summary_left_border()` 的调用删掉了。
- `merge_label=False`（默认值，`build_receipt_pdf` 用这个）：还是原来空白占位 cell + 独立标签 cell 的结构，配合 `connect_summary_left_border()` 补左边框。

两种版本都用生成 PDF 转图片的方式实际渲染检查过，请求書的合并单元格效果符合预期、领収書的収入印紙框没有被破坏。

共享计算文件:

- `backend/apps/accounting/voucher_calculations.py`

该文件负责:

- line_items 规范化
- 税区分校验
- 10％ / 8％ / 非課税 分组计算
- `subtotal_10`, `tax_10`, `subtotal_8`, `tax_8`, `subtotal_non_taxable`, `subtotal`, `tax_total`, `total`

旧数据兼容:

- `backend/apps/accounting/migrations/0012_voucher_line_item_tax_category.py`
- 旧 `line_items` 中没有 `tax_category` 的明细迁移为 `tax_10`。

### PDF 生成和印章

PDF 文件:

- `backend/apps/accounting/pdf.py`

印章文件:

- `backend/assets/images/company_seal.png`

当前印章逻辑:

- 下载 PDF 时由前端选择 `印章あり / 印章なし`。
- 后端 query 参数: `with_seal=1`。
- 默认不盖章。
- 印章尺寸常量: `SEAL_SIZE_PT = 56.7`。
- 56.7 pt 约等于 A4 纸面 2cm x 2cm。
- 绘制前会用 Pillow 裁剪 PNG 的透明区域，使红色主体接近 2cm x 2cm，而不是透明外框为 2cm。
- 位置逻辑不要随意大改。

### 請求書・領収書注意事项

- 不要影响 `AccountingVoucher` 金额计算。
- 不要恢复旧的税抜输入逻辑。
- 不要修改請求書・領収書 PDF 样式，除非任务明确要求。
- 不要影响电子印章开关。

**发现但未处理的数据问题**：验证 PDF 时发现，部分较早创建的 `AccountingVoucher`（例如 id=10、11，最后更新时间在 2026-07-04 早上）存的 `amount`/`tax_amount`/`total_amount` 字段，跟按当前 `voucher_calculations.py` 逻辑对 `line_items` 现算出来的数字对不上——PDF 上方"請求金額合計"/"合計金額"用的是存量字段（旧值），下方"内訳"表格里的 小計/消費税/合計 是现算的（新值），同一份 PDF 上会出现两个不同的合计数字。怀疑是这些记录建于 `tax_category` 相关计算逻辑/`migrations/0012` 数据迁移引入之前，迁移只回填了 `line_items` 里的 `tax_category` 字段，没有触发 `save()` 重新计算 `amount`/`tax_amount`/`total_amount`。**这次没有动这些存量数据**——只要给这些旧 `AccountingVoucher` 记录重新 `.save()` 一次就能修复（`save()` 里已经会调用 `calculate_voucher_amounts()` 重算），但这样会改动已经可能发给客户的历史请求書/領収書上的金额，需要用户确认后再处理，不能自作主张改。

### 支出記録汇总

状态: 已优化。

支出記録页面:

- Page: `frontend/src/pages/accounting/ExpenseListPage.vue`
- API: `GET /api/accounting/expenses/summary/`

汇总卡片:

- 対象件数
- 支出合計
- 帳面残高

帐面余额公式（已改，见下面「帳面残高已改成期首残高口径」）:

```text
帳面残高 = 期首残高（対象期間開始日より前の全履歴累計） + 期間収入 − 期間支出
```

性能修复:

- 不再为了汇总从前端逐页拉取全部支出记录。
- 后端使用数据库聚合 `Count + Sum`。
- 支出侧筛选使用当前支出筛选条件。
- 日期、关键词、出力済み等可对应条件用于收入侧；カテゴリ、支払方法、精算済み只影响支出，不错误过滤收入。

**対象件数/支出合計** 仍然是**当前筛选结果的窄口径**（跟表格里显示的行一一对应，选了カテゴリ筛选就只统计那个カテゴリ），这两个没有改。

### 帳面残高已改成期首残高口径

状态: 已修复（跟下面「支出記録 Excel 导出」是同一次改动，同一个根因）。

原来 `ExpenseViewSet.summary()`（`GET /accounting/expenses/summary/`）的 `balance` 就是纯粹的「当前筛选范围内收入合计 − 当前筛选范围内支出合计」，**没有任何期初余额概念**，而且支出这边用的是 `self.get_queryset()`（会被 カテゴリ/支払方法/精算済み 等明细专用筛选影响），意味着只要用户选个分类筛选，帳面残高就会被错误地拉高——这跟 Excel 导出里发现的问题是同一个根因。现在改成跟 Excel 共用同一个 `compute_period_balance_context(request.query_params)`：

- `balance` = 期首残高（`start_date` 之前的全部历史收支差额，不选 `start_date` 就是 0）+ 期間収入（`[start_date, end_date]` 内的 `IncomeSource`）− 期間支出（`[start_date, end_date]` 内的 **全部** `Expense`，故意不看カテゴリ/支払方法/精算済み/キーワード这些窄筛选，理由同 Excel）
- `total_income` 字段现在也是这个「期間収入」（原来的口径是共享 `search`/`is_exported` 参数、跟支出侧筛选条件不完全一致，现在跟 Excel 统一了）；前端目前没有单独显示 `total_income` 这个数字，只是内部字段口径变了。
- `target_count`/`total_expense`（对应页面上「対象件数」「支出合計」两个卡片）没有变，仍然是当前筛选结果的窄口径，跟表格实际显示的行一一对应。

删掉了不再使用的 `build_income_source_queryset_for_expense_summary()`。已用真实数据验证：筛 5 月 `balance`=107,729（跟 Excel 一致）；筛 5 月 + カテゴリ=停车费 时 `target_count`/`total_expense` 正确收窄到 10 条/4,580，但 `balance` 依然是 107,729，没有被窄筛选拉低/拉高。前端 `ExpenseListPage.vue` 没有改代码，因为 API 返回字段名/形状没变。

### 支出記録 Excel 导出（`build_expenses_excel()`）

状态: 已重做。三个页面（支出記録/収入来源/用車記録）里，**只有支出記録的导出是后端 openpyxl 生成的富报表**；収入来源、用車記録目前还是前端把当前筛选数据直接平铺成一张表（`frontend/src/utils/exportExcel.ts` 的 `exportRowsToExcel()`），没有图表/汇总框/出力条件这些东西，本轮**没有改动**这两个。

后端: `backend/apps/accounting/excel.py` 的 `build_expenses_excel()`/`expenses_excel_response()`，`backend/apps/accounting/views.py` 的 `ExpenseViewSet.excel()`/`build_excel_filter_summary()`/`compute_period_balance_context()`。

- **明细图表已去掉**：原来按分类画的 `PieChart`（含隐藏的 `ChartData` sheet）整段删除，右侧不再有任何分类/精算済み细分图表。
- **顶部汇总框**：从「支出合計/対象件数/平均支出額」换成「期間収入/期首残高/残高」。**跟着导出时选的対象期間（`start_date`/`end_date`）走**，不选日期就等于"全部历史"。第一版曾经做成"固定按系统当前自然月算，不看筛选"，但一验证发现筛别的月份时这三个框完全不动、永远显示当月（哪怕当月还没数据也是 0），已经按用户反馈改掉，教训记在下面「已知坑」里：
  - 期首残高 = `start_date` 之前（不含当天）的 `IncomeSource` 全部累计 − `Expense` 全部累计；没有 `start_date` 就是 0（因为这时"対象期間"本身已经覆盖了全部历史，不存在"之前"）
  - 期間収入 = `[start_date, end_date]`（缺一边就是那一边不设上/下限）内的 `IncomeSource` 合计
  - 残高 = 期首残高 + 期間収入 − 期間支出（`[start_date, end_date]` 内 `Expense` 合计）
  - **期間支出这里故意只按日期筛，不看カテゴリ/支払方法/精算済み/キーワード这些明细表专用的筛选条件**——残高要反映"账上真实还剩多少"，如果因为页面上选了个分类筛选就只减那一个分类的支出，残高会显著偏高、失真。
  - 计算逻辑在 `views.py` 的 `compute_period_balance_context(params)`，用真实数据验证过两种场景都对：全部历史（不选日期）算出残高 -308,430，筛 2026-05 算出期首残高 2,564／期間収入 150,000／残高 107,729，跟用户自己核对的账目吻合。
- **精算相关内容已去掉**：支出明細表不再有「精算済み」列，出力条件不再有「精算済み」这一行。
- **出力条件精简为两项**：只剩「対象期間」「支出カテゴリ」，去掉了「支払方法」「キーワード」。用户确认过这里去掉的原因——`_write_table()` 本来就会给明细表加 Excel 原生的 `auto_filter`（列筛选下拉），所以没必要在出力条件里再用文字重复说明这些筛选条件，直接在 Excel 表格里筛就行。
- **新增収入明細表**：格式仿支出明細（日付/対象/金額/備考），跟着対象期間走（不再固定"今月"），放在支出明細前面。

`build_expenses_excel(expenses, incomes, filters=None, generated_at=None, opening_balance=None, period_expense_total=None)` 签名，`incomes` 传対象期間内的 `IncomeSource`（供収入明細表 + 期間収入汇总框共用），`opening_balance`/`period_expense_total` 由 `compute_period_balance_context()` 算好传入。前端下载入口（`downloadAccountingExpensesExcel()`）调用方式没有变化，这轮没碰前端代码。

**已知坑**：写"账上还剩多少钱"这类累计余额逻辑时，不要脑补"应该按当前系统日期算"这种默认值——一定要跟着页面/导出时实际选的筛选条件走，否则用户一筛历史区间验证就会发现数字完全不对应。这次就是先按"自然月滚动，不看筛选"做了一版（用户当时确认了这个方向），结果一验证就暴露问题，返工过一次。

## 3. 返签 visa 表功能现状

### 页面和路由

状态: 已存在。

- Page: `frontend/src/pages/VisaReturnApplicationsPage.vue`
- Route: `/vouchers/visa-return`
- Menu: 帳票管理 -> 返签 visa 表

### 后端文件

- Model: `VisaReturnApplication`
- Model: `VisaGuarantorTemplate`
- Serializer:
  - `VisaReturnApplicationSerializer`
  - `VisaGuarantorTemplateSerializer`
- ViewSet:
  - `VisaReturnApplicationViewSet`
  - `VisaGuarantorTemplateViewSet`
- URL:
  - `backend/apps/accounting/urls.py`
- PDF:
  - `backend/apps/accounting/visa_return_pdf.py`

### API

返签 visa 表:

- `/api/accounting/visa-return-applications/`
- `/api/accounting/visa-return-applications/{id}/`
- `/api/accounting/visa-return-applications/{id}/pdf/`

在日担保人模板:

- `/api/accounting/visa-guarantor-templates/`
- `/api/accounting/visa-guarantor-templates/{id}/`

模板删除当前是软删除:

- `DELETE` 会设置 `is_active=false`。

## 4. 税务证明更新用模块现状

状态: PDF 坐标映射工具已完成增强；正式 PDF 生成已先接入「社会保险纳入证明兼委任状」这一份。

### 页面和路由

- Page: `frontend/src/pages/TaxRenewalVouchersPage.vue`
- Route: `/vouchers/tax-renewal`
- Menu: 帳票管理 -> 税务证明更新用

### 后端文件

- Model: `TaxRenewalVoucherRecord`
- Model: `TaxRenewalAgentTemplate`
- Serializer: `TaxRenewalVoucherRecordSerializer`
- Serializer: `TaxRenewalAgentTemplateSerializer`
- ViewSet: `TaxRenewalVoucherRecordViewSet`
- ViewSet: `TaxRenewalAgentTemplateViewSet`
- Template config: `backend/apps/accounting/tax_renewal_templates.py`
- Formal PDF: `backend/apps/accounting/tax_renewal_pdf.py`
- PDF diagnostics: `backend/apps/accounting/zei_pdf_diagnostics.py`
- PDF position debug: `backend/apps/accounting/zei_pdf_position_debug.py`
- URL: `backend/apps/accounting/urls.py`

### API

模板清单:

- `/api/accounting/tax-renewal-templates/`

记录:

- `/api/accounting/tax-renewal-records/`
- `/api/accounting/tax-renewal-records/{id}/`
- `/api/accounting/tax-renewal-records/{id}/generate_pdf/`

代理人模板:

- `/api/accounting/tax-renewal-agent-templates/`
- `/api/accounting/tax-renewal-agent-templates/{id}/`

代理人模板删除当前是软删除:

- `DELETE` 会设置 `is_active=false`。

PDF 字段诊断:

- `/api/accounting/tax-renewal-pdf-diagnostics/`
- `/api/accounting/tax-renewal-pdf-diagnostics/numbered_sample/`

PDF 坐标映射调试:

- `/api/accounting/zei-pdf-position-debug/templates/`
- `/api/accounting/zei-pdf-position-debug/mapping/`
- `/api/accounting/zei-pdf-position-debug/preview/`
- `/api/accounting/zei-pdf-position-debug/test-pdf/`

正式 PDF 生成当前支持:

- `social_insurance_payment_certificate_power_of_attorney`
- API payload: `{ "template_key": "social_insurance_payment_certificate_power_of_attorney" }`
- 使用模板: `backend/assets/pdf_templates/zei/pdf/社会保険納入証明書兼委任状.pdf`
- 使用 mapping: `backend/assets/pdf_templates/zei/field_mappings/social_insurance_payment_certificate_power_of_attorney.json`
- 前端记录列表在已选择该模板时显示「社会保険PDF」按钮。
- 正式生成只读取 `record.form_data` / record 根字段 / company / customer / employee / `agent_snapshot`，不读取 mapping 的 `test_value`。
- 空字段跳过，不写 field key / label。
- 其他 9 个 template_key 仍返回:

```text
PDF字段映射未完成
```

不要假装其他 PDF 已经生成。

### PDF 模板目录

目标实际目录:

- `backend/assets/pdf_templates/zei/pdf/`

兼容旧上传目录:

- `backend/assets/pdf_templates/tax/`

配置逻辑优先扫描 `zei/pdf/`；仅当该目录不存在时，才扫描旧上传目录 `tax/` 作为 fallback。

未来字段映射预留目录:

- `backend/assets/pdf_templates/zei/field_mappings/`

坐标 mapping JSON 每个模板一个文件，命名为模板 key:

- `backend/assets/pdf_templates/zei/field_mappings/{template_key}.json`

坐标单位为 PDF pt，page 从 1 开始，x/y 使用左上角原点，和 PyMuPDF 写入坐标一致。

### 业务分类

更新用 `renewal`:

1. 社会保险纳入证明兼委任状
2. 纳税证明书交付请求书-税务署
3. 纳税证明委任状-税务署
4. 纳税证明书交付请求书-大阪市税
5. 纳税证明委任状-大阪市税
6. 纳税证明书交付请求书兼委任状-大阪府税
7. 労働保険料等納入証明書

年金加入 `pension`:

8. 年金适用事务所加入届
9. 年金被保险者资格取得届
10. 被扶养者（异动）届

条件:

- 7 只有 `has_employees=true` 时才可选。
- 10 只有 `has_dependents=true` 时才可选。

### 第二阶段录入优化

- 页面可选择公司 / 客户 / 员工后点击「套用资料」，把现有资料反映到 `form_data`。
- 公司可反映: `company_name`, `company_number`, `company_address`, `company_phone`, `representative_name`, `representative_kana`, `representative_birth_date`。
- 客户可反映: `applicant_name`, `applicant_kana`, `applicant_address`, `applicant_phone`, `applicant_birth_date`。
- 员工可反映: `employee_name`, `employee_kana`, `employee_birth_date`, `employee_address`, `employee_phone`, `employee_my_number`, `employment_start_date`, `salary_amount`。现有 Employee 字段不足时能取多少填多少。
- 代理人模板选择会复制模板内容到当前记录 `form_data`，并保存 `agent_template_id` 和 `agent_snapshot`，后续模板修改不影响旧记录。
- 决算期间使用日期范围选择器，保存 `fiscal_period_start` / `fiscal_period_end`，并自动拆分保存 `fiscal_start_year/month/day` 与 `fiscal_end_year/month/day`。

### 第三阶段 PDF 字段诊断

- 页面提供「PDF字段诊断」入口。
- 后端扫描 `backend/assets/pdf_templates/zei/pdf/` 下所有已匹配模板。
- 返回每个 PDF 的存在状态、页数、页面尺寸、AcroForm 字段数量和字段列表。
- 编号样本接口只对有 AcroForm 字段的 PDF 生成临时下载，不覆盖原模板。
- 当前扫描结果: 10 个业务模板均存在，但均没有 AcroForm 字段。
- 后续 10 个业务模板都需要坐标 mapping。

### 第四阶段 PDF 坐标映射工具

- 内部静态工具页面: `frontend/public/zei-pdf-position-debug.html`
- 本地访问: `http://localhost:5173/zei-pdf-position-debug.html`
- 线上访问: `http://43.139.37.150/sun/zei-pdf-position-debug.html`
- 不加入正式菜单。
- 工具可选择模板、预览 PDF 页面 PNG、切换页码、加载 / 保存 mapping、点击定位、拖动字段区域、方向键微调、导入常用字段、生成测试 PDF。
- 字段支持 `test_value`, `width`, `height`, `align`, `valign`, `max_lines`, `letter_spacing`, `render_mode`, `split_pattern`, `parts`, `box_count`, `start_x`, `box_width`, `box_gap`。
- `render_mode=text` 用于公司名、姓名、地址等连续文字。
- `render_mode=split` 用于年 / 月 / 日、电话分段等固定多个区域，使用 `split_pattern` 和 `parts` 分别定位。
- `render_mode=boxes` 用于 My Number、邮编等每个字符需要独立落格的场景。
- 导入常用字段会填入合理测试内容，例如 `company_name=SUNRISE日晟鴻達株式会社`、`employee_my_number=123456789012`。
- 保存 mapping 前会自动备份已有 JSON 为 `{template_key}.backup.YYYYMMDDHHMMSS.json`。
- 测试 PDF 写入每个字段的 `test_value`；为空时才回退到 `label` 或 field key。测试 PDF 仅用于确认位置、字号、宽高、换行、对齐和拆分效果，不属于正式业务 PDF。
- 如果测试内容放不进字段区域，后端会返回 warning: `字段内容超出范围：field_key`。
- 原始 PDF 模板不能被覆盖。

### 正式 PDF 第一份

- 已支持模板 key: `social_insurance_payment_certificate_power_of_attorney`
- `generate_tax_renewal_template_pdf(record, template_key)` 返回 PDF bytes。
- 内部统计包含 mapping 字段数、成功写入字段数、跳过空字段数、warning 字段。
- 当前 mapping 中 `establishment_symbol`（記号）和 `establishment_number`（事業所番号）使用 `boxes`，分别为 4 格和 6 格；每个字符单独写入一个格子。
- 正式生成器兼容旧日文字段 key，并映射到 `establishment_symbol`, `establishment_number`, `application_reason`, `fiscal_start_year_jp`, `company_address`, `representative_name`, `agent_name` 等真实数据字段。
- 社会保险正式 PDF 固定使用并嵌入 `backend/assets/fonts/YuMincho.ttf`；缺失时直接报错，不 fallback 到 dengxian。
- 当前验证 warning 为空。

### 新建 / 编辑表单动态字段

- `tax_renewal_templates.py` 的模板对象包含 `required_fields`。
- 前端 Drawer 会根据当前 `selected_templates` 合并 `required_fields`，只显示所选 PDF 实际需要的字段。
- 未选择 PDF 时，只显示基础信息、模板选择、公司 / 客户 / 员工套用资料入口、备注，不展开大量详细字段。
- 所需字段按 Collapse 分组显示: 公司信息、申请人信息、代理人信息、年度 / 决算期间、税务信息、员工信息、抚养人信息。
- 保存时只校验当前所选 PDF 对应的 `required_fields`，隐藏字段保留在 `form_data` 中不清空。
- 社会保险模板当前 required fields:
  - `company_name`
  - `company_address`
  - `representative_name`
  - `representative_position`
  - `establishment_symbol`
  - `establishment_number`
  - `application_reason`
  - `fiscal_period_start`
  - `fiscal_period_end`
  - `agent_name`
  - `agent_address`
  - `agent_phone`
  - `agent_relationship`
  - `submit_date`

## 4A. 案件业务模块现状

状态: 案件详情已收束为案件基本信息、当前进捗、案件進捗・必要資料、进度记录。Task 功能已从前端下线（后端保留）。

### 页面和路由

- 案件列表: `frontend/src/pages/CasesPage.vue`
- 案件详情: `frontend/src/pages/CaseDetailPage.vue`
- 担当者管理: `frontend/src/pages/EmployeesPage.vue`
- Route:
  - `/cases`
  - `/cases/:id`
  - `/employees`
  - `/tasks`（仍注册，但菜单已移除，见下方 Task 章节）
- Menu: 案件業務 -> 案件一覧、案件・担当設定管理、顧客管理、会社管理（タスク一覧已从菜单移除；担当者管理没有独立菜单项，通过案件・担当設定管理页或案件详情内的按钮跳转 `/employees`）

### 当前保留范围

- 案件一览
- 案件详情
- 客户
- 公司
- 担当者管理
- 进度记录（進捗履歴 + 進捗記録 Timeline）

### 暂时隐藏范围

- 材料上传
- 文件管理
- 费用管理
- 独立 Reminder 功能
- 邮件、通知、日历、定时任务
- Task（タスク）—— 案件详情内嵌的 Task 管理（一覧、追加、编辑、完了/保留/删除）已整体下线；タスク一覧菜单项已移除。原因：实测全库仅 2 条 Task 记录（9 个案件里 7 个一条没有），而案件已有 `CaseChecklistItem`（`item_type=task`，手続事項）在真实承担同样的"步骤+负责人+完成状态"职责且有 10 条真实数据在用，Task 是重复且未被采用的功能。

注意: 后端已有模型和 API 不删除；当前只在前端入口和案件详情中隐藏暂缓功能。

### 案件详情「現在の進捗」卡片

`frontend/src/pages/CaseDetailPage.vue` 的「現在の進捗」卡片拆成两块:

- 常显区: 現在の進捗状态、最新進捗日。（原来的 タスク進捗/次のタスク/次の担当者 三项已删除，因为它们依赖已下线的 Task 数据，删除前这三项对 7/9 案件都是空的摆设。）
- 進捗履歴区: 用 `el-collapse`（默认收起，`progressHistoryCollapse`）展示 相談日、受任日、資料待ち開始日、書類作成中（必要資料完了日）、申請準備完了日、入管局受理日（`applied_at`，UI 标签已从「申請日」改为「入管局受理日」，字段本身不变）/受付番号、審査開始日、補正資料通知日/内容/截止日/提出日、通知日（許可/不許可，`result_notified_at`）、許可日或不許可日（同一 `result_received_at` 字段，按 `status === 'rejected'` 切换标签）/許可番号/結果備考、取下げ日、完了日，以及 審査期間/追加資料依頼まで/追加資料対応期間/案件処理期間。
- 所有進捗履歴字段只按「有值」显示，不用当前 `status` 做显示与否的过滤条件（许可日/不許可日只切换标签文字，不影响是否显示）。
- 折叠区底部有一个次要文字链接「過去の項目を修正」，见下方「進捗修正」小节。

原来的「進捗変更」+「進捗情報を編集」两个按钮、以及后来一度合并成的单一大表单弹窗，本轮**全部推翻重做**，改成一个更贴近真实业务流程的「進捗を更新」小弹窗 (`progressUpdateDialogVisible` / `progressUpdateForm`)：

- 「新しい進捗」下拉直接用 `caseStatusOptions`（已按业务顺序重排，见下方），不再有「現在の進捗を維持」这种特殊选项——重新选择当前状态本身就是一个合法操作（用于覆盖更新该状态关联的日期/编号，见下）。
- 提交**始终**调用 `changeCaseStatus`（`change-status` action，`status_service.change_case_status`），不再区分"状态是否变化"走不同接口；warnings/force 二次确认逻辑完全沿用未改动。
- 弹窗字段按选中的 `new_status` 动态显示，只出现这个状态真正需要的 1-3 个字段（照搬 `status_service._apply_status_business_fields` 里每个状态实际读取的 payload key，逻辑上一一对应，不再一次性铺开 13 个字段）：
  - `consultation`/`accepted`/`collecting_documents`/`preparing_documents`/`ready_to_apply`/`under_review`：不显示额外字段（这 6 个状态的日期由后端 `_apply_if_empty` 自动打点，只在首次进入时写入，重复选择不会覆盖——刻意保留这个"历史节点不可误改"的行为，因为「審査期間」「案件処理期間」等统计依赖这些日期稳定）。
  - `applied`：入管局受理日 + 受付番号。
  - `additional_documents`：補正資料通知日 + 内容 + 補正資料截止日。
  - `additional_documents_submitted`：補正資料提出日。
  - `approved` / `rejected`：通知日 + 許可日/不許可日 +（仅 approved）許可番号 + 結果備考。
  - `withdrawn`：取下げ日。
  - `completed`：完了日。
  - 这 7 个状态的日期都走后端 `_apply_payload_field`（无条件覆盖写入），所以重复选择同一个状态、改一下日期或编号再提交，就是"更新"这个动作——不需要额外的模式切换。
- 「変更日」只在选中状态与当前状态不同（真正的状态转换）时才显示，因为它只影响 `change_case_status` 的 `status_changed_at` 和各状态"首次打点"的默认值。
- 「備考」默认折叠，点击「備考を追加」才展开（`progressUpdateNoteVisible`），减少默认弹窗高度。

`result_notified_at`（通知日）和 `additional_documents_due_at`（補正資料截止日）不在 `status_service.PROGRESS_INFO_FIELDS` 白名单里，也不在 `_apply_status_business_fields` 读取的 `status_payload` key 里 —— 提交时前端单独比较这两个字段是否变化，变化则额外调用一次 `updateCase(caseId, {...})`（走 `CaseViewSet` 默认的 `PATCH /api/cases/{id}/`，`CaseSerializer` 已包含且可写这两个字段，无需改后端）。

### 進捗修正（過去の項目を修正）

新增次要入口，用于补录历史数据或修正录入错误，**不改变 `status`**：

- 入口：進捗履歴折叠区底部的文字链接，打开 `correctionDialogVisible` / `correctionForm` 弹窗。
- 内容：14 个进捗检查点对应的全部 18 个字段（相談日、受任日、資料待ち開始日、書類作成中/必要資料完了日、申請準備完了日、入管局受理日、受付番号、審査開始日、補正資料通知日、補正資料内容、補正資料截止日、補正資料提出日、通知日、許可日/不許可日、許可番号、結果備考、取下げ日、完了日）全部可自由编辑，包括平时"只认第一次"的 6 个自动打点字段——这是它存在的意义：日常快速流程为了保护统计数据不允许覆盖这些日期，但补录历史数据/修正录入错误时需要能直接改。
- 提交逻辑（`submitCorrection` / `buildCorrectionPayload`）：逐字段比较 `correctionForm` 和当前 `caseDetail`，只把真正变化的字段打包成 `Partial<CasePayload>`，调用 `updateCase`（标准 `PATCH /api/cases/{id}/`，不经过 `status_service.py` 的任何业务规则/警告）。没有变化则提示"変更がありません"，不发请求。
- 保存成功后，前端手动调用 `createTimeline` 补一条 Timeline（标题「進捗情報を修正」，内容是每个变化字段的"旧值 → 新值"列表），因为走 `updateCase` 不会像 `change_case_status`/`update_case_progress_info` 那样自动写 Timeline。这是本次唯一一处前端主动补 Timeline 的地方。

### caseStatusOptions 排序

`frontend/src/utils/caseStatus.ts` 的 `caseStatusOptions` 已从原来的随意顺序改成业务时间顺序：相談中 → 受任済み → 資料準備中 → 書類作成中 → 申請準備完了 → 申請済み → 審査中 → 追加資料対応中 → 追加資料提出済み → 許可 → 不許可 → 取下げ → 完了。下拉选择时从上到下就是真实办案流程。

### 顧客通知文案 / 顧客向け材料案内 简化

案件详情页「顧客通知文案」(`customerNoticeOptions`) 和 案件・担当設定管理页「顧客向け材料案内」(`materialNoticeOptions`) 这两处生成客户材料清单文案的工具，原来都是"文案类型 + 语言 + 3-6 个显示开关"的组合，操作繁琐。已精简：

- 顾客名/案件类型/案件番号/取得場所/必要内容/注意事項这些字段本来就是文案该有的内容，去掉可选开关，永远显示。
- 只保留「未完了のみ」一个开关（仅案件详情页版本有意义，因为只有真实案件才有"已完成/未完成"状态；模板预览版本没有这个开关）。
- 「未完了のみ」的默认值跟着"文案タイプ"联动：选「未完了資料リマインド」自动勾选，其余类型自动不勾选（`applyNoticeTypeDefaults`），用户仍可手动覆盖。

### 案件・担当設定管理里的「案件進捗」设置已隐藏

`CaseStatusSetting` 表和 `Case.status` 字段没有关联，编辑它不会影响任何实际案件的进捗，是历史遗留的摆设功能。已从 `frontend/src/pages/CaseChecklistTemplatesPage.vue` 的「案件関連設定」`el-tabs` 中移除「案件進捗」(`name="case-status"`) 这个 tab，以及仅供它使用的前端代码。

后端 `CaseStatusSetting` 的 model / API / admin 保持不变，只是前端不再提供入口，遵循本项目一贯的"暂时隐藏功能不删除后端"做法。

### 案件・担当設定管理页面精简

`frontend/src/pages/CaseChecklistTemplatesPage.vue` 原来同时塞了分类设置（tabs）、Checklist 模板构建器、和一份完整的担当者（Employee）CRUD，内容过多过杂。已调整：

- 删除页面里重复的「担当者管理」卡片（原来的新增/编辑/查询跟 `/employees` 页面完全重复维护同一份数据），改成一个跳转按钮「担当者管理を開く」→ `router.push('/employees')`。
- 各 tab 顶部原来常驻的「使用場所/影響範囲」`el-alert` 大段说明文字，改成标题旁边一个 `QuestionFilled` 小图标 + `el-tooltip`，悬停才显示，默认不占版面。
- 「Checklistテンプレート」区块同样把原来的说明 `el-alert` 改成小标题 + tooltip 图标。
- 「案件種別」「申請区分」两个 tab 的表格和编辑弹窗去掉了「内部code」列/输入框——排查确认这个字段前后端都没有任何业务逻辑消费它，纯摆设（跟真正驱动案件编号生成的「案件番号略称」`number_abbreviation` 完全是两回事，后者继续保留且必须保留）。后端不受影响：`CaseTypeMasterSerializer`/`CaseApplicationCategorySerializer` 的 `create()` 仍会在没收到 `code` 时用名称自动生成一个，满足数据库唯一约束。
- 「取得場所・準備者区分」这个原本完全不起作用的 tab（详见下方「よくある項目」小节）已被替换。

### よくある項目（ChecklistItemPreset）—— 案件事項的常见项目对照表

新增功能，解决"案件事項/Checklistテンプレート项目每次都要重新手打取得場所"的问题，同时替换掉原来完全没被真正使用过的「取得場所」`AcquisitionPlacePreset`/「準備者区分」`ResponsiblePartyPreset` 两个设置（那两个表本身在实测中被证实：改了也不影响任何地方——Checklist 项目的取得場所是纯自由文本、準備者绑定的是前端写死的枚举，从未真正读取过这两张表；这两个模型/API 保留不删，只是前端不再展示，遵循一贯做法）。

后端:

- 新模型 `ChecklistItemPreset`（`backend/apps/cases/models.py`）：`name`（唯一）、`category`、`acquisition_place`、`responsible_party`（复用 `CaseChecklistTemplateItem.RESPONSIBLE_PARTY_CHOICES`）、`required_details`、`sort_order`、`is_active`。Migration: `apps/cases/migrations/0011_checklistitempreset.py`。
- API: `/api/checklist-item-presets/`（`ChecklistItemPresetViewSet`，支持 `search` 按名称过滤，`is_active`/`ordering` 同其他预设表；分页 `page_size=200`，因为这张表条目数会持续增长，不能用全局默认的 20 条分页把设置页列表截断）。
- 标准数据种子：`POST /api/checklist-item-presets/seed-standard/`（`seed_standard_checklist_item_presets`，位于 `backend/apps/cases/demo_data.py`）。内置约 51 条，取材于出入国在留管理庁官网（経営・管理、技術・人文知識・国際業務、留学、高度専門職、永住許可、家族滞在等在留資格的公開必要書類清单），每条含分类/取得場所/準備者。用 `get_or_create` 实现，**只创建不覆盖**——重复点击不会覆盖用户已经手动修改过的条目，也不会重复创建。

前端:

- 设置页新 tab「よくある項目」（`frontend/src/pages/CaseChecklistTemplatesPage.vue`，替换原「取得場所・準備者区分」）：表格 + 独立的新增/编辑弹窗（`checklistItemPresetDialogVisible`/`checklistItemPresetForm`，不复用其他类型共用的那个通用 `settingDialog`，因为字段形状差太多），外加「標準項目取込」按钮调用种子接口。
- Checklist 项目的「事項名」输入框（案件详情页 `CaseDetailPage.vue` 的案件事項弹窗、设置页 `CaseChecklistTemplatesPage.vue` 的模板项目弹窗，两处都改）从纯输入框/纯历史文本自动补全，升级成「よくある項目 + 历史名称」合并建议列表：优先展示对照表里匹配的名称，选中后自动把分类/取得場所/準備者/必要内容一起带出来（`handleChecklistItemNameSelect`/`handleItemNameSelect`），历史输入过的其他名称仍作为补充候选（不做自动填充，跟以前行为一致）。自动填充只在**选中建议时**触发，手动打字不受影响，且只在目标字段为空时不做特殊限制——选中即覆盖，因为选中本身就是用户的明确操作。

### 顧客通知文案 / 顧客向け材料案内 按準備者分组

案件详情页「顧客通知文案」和设置页「顧客向け材料案内」这两处生成客户材料清单文案的功能，现在会按 Checklist 项目的「準備者」字段分组：

- 準備者是「顧客本人」「会社」（或未设置）的项目 → 照常出现在"请您准备以下材料"正文里，附带取得場所/必要内容/注意事項。
- 準備者是「本公司代办」「行政書士」「税理士」的项目 → 单独列在文案末尾一个新增的说明段落里（"以下事项由我方/税理士等代为办理，您无需准备，仅供您了解进度"），只显示项目名称和取得場所，不要求客户采取行动，但仍然让客户知道这件事存在、事务所正在处理。
- 这个分组只影响文案生成逻辑本身（`buildCustomerNoticeText`/`buildMaterialNoticeText` 新增 `isAgencyHandledParty` 判断），不影响 Checklist 项目数据本身，也不影响案件详情页 Checklist 卡片的正常展示（那里仍然显示全部项目）。

### 新規受付（ReceptionNewPage.vue）案件種別修复

`frontend/src/pages/ReceptionNewPage.vue` 原来的「案件種別」是前端写死的一份自由文本列表（`constants/options.ts` 的 `caseTypeOptions`，与 `案件・担当設定管理` 配置的 `CaseTypeMaster` 完全无关），「ステータス」也是另一份写死的、跟 `Case.STATUS_CHOICES` 完全不匹配的中间态标签列表。后端 `ReceptionSerializer.create()`（`backend/api/serializers.py`）过去直接把这些自由文本塞进 `Case.objects.create(case_type=..., status=...)`，而 `Case.save()` 强制要求新建案件必须有 `case_type_master`/`application_category`（缺了会抛出 `django.core.exceptions.ValidationError`，DRF 默认异常处理不认识这个异常类型，会变成未处理的 500）——也就是说这个入口过去提交必然报错，是一个真实存在但从未被走通过的 bug，不只是"两处案件種別显示不一致"这么简单。

修复:

- 前端：「案件種別」改成跟 `CasesPage.vue`/`CustomerDetailPage.vue`/`CompanyDetailPage.vue` 一致的 `listCaseTypeMasters()` 下拉（绑定 `case_type_master` 外键），新增「申請区分」下拉（`listCaseApplicationCategories()`，绑定 `application_category`）。删除「ステータス」字段——跟案件一覧的新建表单一样不再询问，让后端用 `Case.status` 的默认值（`accepted`，受任済み）。
- 后端：`ReceptionCaseSerializer` 的 `case_type`/`status` 字段替换成 `case_type_master`/`application_category`（`PrimaryKeyRelatedField`，各自只接受 `is_active=True` 的选项），`ReceptionSerializer.create()` 改成把这两个外键传给 `Case.objects.create(...)`。校验现在会经过 DRF 序列化器正常走 400 错误（而不是深埋在 `Case.save()` 里的未处理异常）。
- 移除了不再使用的 `frontend/src/constants/options.ts` 里的 `caseTypeOptions`。

### 顧客・会社新建流程改造（收束成 Lead-first 模型）

原来「顧客一覧的"新規顧客"弹窗」「会社一覧的"新規会社"弹窗」「新規受付（顧客+家族+会社+案件一次性创建）」三条独立的顾客创建路径并存，字段完全重复，而且要不要案件这件事三条路径还互相矛盾。参照 CRM 的 Lead → Contact → Opportunity（Salesforce/HubSpot）、法律行业的 Intake Form → Matter（Clio Grow）思路，把"顾客第一次联系我们"这个自然事件对应的新規受付，收束成唯一的顾客创建入口。

- **`backend/api/serializers.py`**：`ReceptionSerializer` 的 `case` 字段改成 `required=False`，`ReceptionCaseSerializer` 新增 `validate()`——`case_type_master`/`application_category` 要么两个都填要么两个都不填，只填一个会报错。`ReceptionSerializer.create()` 只在 `case_data` 有实际内容时才创建 `Case` 和对应的 Timeline。`customer` 仍然必填（既然是"受付"，总得知道是谁来了）。返回的 `case`/`case_number` 现在可能是 `null`。
- **`frontend/src/pages/ReceptionNewPage.vue`**：「案件情報」卡片去掉必填校验，加了一句提示"まだ案件化しない場合は空欄のままで構いません"（还不确定要不要立案的话，留空即可）。新增 `validateCase()` 校验案件種別/申請区分必须同时填或同时空。提交成功后，如果 `result.case` 有值，跳转案件详情（原行为不变）；没有则跳转顾客详情。
- **`frontend/src/pages/CustomersPage.vue`**：删掉「新規顧客」按钮和创建逻辑（连 `createCustomer` 的 import 都移除了），弹窗变成纯编辑用途，标题/保存按钮文案都固定死。页头按钮换成「新規受付へ」，跳转 `/reception/new`。**`frontend/src/pages/CompaniesPage.vue` 特意没有同步改**——因为 `ReceptionSerializer` 里 `customer` 必填而 `company` 可选，如果把会社一覧的「新規会社」也删了，"只想给一个已有顾客补充公司信息"这种情况（`CustomerDetailPage.vue` 的关联会社板块是纯展示，没有创建公司的能力）就没有路径可用了。跟顾客不同，公司没有"有人上门"这种自然触发事件，单独建公司的需求是合理存在的，所以保留不动。
- **`frontend/src/pages/CustomerDetailPage.vue`**：家族信息的新增/编辑，从弹窗 `el-dialog` 改成**页面内联编辑**。点"家族を追加"或某张卡片的"編集"，会在卡片列表前面就地展开一个编辑表单（用 `familyEditTarget` 是 `'new'` 还是具体某个 `id` 来判断，同一时间只能展开一个），保存后收起、回到卡片视图。目的是消除"要在弹窗里另外填一遍"这种跟"顾客来了才开始记录"的自然流程不搭的别扭感。删除、添加案件的操作流程没有变。

### 案件类型分类问题（未处理，留给用户决策）

排查发现现有 9 个案件里 8 个的 `case_type_master` 都落在兜底类型「その他」，因为 `CaseTypeMaster` 目前只有 6 个签证相关类型 + その他，覆盖不了税務、許認可申請等实际业务线；案件列表显示的"案件種別"用的还是旧的自由文本 `case_type` 字段，跟结构化的 `case_type_master` 早已脱节，导致分类问题平时看不出来。这个问题涉及新增哪些正式类型、把哪个案件改成哪个类型，属于需要用户确认的业务判断，暂未处理，需要时再单独讨论方案。

### Task（已从前端下线，后端保留）

Task 定位仍是案件内部工作步骤和备忘录，但**案件详情内嵌的管理界面已删除**，タスク一覧菜单项已移除，`/tasks` 路由和只读列表页 `frontend/src/pages/TasksPage.vue` 仍保留（无法新增，因为唯一的创建入口在案件详情，已被移除）。后端 Task 模型、API、`api/tasks.ts` 前端封装均未改动。

如果之后要恢复或替代 Task，建议优先考虑扩展 `CaseChecklistItem`（`item_type='task'`）而不是重新启用独立 Task 模型，因为后者是当前真正被使用的步骤追踪机制。

Task 字段（后端保留，供将来参考）:

- `case`
- `title`
- `description`
- `responsible_employee`
- `status`
- `sort_order`
- `due_date`，API 别名 `planned_completion_date`
- `completed_at`
- `created_at`
- `updated_at`

Task 状态: `pending`(未開始) / `in_progress`(進行中) / `completed`(完了) / `paused`(保留) / `cancelled`(取消)。

API: `/api/tasks/`、`/api/tasks/{id}/`，支持 `?case={case_id}`。案件列表 API 仍返回 `task_total_count`/`task_completed_count`/`next_task_title`/`next_task_responsible_employee_name`（后端字段未删，只是案件详情不再展示）。

### 担当者管理

担当者复用现有 `Employee`。

后端:

- Model: `Employee`
- API: `/api/employees/`
- 支持 `search` 查询 `name`, `email`, `phone`
- 支持 query: `?is_active=true` / `?is_active=false`

前端:

- 页面: `frontend/src/pages/EmployeesPage.vue`
- 路由: `/employees`
- 功能: 担当者一覧、新規追加、編集、有効 / 無効切换、検索
- 入口: 案件・担当設定管理页「担当者管理を開く」按钮跳转；没有独立主菜单项。

## 4B. 系统安全与账号管理

用户反馈"后台（Django Admin）基本无用"，转而要求：把マイナンバー加密、给登录加防爆破、把账号管理搬到前端设置页。三件事都已实现。

### my_number 字段加密

- 新增 `backend/apps/common/crypto.py`（`encrypt_text`/`decrypt_text`，用 `cryptography` 的 Fernet 对称加密）和 `backend/apps/common/fields.py`（`EncryptedCharField`，`CharField` 子类，`get_prep_value` 写入时加密、`from_db_value` 读取时解密；解密失败时原样返回，用于兼容尚未跑数据迁移的旧明文行）。
- 应用范围：`Customer.my_number`、`FamilyMember.my_number`（`backend/apps/customers/models.py`）、`CompanyStaff.my_number`（`backend/apps/companies/models.py`），字段类型从 `CharField(max_length=30)` 改成 `EncryptedCharField(max_length=255)`（Fernet 密文比明文长很多，30 位不够放）。
- 迁移分两步：先 `AlterField` 改字段类型（`customers/migrations/0005_...`、`companies/migrations/0006_...`），再用单独的数据迁移（`customers/migrations/0006_encrypt_my_number_data.py`、`companies/migrations/0007_encrypt_my_number_data.py`）把已有明文行重新 `save()` 一次，触发加密。两步分开是为了让 `from_db_value` 的"解密失败就当作旧明文"兜底逻辑在数据迁移阶段生效。已在本地验证：迁移后数据库里存的是 Fernet 密文，ORM 读取仍能拿到正确明文。
- **代价**：Fernet 密文是非确定性的（同一明文每次加密结果都不同），所以 Django Admin 的 `search_fields` 没法再对 `my_number` 做部分匹配搜索——已经把 `my_number` 从 `CustomerAdmin`/`FamilyMemberAdmin` 的 `search_fields` 里删掉。如果以后真的需要"按マイナンバー搜索"，得另外加一个 HMAC 盲索引字段，目前没做。
- `FIELD_ENCRYPTION_KEY`：新增的 Django setting（`backend/config/settings.py`），从环境变量 `FIELD_ENCRYPTION_KEY` 读取，本地 `.env`/`.env.example` 已写好示例值/占位符。**生产环境 `.env.prod` 必须单独生成一个真实密钥并写入，且此后不能再改**，改了旧数据就再也解不开了（见 `docs/DEPLOY.md`）。

### django-axes 登录防爆破

- `backend/config/settings.py`：`INSTALLED_APPS` 加 `axes`，`AUTHENTICATION_BACKENDS` 设为 `['axes.backends.AxesStandaloneBackend', 'django.contrib.auth.backends.ModelBackend']`，`MIDDLEWARE` 末尾加 `axes.middleware.AxesMiddleware`。`AXES_FAILURE_LIMIT = 3`、`AXES_LOCKOUT_PARAMETERS = ['username']`（按用户名锁，不看 IP）、`AXES_COOLOFF_TIME = 1`（1 小时后自动解锁）、`AXES_RESET_ON_SUCCESS = True`。
- 因为 axes 是挂在 Django 认证后端上的，`/admin/login` 和自定义的 `/api/auth/login/`（`backend/apps/authentication/views.py` 的 `login_view`）**都会自动受保护**，不需要分别接线。
- `login_view` 额外加了一步：调用前先用 `AxesProxyHandler.is_allowed()` 检查是否已被锁定，锁定时直接返回 403 + `get_lockout_message()` 的提示文案，而不是走到 `authenticate()` 之后才发现返回 `None`（否则锁定期间会被误判成"用户名或密码错误"）。
- 本地已用 Django shell 模拟连续 4 次错误登录验证：前 3 次返回 401，第 4 次变成 403 + 锁定提示；`python manage.py axes_reset` 可以手动解锁。

### 前端账号管理（`/settings`）

- 原来的 `/settings` 路由指向占位页 `PlaceholderPage`，现在换成真正的 `frontend/src/pages/SettingsPage.vue`，分两块：
  - **パスワードを変更**：所有登录用户都能用，需要输入当前密码校验通过后才能改，调用 `POST /api/users/change-password/`。
  - **アカウント管理**：只有 `auth.user.is_superuser` 为真时才渲染这块（`v-if="isSuperUser"`），包含账号列表、「新規アカウント追加」、每行的「パスワードを再設定」「有効化・無効化」。新建账号目前不给 `is_staff`/`is_superuser`，纯前端登录账号，不获得 Django Admin 权限。
- 后端新增 `backend/apps/authentication/serializers.py`（`SystemUserSerializer` 只读展示、`SystemUserCreateSerializer` 建号、`ChangeOwnPasswordSerializer` 自助改密（校验旧密码）、`ResetPasswordSerializer` root 强制重置（不需要旧密码））和 `backend/apps/authentication/permissions.py`（`IsSuperUser`）。
- `apps/authentication/views.py` 新增 `SystemUserViewSet`：`get_permissions()` 按 `self.action` 区分——`change_password` 只要求登录，其余（`list`/`create`/`retrieve`/`reset_password`/`partial_update`）都要求 `IsSuperUser`；`http_method_names` 去掉了 `put`/`delete`（不允许整体替换或硬删除账号，只能改 `is_active`）；`partial_update` 强制只准改 `is_active` 一个字段，改别的字段会 400。路由注册在 `backend/api/urls.py` 的 `router.register('users', SystemUserViewSet, basename='system-user')`。
- 权限边界已用 Django test client 分别以 root 和普通用户身份跑过一遍（列表/建号/强制改密/改自己密码/越权改别人密码），也用真实浏览器（临时注入本地测试 session cookie，没有走真实登录表单）走了一遍新建账号的 UI 流程，两种身份下界面表现符合预期。
- Employee 和 `auth.User` 之间**没有建立关联**——这次的账号管理是独立于 `Employee`（担当者）体系之外的登录账号管理，如果以后需要"担当者一建号就自动能登录"这种联动，需要单独设计。

## 5. 清風合格通知書模块现状

状态: 待开发 / 暂停处理。

要求:

- 不删除现有代码。
- 不修改现有功能。
- 后续不要继续围绕清風合格通知書开发，除非用户重新明确要求。

### PDF 模板和 mapping

模板目录:

- `backend/assets/pdf_templates/visa_return/`

当前文件:

- `visa_tem.pdf` - 当前 AcroForm 模板。
- `form_field_mapping.json` - AcroForm 字段映射。
- `visa_1.pdf` / `visa_2.pdf` - 旧坐标 fallback 模板。
- `field_positions.json` - 旧坐标 fallback 坐标。

### AcroForm 填充逻辑

主逻辑在:

- `backend/apps/accounting/visa_return_pdf.py`

流程:

1. 优先使用 `visa_tem.pdf` + `form_field_mapping.json`。
2. 从 `VisaReturnApplication` 根字段、`form_data`、`guarantor_snapshot` 组装变量。
3. 根据 mapping 写入 AcroForm 字段。
4. 支持 text / choice / radio 等字段。
5. 填充后执行 flatten，把表单值固化为普通 PDF 内容。
6. 如果 AcroForm 分支失败，fallback 到旧坐标填充。

### 字体逻辑

返签 visa PDF 字体路径:

- `backend/assets/fonts/dengxian.ttf` - 当前优先字体。
- `backend/assets/fonts/NotoSansCJK-Regular.ttc`
- `backend/assets/fonts/SourceHanSans-Regular.otf`
- `backend/assets/fonts/NotoSansCJKjp-Regular.otf`
- `backend/assets/fonts/YuMincho.ttf`

当前逻辑:

- 优先使用 `dengxian.ttf`。
- 不写死系统字体路径。
- 如果只有 YuMincho，可能有简体中文字形缺失风险。

### 在日担保人模板功能

状态: 已存在。

Model:

- `VisaGuarantorTemplate`

字段包括:

- `name`
- `guarantor_name`
- `guarantor_name_en`
- `guarantor_phone`
- `guarantor_address`
- `guarantor_address_en`
- `guarantor_birth_date`
- `guarantor_nationality`
- `guarantor_visa_status`
- `guarantor_occupation`
- `guarantor_relationship`
- `guarantor_company_name`
- `note`
- `is_active`
- `sort_order`
- `created_at`
- `updated_at`

前端:

- 在 `VisaReturnApplicationsPage.vue` 内通过 Drawer 管理。
- 支持新增、编辑、搜索、停止模板。
- 在申请表中选择模板后，会复制到当前申请表单。

快照逻辑:

- 选择模板后写入 `guarantor_snapshot`。
- 同时写入相关 `form_data`。
- 模板后续修改不影响已保存申请记录。
- 当前没有给 `VisaReturnApplication` 增加模板外键。

### 返签 visa 表关键业务规则

- `x1` 到 `x6` 默认全部为 `no`，即 PDF 上选择「否」。
- 前端显示为「是 / 否」，不要再用不清楚的 boolean 让用户误会。
- `same` 默认是 `同上`，用于在日邀请人同上。
- `guarantor_nationality` 和 `guarantor_visa_status` 会组合输出为类似 `日本 / 永住者`。

### 家庭地址规则

当前新增字段在 `form_data` 中:

- `registered_address` - 户籍地址
- `current_address` - 现住址
- `home_address2` - 兼容旧 mapping / 旧逻辑

编辑旧记录:

- 如果 `current_address` 为空但 `home_address2` 有值，则回填 `current_address = home_address2`。

保存:

- 继续写入 `home_address2 = current_address || home_address2`，保持旧逻辑兼容。

PDF 输出:

```python
if registered_address and current_address:
    "户籍地址：{registered_address}\n现住址：{current_address}"
elif registered_address:
    "户籍地址：{registered_address}"
elif current_address or home_address2:
    "{current_address or home_address2}"
```

注意:

- 只有现住址时，不加「现住址：」标签。
- 两个地址都有时，户籍地址在上，现住址在下。

## 4. 返签 visa 调试工具

### 坐标调试工具

文件:

- `frontend/public/visa-position-debug.html`

用途:

- 内部工具。
- 显示旧 `visa_1.pdf` / `visa_2.pdf` 预览。
- 可拖动坐标并保存 `field_positions.json`。

### AcroForm 字段映射工具

文件:

- `frontend/public/visa-form-field-mapping.html`

后端:

- `backend/apps/accounting/visa_form_fields.py`
- API:
  - `/api/accounting/visa-form-fields/`
  - `/api/accounting/visa-form-fields/preview/`
  - `/api/accounting/visa-form-field-mapping/`

用途:

- 内部工具。
- 显示 `visa_tem.pdf` 的 AcroForm 字段框。
- 拖拽系统变量到 PDF 字段，保存 `form_field_mapping.json`。

注意:

- 不加入正式菜单。
- 不要随便破坏。
- 不要把这些工具变成客户使用页面。

## 5. 清風合格通知書 / PDF 添加文字功能

用户有时会写成「清風合同通知書」，但当前代码、菜单和模板实际是「清風合格通知書」。

### 当前状态

状态: 已存在。

菜单:

- 帳票管理 -> 清風合格通知書

路由:

- `/vouchers/seifu-notice`

前端:

- `frontend/src/pages/SeifuNoticePdfTextPage.vue`

后端:

- `backend/apps/accounting/seifu_notice_pdf.py`
- `backend/apps/accounting/urls.py`

API:

- `GET /api/accounting/seifu-notice-pdf/template/`
- `GET /api/accounting/seifu-notice-pdf/preview/?page=1`
- `POST /api/accounting/seifu-notice-pdf/generate/`

模板:

- `backend/assets/pdf_templates/seifu/合格通知書.pdf`

### 功能

- 显示 PDF 页面预览。
- 支持多页 PDF，虽然当前模板检测为 1 页。
- 支持页码切换。
- 点击 PDF 预览图添加文字对象。
- 文字对象可编辑内容。
- 文字对象可拖动调整位置。
- 可删除文字对象。
- 可在不同页添加不同文字。
- 生成新 PDF 并下载。
- 不覆盖原始 PDF。
- 保持原 PDF 页面尺寸和原有内容。
- 新增文字使用 PyMuPDF 写入矢量文本。
- 不把整页 PDF 渲染成图片后保存。

### 默认文字样式

- 字体: Adobe 黑体 Std
- 字号: 18 pt
- 颜色: `#383737`
- 写入方式: PyMuPDF `insert_text`

### 字体要求

后端只允许使用 Adobe 黑体 Std，不允许静默替换:

1. `backend/assets/fonts/Adobe 黑体 Std R.otf`
2. `backend/assets/fonts/AdobeHeitiStd-Regular.otf`
3. `backend/assets/fonts/AdobeHeitiStd.otf`

如果都不存在，必须明确报错:

```text
缺少字体文件：Adobe 黑体 Std
```

当前项目检测到:

- `backend/assets/fonts/Adobe 黑体 Std R.otf`

### 关键实现约束

- 生成 PDF 时不能覆盖 `合格通知書.pdf`。
- 生成 PDF 时不能把页面转成图片。
- 必须保持原始页面清晰度。
- 字体缺失时不能 fallback 到 YuMincho / dengxian / 默认字体。
- 坐标使用 PDF pt 坐标，左上原点，和 PyMuPDF 预览图坐标一致。

## 6. 当前已知注意事项

- 不要影响請求書・領収書。
- 不要影响返签 visa。
- 不要影响在日担保人模板。
- 不要影响 `visa-position-debug.html`。
- 不要影响 `visa-form-field-mapping.html`。
- 不要随便生成 migration。
- 不要覆盖任何 PDF 模板。
- 不要把正式 PDF 输出改成整页图片。
- 不要静默替换用户指定字体。
- 工作区可能已有多项历史未提交改动，不要随意 revert。
- 修改文件前先确认用户本轮允许范围。

## 7. 常用命令

### Backend

```bash
cd backend
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm run dev
npm run build
```

### Docker / Production

```bash
docker compose --env-file .env.prod build
docker compose --env-file .env.prod up -d
docker compose --env-file .env.prod exec backend python manage.py migrate
docker compose --env-file .env.prod exec backend python manage.py collectstatic --noinput
```

### Git

```bash
git status --short
git diff --stat
git add <files>
git commit -m "message"
git push
```

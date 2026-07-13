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

### 金额计算规则

当前规则非常敏感，不能改错:

- 用户输入的明细单价 / 金额是 **税込金额**。
- 固定税率: 10%。
- `total_amount` = 税込合计。
- `amount` = 税抜金额。
- `tax_amount` = 消費税。
- 税抜金额用税込合计反算:

```text
amount = round_half_up(total_amount / 1.1)
tax_amount = total_amount - amount
```

注意:

- 不要把用户输入金额当税抜再乘 1.1。
- 不要二次加税。
- PDF 明细中的单价和金额显示为税込。
- PDF 汇总显示: 税抜金額 / 消費税 / 税込合計。

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

状态: 案件详情已收束为案件基本信息、当前状态、工作任务和进度记录。

### 页面和路由

- 案件列表: `frontend/src/pages/CasesPage.vue`
- 案件详情: `frontend/src/pages/CaseDetailPage.vue`
- 担当者管理: `frontend/src/pages/EmployeesPage.vue`
- Route:
  - `/cases`
  - `/cases/:id`
  - `/employees`
  - `/tasks`
- Menu: 案件業務 -> 案件一覧、顧客管理、会社管理、担当者管理、タスク一覧

### 当前保留范围

- 案件一览
- 案件详情
- 客户
- 公司
- Task
- 担当者管理
- 进度记录

### 暂时隐藏范围

- 材料上传
- 文件管理
- 费用管理
- 独立 Reminder 功能
- 邮件、通知、日历、定时任务

注意: 后端已有模型和 API 不删除；当前只在前端入口和案件详情中隐藏暂缓功能。

### Task 定位

Task 是案件内部工作步骤和备忘录，用来查看案件做到哪一步、下一步做什么、由谁负责。

前端显示统一使用日文「タスク」，不要显示中文「工作任务」。

Task 字段:

- `case`
- `title`
- `description`
- `responsible_employee`
- `status`
- `sort_order`
- `due_date`，前端显示为 `planned_completion_date`
- `completed_at`
- `created_at`
- `updated_at`

Task 状态:

- `pending`: 未开始
- `in_progress`: 进行中
- `completed`: 已完成
- `paused`: 暂缓
- `cancelled`: 取消

规则:

- 状态改为 `completed` 且 `completed_at` 为空时，自动写入当前日期。
- 状态从 `completed` 改回其他状态时，可清空 `completed_at`。
- `planned_completion_date` 只是计划完成日期，不触发提醒。
- Task 按 `sort_order` 排序，案件详情中未完成优先显示。

### API

- `/api/tasks/`
- `/api/tasks/{id}/`
- 支持 query: `?case={case_id}`

案件列表 API 额外返回 Task 摘要:

- `task_total_count`
- `task_completed_count`
- `next_task_title`
- `next_task_responsible_employee_name`

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

Task 新增 / 编辑:

- 「担当者」下拉只加载有效 `Employee`。
- 允许为空，显示「未指定」。
- 已停用负责人不会出现在新建 Task 的可选列表中。
- 已有 Task 仍通过 `responsible_employee_name` 显示原负责人姓名；编辑旧 Task 时会保留一个「（無効）」选项避免丢失显示。
- 案件负责人和 Task 负责人不强制绑定。

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

# 2026-09-28 P2 Visa 一括导入分支（codex/p2-visa-import）

基于：`codex/p2-accounting` `e86e961`（直接接上会计分支的 migration，不需要合并用 migration）。未推送、未部署。Visa 仍在 `accounting/vouchers`，权限为 `accounting.use_visa`（初期只有李）。原有的「多人一括作成（贴付）」作为辅助入口保留。

## 流程与接口（`/api/accounting/visa-imports/`）

1. `GET template/`：下载标准模板 CSV（UTF-8 BOM）。
2. `POST parse/`：上传 CSV/XLSX（5MB、500 行以内）。
   - CSV 依次尝试 UTF-8(BOM) → Shift_JIS(cp932) → GB18030，也可以手动指定。
   - XLSX 返回工作表列表，可以按名称选择。
   - 以第一个非空行为表头，统计并跳过空行，按别名自动映射列。
   - 同一文件（SHA-256）以前导入过时给出警告。
3. `POST {id}/preview/`：按映射和共同项目（例：在日担保人），逐行返回**原值（raw）、转换后的值（value）、错误、警告**，错误不会被静默跳过。
   - 日期：`YYYY-MM-DD`、`/`、`.`、`年月日`、`YYYYMMDD`、Excel 日期和序列号。
   - 性别、婚姻状况：日文、中文、英文写法都能识别。
   - 护照号和电话按字符串处理，保留前导零；如果 Excel 里存成了数值，会提示前导零可能丢失。
   - 邮箱格式校验、必填检查。
   - 重复检测：同一文件内护照号重复，或与已登记申请的护照号重复。
4. `POST {id}/commit/`：两种创建方式。
   - 「只创建有效行，错误行出报告」：默认；
   - 「全部正确时才创建」：有错误时什么都不创建，返回 400。
   - 与已有申请重复的行默认跳过。
   - 同一 `request_id` 重复提交不会重复创建。
   - 修正错误行后再次提交时，已创建的行不会重复创建。
5. `GET {id}/error-report/`：错误行 CSV（行号、字段、原值、错误原因）。
6. `POST {id}/pdf-zip/`：把本批次创建的申请生成 PDF 打成 ZIP。某张 PDF 生成失败不影响其他，失败情况记在 ZIP 里的 `結果.txt` 和响应头中。

## 审计（全部敏感导出都记录）

- `visa_import_parse`：文件名、行数、哈希。
- `visa_import_commit`：件数，失败时记为 `denied`。
- `visa_import_error_report`、`visa_pdf_zip_export`。
- 原有的单张 PDF 下载也补上了 `visa_pdf_export`。
- AuditLog 和 `VisaImportBatch` 都不保存行数据本身；只有错误行会保存修正所需的原值。

## 前端

`VisaImportDrawer.vue`：上传 → 列映射（含共同项目）→ 预览（可以直接修改错误行的原值后重新校验）→ 结果（ZIP、错误报告、重试）。

## Migration

`accounting/0017_visa_import_batch`（新表 + 申请表新增 `import_batch`/`import_row_number`，加法）。

## 验证

- 后端 `python manage.py test`：238 项全部通过（会计分支的 226 项 + 本分支 12 项）。
- 前端 `npm run build` 通过，`npm run test:unit` 6 项通过；`makemigrations --check`：无差异。
- 浏览器实测：未完成。

## 已知限制

- 编码判定按顺序尝试，部分 GB18030 文本有可能被当作 Shift_JIS 解码成功，出现乱码。这种情况请在界面上手动指定编码。
- PDF 生成依赖现有模板文件；模板缺失的环境会在 ZIP 的结果文件中列出失败项。

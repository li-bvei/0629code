# 2026-09-28 P2 会计分支（codex/p2-accounting）

基于：`codex/p1-case-workspace` `dde7e4f`。未推送、未部署。保留 P0/P1 的 BusinessAccessPolicy、AuditLog、Case 权限和受保护下载。

## 实现

1. **Income/Expense 可选关联 Customer/Company/Case**（migration `accounting/0016_income_expense_party_links`，加法）
   - 关联案件需要对该案件有「变更」权限（因为会写 Timeline）：普通用户只能关联本人担当的案件；业务管理员虽能查看全部案件，也不能关联。
   - 顾客/公司必须在本人可见范围内（只能看到最小识别信息的对象不能关联）。
   - 只指定了案件时，自动带出案件的顾客和公司。
   - 收入沿用模块级权限（初期只有李），并做同样的关联检查。
2. **案件 ↔ 会计**
   - `GET /api/cases/{id}/accounting-summary/` 按会计权限范围汇总：支出看本人的，持有 `expense_view_all` 时看全员（只读）；收入和税务证明看各自模块权限。
   - 案件侧栏新增会计摘要（`CaseAccountingSummary.vue`），可以跳到带 `?case=` 筛选的支出一览。
   - 支出一览新增关联案件列，支出/收入表单新增关联选择；新增 `RemoteCaseSelect`，后端 `/api/cases/?search=` 只在本人范围内检索。
3. **支出分类**（`apps/accounting/category_suggestions.py`、`GET expenses/category-suggestions/`）
   - `category` 仍是自由文本，可以手动输入任意值。
   - 检索范围是分类主档加本人历史记录。
   - 规范名建议：吸收全角/半角、空格、「費用→費」等写法差异，并用同义词表提示「使用某某」；按不按都可以，照原样保存也行。
   - 推荐：按场所、费用对象、备注，在**本人**历史中按频率和新旧排序。即使持有 `expense_view_all` 也不参考他人记录。
   - 不改写旧数据；不使用外部生成式 AI。
4. **个人报销**
   - 仍是简单登记，没有新增审核、批准、支付、入账、退回等字段或流程（有测试确认）。
   - owner 隔离继续由后端强制；焦、周可以查看全部，但只能修改自己的记录。
5. **Timeline**
   - 支出关联或解除关联案件时记 `expense_recorded`，收入记 `accounting_linked`。
   - 只记录日期和分类，**不记金额，不记所有者**，避免能看案件的人看到他人的报销金额。
   - 关联时写审计 `expense_case_linked` / `income_case_linked`。

## 验证

- 后端 `python manage.py test`：226 项全部通过（P1 的 213 项 + 本分支 13 项）。
- 前端 `npm run build`：通过；`npm run test:unit`：6 项通过；`makemigrations --check`：无差异。
- 浏览器实测：未完成（与 P0/P1 同样的阻断项）。

# 2026-09-29 P2 集成分支（codex/p2-integration）

基于 `codex/p1-case-workspace` `dde7e4f`，依次合并：

1. `codex/p2-visa-import` `5f11af4`（含会计分支 `codex/p2-accounting` 全部提交，包括「精算済み」UI 废止 `91a91a8`）；
2. `codex/p2-documents` `6b3d050`。

未推送、未部署、未连接生产。

## 冲突处理

- 只有文档冲突（`AI_HANDOFF.md`、`DATABASE.md`、`DEVELOPMENT_PLAN.md`、`README.md`），手动合并：两侧段落都保留；`DEVELOPMENT_PLAN` 的 P2 进度表取会计/Visa 侧的 C7、C8、C10 与文件侧的 C9。
- 代码自动合并：`access_rules.py`（会计：IncomeRule/关联检查；文件：DocumentRule.prepare_create）改动在不同区段；`timelines/models.py`、`CaseDetailPage.vue` 无冲突。
- migration：`accounting/0016～0017` 与 `documents/0004` 分属不同 app，互不依赖，无需合并 migration。

## P2 收尾（分支 `codex/p2-polish`，基于 `codex/p2-c11-vouchers`）

- 支出一览「新規支出」快捷对话框改为与完整新增页相同的输入栏（共用组件 `components/accounting/ExpenseFormFields.vue`）：分类可检索/手输、规范名提示、本人历史推荐，以及 Case/Customer/Company 关联。
- 选择 Case 时自动带出该案件的 Customer、Company（仍可修改）；后端照旧强制检查案件「变更」权限和顾客/公司可见范围，403 时显示后端给出的理由。
- 不恢复「精算済み」；无后端改动，无 migration。
- 演示数据只写入本地预览库 `gyoseishoshi_erp_p2_preview`（脚本放在会话临时目录，不进入仓库、不作为 seed）：李本人的分类历史、一个无害测试 PDF（Checklist 关联→替换→归档→恢复）、符合模板的 Visa CSV/XLSX（2 条正常＋1 条错误，预览、提交、重复提交幂等、错误报告、PDF ZIP）。

## 验证

- 后端 `python manage.py test`：247 项全部通过。
- `makemigrations --check --dry-run`：No changes detected。
- 前端 `npm run test:unit`：6 项通过；`npm run build`：通过。
- 浏览器实测：未做（与 P0/P1 同样的阻断项，预览库 `gyoseishoshi_erp_p0_preview` 未迁移到本分支）。

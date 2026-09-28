# 2026-09-29 P2 集成分支（codex/p2-integration）

基于 `codex/p1-case-workspace` `dde7e4f`，依次合并：

1. `codex/p2-visa-import` `5f11af4`（含会计分支 `codex/p2-accounting` 全部提交，包括「精算済み」UI 废止 `91a91a8`）；
2. `codex/p2-documents` `6b3d050`。

未推送、未部署、未连接生产。

## 冲突处理

- 只有文档冲突（`AI_HANDOFF.md`、`DATABASE.md`、`DEVELOPMENT_PLAN.md`、`README.md`），手动合并：两侧段落都保留；`DEVELOPMENT_PLAN` 的 P2 进度表取会计/Visa 侧的 C7、C8、C10 与文件侧的 C9。
- 代码自动合并：`access_rules.py`（会计：IncomeRule/关联检查；文件：DocumentRule.prepare_create）改动在不同区段；`timelines/models.py`、`CaseDetailPage.vue` 无冲突。
- migration：`accounting/0016～0017` 与 `documents/0004` 分属不同 app，互不依赖，无需合并 migration。

## 验证

- 后端 `python manage.py test`：247 项全部通过。
- `makemigrations --check --dry-run`：No changes detected。
- 前端 `npm run test:unit`：6 项通过；`npm run build`：通过。
- 浏览器实测：未做（与 P0/P1 同样的阻断项，预览库 `gyoseishoshi_erp_p0_preview` 未迁移到本分支）。

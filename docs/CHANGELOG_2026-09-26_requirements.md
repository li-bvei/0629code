# 2026-09-26 需求与交接文档整理记录

> 2026-09-27 用户进一步确认报销和文件管理范围；Drive 混合方案、报销审批设想和 `强哥` 表处理已被后续决定覆盖。当前要求以 `CHANGELOG_2026-09-27_requirements_clarification.md` 和最新需求文档为准。

## 范围

本批次只整理 Markdown 文档，没有修改后端、前端、数据库、migration 或部署配置。

## 完成内容

- 新增 `DEVELOPMENT_REQUIREMENTS_2026-09-26.md`，完整记录模块独立原则、案件清理边界、材料与 Google Drive 安全方案、会计及个人报销、支出分类推荐、Visa CSV/XLSX 批量生成、帐票、不动产、权限、审计和迁移要求。
- 更新 `AI_HANDOFF.md` 的阅读顺序、当前 Git 同步状态、文档地图和最新需求摘要。
- 更新 `DEVELOPMENT_PLAN.md`，将多人权限、数据所有权、AuditLog、会计增强、Drive、Visa 和不动产纳入 P0–P3 计划。
- 同步修正 `PROJECT.md` 和 `ROADMAP.md` 中已被新要求覆盖的“暂不做权限/材料/费用”旧规划，同时保留多租户和复杂组织权限平台为范围外事项。
- 明确旧版“暂不设计复杂权限矩阵”的计划已被新需求覆盖。
- 更新 `docs/README.md` 文档索引。

## 当前 Git 基线

文档修改前：

```text
main = origin/main = de95411ea87cc981b3874237047722e54544c0ef
ahead/behind = 0/0
worktree = clean
```

## 验证说明

- 本批次应执行 Markdown 链接/结构、`git diff --check` 和文档内容一致性检查。
- 因未修改应用代码，本批次不重新声明后端测试或前端构建已经执行；最后一次应用验证仍以 `AI_HANDOFF.md` 的记录为准。

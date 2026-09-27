# 2026-09-27 需求修正记录

## 范围

本批次只修正 Markdown 需求和计划，没有修改应用代码、migration 或数据，也没有执行文件迁移。

## 用户最终确认

- 现有 Expense 全部是当前用户本人的报销数据。
- 报销保持当前简单登记方式，不新增提交、审核、批准、支付、入账或退回流程。
- 本阶段不迁移、不索引、不连接 Google Drive；只完善现有系统的 Document 文件管理。
- `LIST.xlsx` 的 `强哥` 工作表已经无用，不分析、不映射、不迁移。
- 可以开发新的内部利润分配功能，但必须独立设计，不能复用 `强哥` 表数据，也不能混入法定宅建台账。

## 同步修改

- `DEVELOPMENT_REQUIREMENTS_2026-09-26.md`
- `AI_HANDOFF.md`
- `DEVELOPMENT_PLAN.md`
- `ROADMAP.md`
- `README.md`

## 验证说明

- 本批次应执行 Markdown 引用、冲突标记和 `git diff --check` 检查。
- 因未修改应用代码，不重新声明后端测试或前端构建已经执行。

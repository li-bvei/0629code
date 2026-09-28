# 2026-09-28 P1 案件工作台本地实现

分支：`codex/p1-case-workspace`（worktree `../0629code-p1`，基于 P0 `be0e419`，未推送、未部署）
依据：`docs/SYSTEM_ARCHITECTURE.md`、`docs/DEVELOPMENT_PLAN.md` P1-B1～B7。P1 阶段只保留这一份 CHANGELOG。

## 范围与限制

- 不改变 13 个 Case 进捗状态；不删除 Task、Reminder、Document、Portal；不把会计、文件、不动产并入 Case。
- 不改变 P0 权限架构：所有新接口都经过 BusinessAccessPolicy（专用动作按「变更」判定）。
- 没有修改生产，没有开始 P2/P3。

## 实现

1. **Next Action / 待机**
   - Case 新增字段：`work_status`、`waiting_reason/note/since/until`、`next_action_assignee`、`next_action_blocked_reason`、`next_action_completed_at/by`。
   - 所有修改都走 `work_service`：`select_for_update` 事务 + Timeline + AuditLog。
   - 通用 PATCH 不能写这些字段，也不能写 `next_action` / `next_action_due_at`。
   - Next Action 的负责人必须能查看该案件（没有账号的担当者只做记录）。
   - 案件完了/取下/不许可时自动解除待机。进捗变为完了记 `case_completed`，从完了改回其他状态记 `case_reopened`，进捗变更另写审计 `case_status_changed`。
   - Dashboard 的 `waiting` 改为按 `work_status` 统计，旧口径保留为 `waiting_by_status`。
2. **Case Workspace Action Bar**（`components/case/CaseActionBar.vue`，只用 Dialog/Drawer）
   - 按钮：対応記録、資料受領、ファイル、入金、次の対応（设置/完成）、待機/解除、完了/再開。
   - 入金只在案件经过里记录一条（`payment_received`），会计数据引导到会计模块登记。
3. **今日作业台**
   - 接口 `GET /api/workbench/today/?scope=mine|all`，页面 `/workbench`。
   - 显示我的案件、我的 Next Action（负责人是我，或未指定负责人而案件担当是我）、我的待机案件；全体视图需要 `case_view_all`；可以在行内完成 Next Action、解除待机。
   - 账号未关联 Employee 时给出提示。
4. **Checklist 与 Document 联动**
   - 新增 `received_at`、`document` 字段和 `receive` action。只能关联同一案件、且在本人范围内的 Document，写 `document_received`，可以同时标记完成。
   - 不连接 Google Drive，文件仍然只能经受保护下载访问。
5. **Timeline 自动化**
   - 文件登记/替换 `document_uploaded`、资料受领 `document_received`、Checklist 完成、Waiting 开始/结束、Next Action 设定/完成、案件完了/再开、入金记录 `payment_received`。
   - 税务证明记录关联案件时记 `accounting_linked`，生成 PDF 时记 `pdf_generated`，会计数据留在会计模块。
6. **RemoteSelect**
   - 把检索状态抽到 `remoteSearch.ts`：只采用最后一次请求的结果，显示错误（以前会被静默吞掉），保留当前选中值的显示名，补取初始值。
   - 前端单元测试 `npm run test:unit`，用已安装的 esbuild + Node 内置 `node:test`，没有新增依赖。
   - 后端补充了顾客、公司、担当者检索的权限范围测试。

## AuditLog 事件（新增）

`case_next_action_set`、`case_next_action_completed`、`case_waiting_started`、`case_waiting_ended`、`case_payment_noted`、`case_status_changed`、`checklist_item_received`

## Migration

`cases/0018_case_work_status_next_action`、`cases/0019_checklist_item_document_link`：加法，不写数据。

## 验证

- 后端 `python manage.py test`：213 项全部通过（P0 的 189 项 + P1 新增 24 项）。
- 前端 `npm run test:unit`：6 项通过；`npm run build`：通过。
- `makemigrations --check`：无差异；`manage.py check`：0 issues；`git diff --check`：通过。
- **未完成**：浏览器实测（与 P0 同一原因：预览进程无法读取 venv）。

## 未做 / 与原计划的差异

- 「タスク」按钮没有单独实现：历史 Task 模块保持隐藏，由「次の対応」代替。
- 「snooze」没有单独实现：用修改期限代替。
- Expense 没有 case 外键，所以支出事件没有写入 Timeline（归 P2-C1）。

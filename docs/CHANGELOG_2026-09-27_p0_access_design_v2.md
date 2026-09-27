# 2026-09-27 P0 访问控制方案第 2 版修订记录

## 范围

本批次只修改 Markdown：`P0_ACCESS_CONTROL_DESIGN.md`（重写为第 2 版）、`AI_HANDOFF.md`、`DEVELOPMENT_PLAN.md`，并新增本记录。没有修改代码、数据库、nginx 或账号，没有创建 migration，没有提交 Git，也没有开始批次 1。

## 用户确认的修正

1. **BusinessAccessPolicy**：Django 的 `has_perm()` 对 active superuser 会自动放行，`ModelBackend` 对 superuser 返回全部权限（已核对 Django 4.2.30 源码）。业务权限因此改为统一策略：只读取 Group 和直接授权中的显式 `Permission`，不读取 `is_superuser`。所有 ViewSet、专用 action、导出、下载、Dashboard、图表共用一套规则注册表，并用覆盖测试和静态约束测试防止遗漏。Admin 和服务器维护仍使用 `is_superuser`/`is_staff`。必测“只有 superuser、没有业务 Group 的账号不能读取 Expense”。
2. **李**：`zbry6947@gmail.com`，唯一系统超级管理员，唯一初始 accounting_admin，拥有全部明确业务权限。受保护身份使用专用表 `authentication_protected_accounts`（FK，只能由服务器命令管理），不靠姓名，也不硬编码 ID。username 不能经 Web 修改，改名只能用服务器命令。
3. **焦、周**：业务管理员，初始 `expense_view_all`，没有 `change_all`/`export_all`，没有其他会计模块。只有在批次 8（权限矩阵、李恢复、回滚演练）全部通过后，才在批次 9 单独执行 `is_superuser=False`、`is_staff=False`。
4. **NAING** 不处理；**localdev** 只允许存在于本地开发环境，生产中存在并启用时部署检查失败。
5. **Q1～Q11 决定**已写入方案：生产按 username 匹配；没有完整会计权限不显示余额；其他会计模块初期只开放给李；无担当案件只有李能修改，受付默认担当为本人，未关联 Employee 时必须选择担当；搜索只返回最小识别字段；越出范围的证件遮罩；未立案顾客的完整敏感详情只有李可见；越出担当范围的下载需要 `document_download_all` 并写审计；降级后取消 Admin 资格；调试和演示端点生产完全禁用，保留的诊断功能需要李 + diagnostic 权限并写审计；不采用“登录即可下载”的过渡方案。
6. **AuditLog 下载语义**：`download_denied`、`download_authorized`、`download_started`，不记录 completed；nginx 的 access log 只作运维旁证。AuditLog 没有公开写入、修改、删除 API，后台只读，初期只有李可见。
7. **Expense 回填**：本地 1,300 条仅作本地统计。生产按“只读统计 → 备份 → dry-run → 显示目标 username/Employee → expect-count → ID 清单 → 用户确认 → 按清单回滚”执行。新增 Expense 的 owner 由后端强制填写。
8. **/media/**：保留为 P0-A8。切换 nginx 前先只读核对 API、前端、历史数据、PDF 中的引用。X-Accel 路径由 realpath 校验后的相对路径生成，不直接拼接文件名。

## 最终批次与需批准的数据操作

见方案 §11（批次 0～9）与 §12（D1～D12）。

## 未同步的文件（已于同日在 `CHANGELOG_2026-09-27_p0_docs_sync.md` 中同步）

本次按用户要求只更新了上述文件。以下文档中与第 2 版不一致的地方，等用户确认后再更新：

- `DEVELOPMENT_REQUIREMENTS_2026-09-26.md` §9.5 和 §13 中“会计 view_all 仅授予确认账号”：第 2 版中焦、周也有 `expense_view_all`。
- `DATABASE.md` §11.2 的 Group 名称，以及缺少受保护账号表。
- `README.md` 索引中缺少本记录。

## 验证

- `git diff --check` 通过。
- 未修改应用代码，不声明后端测试或前端构建已执行。

# 2026-09-27 P0 文档同步与受保护账号两阶段启用

## 范围

只修改 Markdown。没有开始批次 1，没有连接生产库，没有修改代码、数据库、账号或 nginx，没有创建 migration，也没有提交 Git。

## 同步内容

- `DEVELOPMENT_REQUIREMENTS_2026-09-26.md` §9.5：会计权限改为已确认（尚未实现）。李拥有全部业务权限和 `expense_view_all`/`change_all`/`export_all`；焦、周为业务管理员，拥有 `expense_view_all`，没有 `change_all`/`export_all`，可以查看全部 Expense，但只能修改自己的；其他会计、帐票、Visa、税务功能初期只开放给李。回填目标账号已确认。§13 删除“账号与会计 view_all 待确认”一项。
- `DATABASE.md` §11.2：重写为“已确认但尚未实现（P0 计划）”，并加醒目标注“以上属于 P0 计划，当前数据库尚未实现”。列出 ProtectedAccount（稳定 FK 关系，不按数据库 ID 固定李）、Employee.user、Expense owner/created_by/updated_by、AuditLog 四项计划结构，以及 system_admin、accounting_admin、business_admin、expense_viewer、staff 五个计划 Group 与初期成员。当前实际状态单独列出。
- `README.md`：加入 P0 方案（注明 AI 开始权限相关开发前必须先阅读）、第 2 版修订记录和本记录。
- `P0_ACCESS_CONTROL_DESIGN.md` 升级为第 2.1 版：
  - 全文状态标记：【已实现·现状】、【已确认·未实现】、【待批准数据操作】；
  - §2.2 localdev：发现时先只读报告，批准后只能停用，不自动删除；部署检查先 warn，确认后改为 enforce；
  - §3.3 ProtectedAccount 两阶段启用：阶段 A 不强制，注册李并验证；阶段 B 显式开启 `PROTECTED_ADMIN_ENFORCEMENT`。保护表为空时部署检查失败，不退回“允许所有 superuser”，服务器命令始终可用；
  - §4.4 策略白名单：逐项写明文件和理由，并列出不得进入白名单的范围；
  - §11 批次 2 拆成阶段 A 和阶段 B；§12 D4、D5、D12 修正。
- `AI_HANDOFF.md`、`DEVELOPMENT_PLAN.md`：同步第 2.1 版要点。

## 验证

- `git diff --check` 通过。
- 未修改应用代码，不声明后端测试或前端构建已执行。

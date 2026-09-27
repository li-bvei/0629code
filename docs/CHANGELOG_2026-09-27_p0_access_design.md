# 2026-09-27 P0 访问控制方案编写记录

## 范围

本批次只新增/修改 Markdown 文档，没有修改代码、数据库、nginx 或任何账号，没有创建 migration，没有提交 Git。编写方案时对本地库（`gyoseishoshi_erp@127.0.0.1`）执行了只读查询：User 的 is_staff/is_superuser、Group 与个别权限数量、Expense 条数与日期范围；不含密码哈希、Token 等认证秘密。

## 用户确认的账号映射

- User 1 李 ↔ Employee 1：唯一系统超级管理员 + 业务超级管理员；会计 `view_all`/`change_all`/`export_all`。
- User 2 焦 ↔ 待新建 Employee「焦」：业务管理员，后续降级（不再保留 superuser）。
- User 3 周 ↔ Employee 2：业务管理员，后续降级。
- Employee 3 NAING：无账号，不授权。
- User 4 localdev：本地开发账号，不关联、不授权；生产不得存在或必须停用；本次不修改。
- 降级焦、周必须在 User–Employee 关联、角色与数据范围、回归测试、李权限确认、回滚方案完成后单独执行。

## 新增

- `docs/P0_ACCESS_CONTROL_DESIGN.md`：现状盘点、账号与角色、User–Employee 设计、权限模型（Group/Permission，业务判定忽略 is_superuser）、各模块数据范围、Expense owner 与回填、AuditLog、`/media/` 受保护下载（X-Accel-Redirect）、账号降级安全顺序与回滚、测试矩阵、批次 0～9、未决问题 Q1～Q11。

## 同步修改

- `AI_HANDOFF.md`：§8 记录方案、账号映射、硬性顺序和新发现风险；§12 文档地图；§15.2 只读查询说明。
- `DEVELOPMENT_PLAN.md`：P0-A4/A6/A7 改为 🚧（方案草案已写，代码未开始）；§2.4 记录最终映射并指向方案；§2.10 指向方案 §8。
- `DATABASE.md`：§11.2 增加拟定 schema 摘要与当前账号现状（均标注未实现）。
- `README.md`：索引加入方案与本记录。

## 盘点中新发现的风险（已写入方案）

- 任一 superuser（焦、周、localdev）现在都可以降级或停用李；降级批次前需先加账号保护（方案 §9.4）。
- Expense 除 ViewSet 外还有 dashboard、余额计算、图表、`copy-expenses`（可引用任意 Expense ID）等全表访问路径。
- 余额计算依赖没有 owner 的 IncomeSource，隔离后普通用户的余额口径需确认（Q2）。
- 调试/诊断端点对任意登录用户开放（Q10）。
- 全部账号 `is_staff=True`，可进入 Django Admin 并绕过 API 权限。

## 验证

- `git diff --check` 通过。
- 未修改应用代码，不声明后端测试或前端构建已执行。

## 回滚

只涉及 Markdown，恢复上述文档即可。

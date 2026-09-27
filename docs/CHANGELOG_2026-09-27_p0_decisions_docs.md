# 2026-09-27 P0 方案依据确认与文档冲突修正

## 范围

本批次只修改 Markdown 文档，没有修改应用代码、nginx、migration 或数据，也没有提交 Git。唯一的数据库操作是对本地库（`gyoseishoshi_erp@127.0.0.1`）执行只读 User/Employee 清单查询，不含密码哈希、Token 等认证秘密。

## 用户确认的 P0 方案依据

1. 账号：只读清单已提供；用户确认具体账号前不得回填 Expense。
2. Customer/Company：具有案件业务权限的员工可搜索防重复登记所需的最小识别信息；详情、敏感字段、文件和修改按 `own`/`assigned`/`all` 控制。
3. 会计：`view_all`/`change_all`/`export_all` 初期仅授予用户确认的账号；superuser/系统管理员不自动获得；报销保持简单登记。
4. P0 第一批：只对 Expense 实施 `owner`/`created_by`/`updated_by` 和数据隔离；Income、VehicleUsage、AccountingProject 等只盘点。Case 按担当 Employee 控制，不用 owner；Document 继承关联 Case 权限，无 Case 时由上传人或明确授权控制。
5. `/media/` 公开访问提升为 P0 安全项（P0-A8），先写方案，不改 nginx。
6. Document 第一阶段不做完整版本管理（版本树、比较、恢复以后再评估）。
7. P2-C7 第一阶段保留 `Expense.category` 自由文本，不改外键、不批量清洗；规范分类只作建议，保留原始输入。

## 修正的文档冲突

- `DATABASE.md`：删除“不提前设计审计、权限”的旧前提；补充已实现的 `ReceptionIdempotencyRecord` 与 Timeline `actor`/`event_type`/`metadata`；记录 Document 现有字段、第一阶段范围和 `/media/` 风险；User–Employee、owner、AuditLog 标为“计划中，尚未实现”；从“未来扩展”中移出操作日志与模块权限。
- `CODING_RULES.md`：项目目录名改为 `0629code`；明确普通业务表不滥加审计字段，但统一 owner 字段和独立 AuditLog 属于已确认要求。
- `AI_HANDOFF.md`：§3 工作区改为“提交同步、存在未提交文档变更”；§8 补 P0-A8、P2-C7～C11、P3-D1～D5；删除 Checklist 模板审阅“完全暂缓”的旧表述（并入 P2-C9）；§14 标注为历史记录；文档地图加入本文件。
- `DEVELOPMENT_PLAN.md`：§0 更新到 2026-09-27；新增 P0-A8 与 §2.10 `/media/` 方案要求；§2.4 记录方案依据和 P0 小方案目录；P2-C7/C9 范围收窄。
- `PROJECT.md`：删除“客户不拥有后台账号”的重复表述；增加个人报销 owner 隔离原则。
- `DEVELOPMENT_REQUIREMENTS_2026-09-26.md`：说明“文档索引”仅指系统内部文件元数据；第一阶段不做完整版本管理；新增 §9.5 P0 第一批范围；P0 列表加入 `/media/` 项；§13 未决问题更新。
- `README.md`：索引加入本文件。

## 验证

- `git diff --check` 通过。
- 未修改应用代码，不重新声明后端测试或前端构建已执行。

## 回滚

只涉及 Markdown；如需回滚，恢复上述文档到修改前版本即可，无数据或部署影响。

# 文档入口

## AI 首先阅读

- [AI 交接总文档](AI_HANDOFF.md)：当前项目状态、实际代码能力、风险、优先级和验证结果。
- [系统架构约束](SYSTEM_ARCHITECTURE.md)：全项目唯一的架构约束文档，不可违反。文档优先级：AI_HANDOFF > SYSTEM_ARCHITECTURE > DEVELOPMENT_REQUIREMENTS > DEVELOPMENT_PLAN > DATABASE > CHANGELOG。
- [2026-09-26 业务扩展与权限开发要求](DEVELOPMENT_REQUIREMENTS_2026-09-26.md)：模块边界、会计/报销、现有系统文件管理、Visa、不动产、权限、审计和验收基准；已包含 2026-09-27 修正。读完交接文档后立即阅读。

## 产品与开发规则

- [项目定位与 MVP 范围](PROJECT.md)
- [数据库与实体关系](DATABASE.md)
- [编码与 AI 协作规则](CODING_RULES.md)
- [路线图](ROADMAP.md)

## 开发计划

- [当前开发计划（任务清单 + 内容修改计划）](DEVELOPMENT_PLAN.md)：接手任务前先看这份，按里面的顺序推进。
- [P0 访问控制设计方案](P0_ACCESS_CONTROL_DESIGN.md)：账号映射、BusinessAccessPolicy、Expense 隔离、ProtectedAccount 两阶段启用、AuditLog、受保护文件下载、批次与回滚、需批准的数据操作（第 2.1 版；2026-09-28 本地已实现，生产未部署）。**AI 开始任何权限、账号、审计、Expense 隔离或文件下载相关开发前，必须先完整阅读本方案。**

## 运维与变更记录

- [部署说明](DEPLOY.md)
- [2026-09-06 intake / workspace 变更记录](CHANGELOG_2026-09-06_intake_workspace.md)
- [2026-09-16 P0 追加修正变更记录](CHANGELOG_2026-09-16_p0_followup.md)
- [2026-09-26 需求与交接文档整理记录](CHANGELOG_2026-09-26_requirements.md)
- [2026-09-27 需求修正记录](CHANGELOG_2026-09-27_requirements_clarification.md)
- [2026-09-27 P0 方案依据确认与文档冲突修正](CHANGELOG_2026-09-27_p0_decisions_docs.md)
- [2026-09-27 P0 访问控制方案编写记录](CHANGELOG_2026-09-27_p0_access_design.md)
- [2026-09-27 P0 访问控制方案第 2 版修订记录](CHANGELOG_2026-09-27_p0_access_design_v2.md)
- [2026-09-27 P0 文档同步与受保护账号两阶段启用](CHANGELOG_2026-09-27_p0_docs_sync.md)
- [2026-09-28 P0 访问控制本地实现（最终）](CHANGELOG_2026-09-28_p0_access_control.md)
- [2026-09-28 P1 案件工作台本地实现](CHANGELOG_2026-09-28_p1_case_workspace.md)
- [2026-09-28 P2 文件管理分支](CHANGELOG_2026-09-28_p2_documents.md)
- [2026-09 项目审查报告](PROJECT_AUDIT_2026-09.md)

## 历史上下文

- [AI_CONTEXT.md](../AI_CONTEXT.md)：长期产品与实现背景，按需阅读。
- [AI_TASK.md](../AI_TASK.md)：历史任务记录；其中 Legacy 规格不代表当前需求。

文档发生冲突时，先以当前代码、migration、测试为实现事实，再以 AI_HANDOFF.md 的当前状态和产品文档决定下一步；不要从历史任务段落自动推导新功能。

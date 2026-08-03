# PROJECT

## 1. Project Overview

本项目是日本行政书士事务所内部使用的 ERP 系统。

系统用于管理客户、公司、案件、タスク、时间线、会计和帳票。整个系统以案件管理为核心，会计和帳票服务于事务所日常运营。

本项目面向个人长期维护，优先完成 MVP，不追求复杂平台化能力。

系统以案件生命周期（Case Lifecycle）为主线，帮助事务所管理日常业务。

## 2. Product Positioning

本系统是事务所内部业务管理工具。

它不是：

- SaaS 平台
- 复杂 OA
- 客户自助业务平台
- 通用财务软件

担当者使用现有 Employee 数据，客户不拥有后台账号。

客户不拥有后台账号。客户只能通过 Portal 在有限范围内参与自己的案件。

## 3. Technology Stack
Admin:

- Django Admin
- Django SimpleUI

Frontend:

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- Axios
- Element Plus

Backend:

- Django
- Django REST Framework

Database:

- MySQL

## 4. Core Concepts

Case 是系统核心。

核心概念：

- Customer: 自然人客户
- Company: 法人或相关公司
- Case: 案件
- Task / タスク: 案件内部工作步骤与备忘录
- Employee: 担当者
- Timeline: 案件时间线
- Accounting: 会计管理
- Voucher: 請求書・領収書等帳票

Case 为系统核心对象，其它业务对象根据业务需要与 Case 建立关联。

当前前端暂时隐藏材料上传、文件管理、费用管理和独立 Reminder 入口；后端已有模型和 API 不删除。

## 5. User Roles

内部用户：

- 管理员
- 事务所工作人员

外部用户：

- 客户 Portal 访问者

MVP 阶段不设计复杂权限体系，只区分内部后台访问和客户 Portal 访问。

## 6. Main Modules

当前主要模块：

- 客户管理
- 公司管理
- 案件管理
- タスク管理
- 担当者管理
- 时间线管理
- 案件・担当設定管理
- 会計管理
- 帳票管理
- 客户 Portal（未完成）

模块之间以案件为主线组织，不做独立的 CRM 流程。

帳票管理当前包含:

- 請求書・領収書
- 返签 visa 表
- 税务证明更新用
- 清風合格通知書（待开发 / 暂停处理）

会計管理当前包含:

- 会計ダッシュボード
- 支出記録
- 支出カテゴリ
- 収入元
- 車両使用記録
- プロジェクト収支表

## 7. Client Portal

客户通过「案件号 + 生日」进入 Portal。
Portal 为独立页面，不属于后台系统。

客户只能：

- 查看案件进度
- 上传资料
- 填写表单
- 下载文件

客户不能：

- 注册账号
- 登录后台
- 查看其他案件
- 修改内部数据

## 8. Development Principles

开发原则：

- 不过度设计
- 保持架构简单
- 优先考虑可维护性
- 每次只完成一个小功能
- 不猜测需求
- 不主动增加未要求的功能
- 所有设计以 MVP 为目标
- 文档优先，代码实现遵循 docs 目录内容。

## 9. MVP Scope

MVP 只实现支撑案件管理闭环的最小功能：

- 内部用户可以管理客户、公司和案件
- 每个案件可以记录タスク和时间线
- 案件・担当設定管理集中维护案件種別、申請区分、案件進捗、Checklistテンプレート、取得場所、準備者区分和担当者
- 請求書・領収書可以生成 PDF
- 会计管理支持支出、收入、车辆使用和项目收支基础记录
- 客户 Portal 仍待后续完成
- 系统具备基础 API 和前端页面结构

MVP 不追求自动化、复杂权限、统计报表或外部系统集成。

## 10. Out of Scope

以下内容不属于 MVP：

- 多租户 SaaS
- 客户账号体系
- 在线支付
- 电子签名
- 邮件自动化
- LINE 或外部消息集成
- 高级审批流
- 复杂权限矩阵
- 数据分析看板
- 移动 App

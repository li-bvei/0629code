# DATABASE

## 1. Database Overview

数据库使用 MySQL。

数据模型以 Case 为中心设计。数据库以 Case 为核心设计，业务数据优先围绕 Case 组织。

MVP 阶段保持表结构清晰，不提前设计复杂审计、权限或多租户结构。

## 2. Naming Rules

命名规则：

- 表名使用小写蛇形命名
- 字段名使用小写蛇形命名
- 主键统一使用 `id`
- 外键使用 `{model}_id`
- 时间字段使用 `_at` 结尾
- 布尔字段使用 `is_` 或 `has_` 开头

示例：

- `customers`
- `companies`
- `cases`
- `case_tasks`
- `case_documents`

## 3. Common Fields

核心业务表默认包含：

- `id`
- `created_at`
- `updated_at`

需要软删除时再增加：

- `deleted_at`

MVP 阶段不默认给所有表添加软删除。只有明确需要恢复或隐藏历史数据的表才使用。

## 4. Core Entities

核心实体：

- `customers`: 客户
- `companies`: 公司
- `cases`: 案件
`cases` 是主表之一，应包含案件号、案件类型、状态、客户、公司、受理日期等基础字段。

- `employees`：后台用户

Employee 后面一定会出现，现在加进去即可。



客户和公司可以独立存在，但业务操作应尽量从案件进入。

## 5. Relationships

基础关系：

- 一个 Customer 可以关联多个 Case
- 一个 Company 可以关联多个 Case
- 一个 Case 可以关联一个 Customer
- 一个 Case 可以关联一个 Company
- 一个 Case 可以拥有多个 Task
- 一个 Case 可以拥有多个 Reminder
- 一个 Case 可以拥有多个 Timeline
- 一个 Case 可以拥有多个 Document
- 一个 Employee 可以负责多个 Case

以后负责人、创建人都会用到。

MVP 阶段暂不设计复杂多对多参与人结构。如后续案件需要多个客户或多个公司，再单独扩展。

## 6. Workflow Tables

工作流相关表：

- `case_tasks`: 案件任务
- `case_reminders`: 案件提醒
- `case_timelines`: 案件时间线

`case_tasks` 用于记录内部待办。

`case_reminders` 用于记录重要日期和提醒事项。

`case_timelines` 用于记录案件进展，既可给内部查看，也可选择性展示给客户 Portal。Timeline 为系统操作记录，不允许修改，只允许追加。

## 7. Resource Tables

资源相关表：

- `case_documents`: 案件文件
- `forms`: 客户填写的表单记录

文件应关联 Case，并记录文件来源：

- 内部上传
- 客户上传
- 系统生成

MVP 阶段只保存文件元数据和存储路径，不设计复杂版本管理。

## 8. Portal

Portal 访问基于：

- 案件号
- 客户生日

Portal 不使用客户账号。

Portal 相关数据应支持：

- 判断案件是否允许 Portal 访问
- 判断时间线是否对客户可见
- 判断文件是否允许客户下载
- 记录客户上传的资料

生日属于敏感信息，后端接口不得返回不必要的生日字段。

## 9. Future Extensions

未来可按需要扩展：

- 多客户或多公司参与同一案件
- 文件版本管理
- 操作日志
- 细粒度权限
- 通知发送记录
- 外部系统同步记录

这些能力不进入 MVP，除非有明确业务需求。

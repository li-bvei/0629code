# CODING_RULES


## 1. General Principles

开发原则：

- 简单优先
- 只做当前明确需要的功能
- 不为了未来可能性提前抽象
- 代码可读性优先于技巧
- 每次改动保持小范围
- 文档与代码不一致时，先更新或确认文档

`docs` 是项目设计依据。开发前应先确认相关文档。

## 2. Project Structure

项目根目录规划：

```text
0629myproject/
├── frontend/
├── backend/
└── docs/
```

目录职责：

- `frontend`: Vue 3 前端项目
- `backend`: Django 后端项目
- `docs`: 项目文档

不要在根目录随意放置业务代码。

## 3. Frontend Rules

前端规则：

- 使用 Vue 3 Composition API
- 使用 TypeScript
- 使用 Pinia 管理必要的全局状态
- 使用 Vue Router 管理页面路由
- 使用 Axios 访问后端 API
- 使用 Element Plus 作为基础 UI 组件库

页面和组件应保持简单。组件只有在重复使用或明显变复杂时才拆分。

## 4. Backend Rules

后端规则：

- 使用 Django
- 使用 Django REST Framework
- 业务逻辑不要直接写在 View 中。
- API 返回结构保持一致
- 不提前引入复杂分层

Django app 应按业务模块划分，但 MVP 阶段避免拆得过细。

## 5. Database Rules

数据库规则：

- 使用 MySQL
- 表结构围绕 Case 设计
- 字段命名保持统一
- 外键关系清晰
- 不提前设计多租户
- 不默认加入复杂审计字段

数据库变更必须通过 migration 管理。

## 6. API Rules

API 规则：

- 内部后台 API 与 Portal API 分开
- Portal API 只能返回客户允许查看的数据
- 不返回不必要的敏感字段
- 列表接口保持分页能力
- 错误信息保持简洁清晰
- 所有时间统一使用 UTC 存储，前端负责展示

API 命名应围绕资源，不围绕页面。

## 7. Naming Convention

命名规则：

- Python 使用 snake_case
- TypeScript 变量和函数使用 camelCase
- Vue 组件使用 PascalCase
- 数据库表和字段使用 snake_case
- API 路径使用 kebab-case 并在项目中保持一致

业务命名应贴近领域概念，如 `case`, `customer`, `company`, `document`。

## 8. Git Rules

Git 规则：

- 每次提交只包含一个清晰主题
- 不混入无关格式化
- 不提交临时文件
- 不提交本地密钥或数据库文件
- 提交前确认项目能正常运行

提交信息保持简洁，说明做了什么。

## 9. AI Development Rules

AI 协作规则：

- 不根据历史聊天覆盖最新文档
- 如果聊天内容与文档冲突，以文档为准
- 如果文档之间冲突，先提出问题
- 不主动增加未要求的功能
- 不初始化未被要求的项目
- 不创建未被要求的配置文件
- 每次只完成当前明确任务
- 修改已有代码时，优先保持原有风格，不随意重构整个模块。
- 完成任务后，简要说明修改内容，并等待下一步指令

所有实现都应服务于个人长期维护和 MVP。

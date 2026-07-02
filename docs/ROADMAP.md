# ROADMAP


## 1. MVP Milestones

MVP 目标是完成一个可用于事务所内部案件管理的最小系统。

里程碑：

- 项目基础文档
- 前后端项目初始化
- 后端基础 API
- 前端基础页面
- 案件管理闭环
- 客户 Portal MVP
- 文件上传与下载

每个阶段只完成必要功能，不提前加入复杂能力。

## 2. Phase 1: Project Foundation

目标：确定项目方向和维护规则。

内容：

- 完成项目文档
- 确认目录结构
- 确认数据库设计原则
- 确认编码规则
- 确认 MVP 范围

完成标准：

- `docs` 中的核心文档可作为后续开发依据

## 3. Phase 2: Project Initialization

目标：建立可运行的前后端基础项目。

内容：

- 初始化 Vue 3 + TypeScript + Vite 前端
- 初始化 Django + DRF 后端
- 集成 Django SimpleUI
- 配置 MySQL 连接
- 建立基础目录结构
- 建立基础路由和 API 结构
- 配置 Django Admin 作为第一阶段后台管理

完成标准：

- 前端可以启动
- 后端可以启动
- Django Admin + SimpleUI 可以正常访问
- MySQL 正常连接
- 前后端目录结构清晰
- 不包含业务代码

## 3.1 Current MVP Progress

当前已完成：

- 前端后台 Layout 与主要菜单
- Dashboard 真实数据展示
- Customer 列表、搜索、详情、CRUD
- FamilyMember 在 Customer Detail 中 CRUD
- Company CRUD
- Case 列表、详情、CRUD
- Case 自动案件号生成
- Case Detail 中 Task CRUD
- Case Detail 中 Reminder CRUD
- Case Detail 中 Timeline 追加
- Case Detail 中 Document 元数据 CRUD
- Django Admin / SimpleUI 基础管理
- seed_demo_data 开发测试数据命令

当前未完成：

- 客户 Portal
- 真实文件上传和下载
- 申請書 PDF / Excel 生成
- 复杂权限系统
- 通知发送

## 3.2 Local Development

后端启动：

```bash
cd backend
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo_data
.venv/bin/python manage.py runserver
```

前端启动：

```bash
cd frontend
npm install
npm run dev
```

常用检查：

```bash
cd backend
.venv/bin/python manage.py check
.venv/bin/python manage.py showmigrations

cd frontend
npm run build
```

本地访问：

- 前端后台：`http://127.0.0.1:5173/dashboard`
- Django Admin：`http://127.0.0.1:8000/admin/`
- API：`http://127.0.0.1:8000/api/`


## 4. Phase 3: Core Case Management

目标：完成内部案件管理的核心闭环。

内容：

- 客户基础管理
- 公司基础管理
- 案件基础管理
- 案件状态管理
- 案件关联客户和公司
- Employee 登录

完成标准：

- 内部用户可以创建、查看、编辑案件
- 案件可以关联客户和公司

## 5. Phase 4: Portal MVP

目标：让客户可以通过最小方式查看自己的案件。

内容：

- 通过案件号和生日访问 Portal
- 查看案件基础进度
- 查看对客户可见的时间线
- 填写表单
- 上传资料

完成标准：

- 客户不需要账号即可访问自己的案件信息
- 客户不能访问其他案件或内部后台

## 6. Phase 5: Document Management

目标：支持案件相关文件管理。

内容：

- 文件分类
- 文件下载
- 文件归档
- 文件权限

完成标准：

- 文件能关联到案件
- Portal 只展示允许客户访问的文件

## 7. Phase 6: Optimization

目标：在 MVP 可用后做必要优化。

内容：

- 修复使用中发现的问题
- 改善页面易用性
- 补充必要测试
- 优化常用查询
- 补全文档

完成标准：

- 系统稳定支持日常案件管理

## 8. Out of Scope

MVP 之外的内容：

- 多租户
- 客户账号体系
- 在线支付
- 自动通知
- 复杂审批流
- 高级报表
- 外部服务集成
- 移动 App

这些内容仅在 MVP 稳定后，根据明确需求再评估。

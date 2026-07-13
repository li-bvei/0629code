# AI Task

## Current Task

案件业务模块前端显示与负责人管理入口修正。

费用功能、材料上传、文件管理、独立 Reminder 功能暂时不做；不要删除后端已有模型和 API，只在前端暂时隐藏不需要的入口。

本阶段要求:

- 前端统一使用日文「タスク」，不要显示中文「工作任务」。
- 案件业务菜单增加「担当者管理」入口。
- 担当者复用现有 `Employee`。
- Task 新增 / 编辑时可以选择有效担当者，允许为空。

「清風合格通知書 / PDF 添加文字」功能状态保持:

```text
待开发 / 暂停处理
```

后续不要继续围绕清風合格通知書开发，除非用户重新明确要求。

## 1. 当前目标

案件模块主要保留:

- 案件一览
- 案件详情
- 客户
- 公司
- タスク
- 担当者管理
- 进度记录

案件详情重点展示:

- 案件基本信息
- 当前状态
- 当前阶段 / 进度
- 次のタスク
- タスク一覧
- 进度记录

暂时隐藏:

- 材料上传
- 文件管理
- 费用管理
- 独立 Reminder 功能
- 时间提醒、通知、邮件、日历、定时任务

## 2. 菜单

案件業務菜单:

- 案件一覧
- 顧客管理
- 会社管理
- 担当者管理
- タスク一覧

担当者管理:

- 页面: `frontend/src/pages/EmployeesPage.vue`
- 路由: `/employees`
- 使用现有 `/api/employees/`

## 3. Task 定位

Task / タスク 是案件内的工作步骤备忘录。

示例:

1. 开具税务证明
2. 开具年金证明
3. 整理申请资料
4. 客户确认
5. 提交入管局
6. 等待审查结果

每个 Task 记录:

- 做什么
- 谁负责
- 计划什么时候完成
- 当前状态
- 实际完成日期
- 备注
- 在案件中的步骤顺序

不做:

- `remind_at`
- 自动通知
- 邮件提醒
- 重复提醒
- 日历同步
- 后台定时任务

前端文案:

- タスク
- タスク追加
- タスク一覧
- 次のタスク

不要再显示中文「工作任务」。

## 4. Task 字段

现有 `Task` model 已复用，并补充字段:

- `case`
- `title`
- `description`
- `responsible_employee`
- `status`
- `sort_order`
- `due_date`
- `completed_at`
- `created_at`
- `updated_at`

说明:

- `due_date` 作为旧字段保留，前端和 API 别名显示为 `planned_completion_date`。
- 新增字段已生成并应用 migration: `tasks.0002_alter_task_options_task_completed_at_and_more`。
- 旧状态会迁移:
  - `todo` -> `pending`
  - `done` -> `completed`
  - `未対応` -> `pending`
  - `対応中` -> `in_progress`
  - `完了` -> `completed`
  - `保留` -> `paused`

## 5. Task 状态

前端显示:

- `pending`: 未开始
- `in_progress`: 进行中
- `completed`: 已完成
- `paused`: 暂缓
- `cancelled`: 取消

规则:

- 状态改为 `completed` 时，如果 `completed_at` 为空，自动写入当前日期。
- 状态从 `completed` 改回其他状态时，可以清空 `completed_at`。
- `planned_completion_date` 只是计划完成日期，不触发提醒。
- 没有填写日期也可以保存。

## 6. 案件详情 Task

案件详情显示「タスク一覧」。

列表字段:

- 步骤
- タスク名
- 担当者
- ステータス
- 予定完了日
- 完了日
- 備考
- 操作

操作:

- タスク追加
- 編集
- 完了
- 保留
- 削除
- 上移
- 下移

要求:

- 一个案件可以添加任意数量 Task。
- 按 `sort_order` 排序。
- 已完成 / 取消任务显示删除线并排在未完成任务后。
- 可以快速点击「完成」。
- 新增 / 编辑使用 Dialog，不跳转单独页面。

## 7. 担当者管理

担当者就是现有 `Employee`。

功能:

- 担当者一覧
- 新規追加
- 編集
- 有効 / 無効切换
- 検索

显示:

- 氏名
- メール
- 電話
- 有効状態
- 更新日時
- 操作

Task 新增 / 编辑:

- 字段名称为「担当者」。
- 数据来源为有效 `Employee`。
- 下拉显示 `Employee.name`。
- 允许为空，显示「未指定」。
- 已停用负责人不出现在新建 Task 的可选列表。
- 已有 Task 仍显示原负责人姓名。
- 提供「担当者管理」快捷入口跳转 `/employees`。

## 8. 案件列表

案件列表增加:

- 任务进度: `已完成数量 / 总数量`
- 次のタスク: 第一条未完成、未取消 Task 的标题和负责人

后端 `CaseSerializer` 返回:

- `task_total_count`
- `task_completed_count`
- `next_task_title`
- `next_task_responsible_employee_name`

## 9. 验证命令

后端:

```bash
cd backend
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
```

前端:

```bash
cd frontend
npm run build
```

# 2026-09-30 UI：共享表单与操作区布局（分支 `codex/ui-form-layout`）

只改前端布局。未改 API、权限判定、数据库、migration、业务状态流转。

## 共享组件（`frontend/src/components/layout/`）

| 组件 | 用途 |
|---|---|
| `RecordFormLayout` | 本文 `minmax(0, 1fr)` ＋ 右列（默认 300px，`auto` 列）。1100px 未满右列移到本文下方并取消 sticky |
| `FormSection` | 见出し・说明＋1〜3 列输入网格（640px 未满 1 列，`form-grid-full` 占整行） |
| `FormActions` | 保存・取消按钮列。640px 未满全幅纵向，最后写的按钮（保存）在最上。Dialog/Drawer 放 `#footer` |
| `ResponsiveActionBar` | 详细画面操作列（数据驱动）。640px 未满只保留 `collapse: 'never'` 的按钮，其余进「その他」菜单。切换只靠 CSS |
| `TableRowActions` | 表格行操作：前 N 个文字按钮，其余进「その他」；危险操作不做按钮、放菜单最后 |

规则集中在 `frontend/src/styles/layout.css`：页面见出し换行、Dialog 最大宽高（只滚动本文，底部操作栏常驻）、Drawer 不超过屏宽、手机宽度顶部栏两行化。

## 应用的页面

- 支出：新规・编辑页用 `FormActions`；一览的快速添加・批量添加对话框的按钮移到底部操作栏（批量添加的「预览／确认追加」原来夹在本文中间）。
- Visa 导入 Drawer：各步骤的进退按钮从本文移到底部操作栏（原来在纵向 flex 中被拉成整行宽且错位）；作成方式的单选改为纵向、可换行。
- 见积书・契约书对话框：底部 `FormActions`；契约期间两个日期可换行；手机宽度下明细表不再把表单撑到 822px（网格改为 `minmax(0, 1fr)`）。
- 请求书・领收书：明细行去掉内联 `grid-template-columns`（它覆盖了窄屏的 1 列规则）。
- 不动产详情：字段列表 `minmax(0, 1fr)`・长文换行，手机宽度 1 列；卡片网格最小宽度不超过容器。
- 案件详情：页头操作与 Action Bar 改为 `ResponsiveActionBar`；右列改为 `RecordFormLayout`（原来 760px 才切换，1024px 时本文被挤到约 400px）；卡片标题按钮可换行（「案件進捗・必要資料」在 390px 时超出卡片）；概要卡片手机宽度改为上下排列。
- 顾客・公司详情：页头操作 `ResponsiveActionBar`，右列 `RecordFormLayout`（1100px 未满在下方 2 列）。
- 书类管理：操作列 220px→150px，`TableRowActions`（差し替え＋その他）；筛选下拉手机宽度全幅。
- 设置：共通规则覆盖（Dialog・页头）。
- 会计工具栏・筛选按钮换行时不再残留左边距。

## 验证

- 前端单测 17 项通过（新增 `tests/layoutActions.test.ts` 5 项），`vue-tsc -b`＋`vite build` 通过。
- 平台预览（backend 127.0.0.1:8041・`gyoseishoshi_erp_platform_preview`，UI 分支前端 `[::1]:5221`，system_admin 测试账号的现有会话）在 1440・1280・1024・768・390 五种宽度检查 17 个页面和 12 个 Dialog/Drawer：页面横向溢出 0、视口外元素 0、按钮与输入框重叠 0、按钮文字截断 0、Dialog/Drawer 底部操作栏全部在视口内；右列 1280 在右侧（sticky），1024 在下方。发现并修复的问题见上（390px 卡片标题按钮、390px 见积・契约对话框溢出）。
- 截图：390px 的案件详情（页头・Action Bar・「その他」菜单）已目视确认；之后浏览器面板被隐藏无法截图，其余宽度以 DOM 测量为准（测量时面板隐藏会使 Drawer 进入动画停在初始帧，已排除该干扰）。控制台无错误。

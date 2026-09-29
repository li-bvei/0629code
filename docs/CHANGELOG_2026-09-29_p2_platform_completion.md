# 2026-09-29 P2 平台能力收尾（codex/p2-platform-completion）

基于 `codex/p3-real-estate` `1a4c5e3`。未推送、未部署、未连接生产；未开始正式 LIST.xlsx 导入；未修改 P2/P3 预览库中的任何台账。

## 切片 1：事务所「事業年度末月」设置（migration `office/0001_office_settings`、`real_estate/0003_ledger_fiscal_month_snapshot`，只加结构）

- 既有系统没有可复用的事务所级设置模型，新增最小单例 `OfficeSettings`（表 `office_settings`，固定 pk=1，只有 `fiscal_year_end_month`、`updated_by`、`updated_at` 三列）。不是通用 key-value 配置表。
- 读取顺序：数据库中的设置 → 环境变量 `OFFICE_FISCAL_YEAR_END_MONTH`（兼容旧的 `REAL_ESTATE_FISCAL_YEAR_END_MONTH`）→ 默认 3 月。migration 不插入行；第一次保存时才创建。
- API `GET/PATCH /api/office-settings/`：参照为全部业务利用者；修改需要新权限 `office.manage_office_settings`（只加入 system_admin 角色，即李）。取值 1～12 校验；修改写 AuditLog（`module=office`、`fiscal_year_end_month_changed`，记录旧值→新值和旧来源）。
- 设置页新增「事務所設定：事業年度末月」卡片：说明适用范围和不追溯规则、1～12 选择、变更前确认；无权限者只读。
- 不动产台账：`LegalLedger.fiscal_year_end_month` 保存计算所用决算月的快照。
  - 创建台账时保存当时的事务所设置；未关闭的台账之后一直用自己的快照计算事业年度和保存期限。
  - 年度关闭时确定快照和保存期限（只有没有快照的旧行才用当时的设置补上），关闭后的台账冻结：以后修改系统决算月、甚至更正取引日，都不改变其决算月、事业年度和保存期限；重复关闭不变。
  - 租赁仍默认保存 5 年；sale 仍只保留字段。
  - 工作台显示「事業年度：2027（3 月決算・快照）」。

## 切片 2：Case 归档完善（migration `cases/0020_case_archive_metadata`，只加结构）

- 新增列：`archived_by`、`archive_reason`、`restored_at`、`restored_by`（`archived_at` 沿用既有列）。既有案件不回填。
- `POST /api/cases/{id}/archive/`：理由必填；进度未到完成/许可/不许可/取下げ时沿用既有「需要确认」规则（`requires_force`→确认后 `force`）；写 Timeline（`event_type=case_archived`，标题沿用「登録状態変更」）和 AuditLog（`case_archived`，含理由）。
- `POST /api/cases/{id}/restore/`：登记状态回到「有効」，清空 `archived_*` 并记录 `restored_at/by`；旧的归档日期・理由写入 Timeline（`case_restored`）和 AuditLog（`case_restored`，`extra.previous_archive`）。复原后按原有权限和进度正常工作。
- 既有 `change-registration-status` 进入/离开「アーカイブ」时同样记录实行者・理由・复原信息，并新增 AuditLog `case_registration_status_changed`。
- 归档中的案件：可以查看；基本信息修改、进度变更、Next Action 等变更类 action 返回 400（提示先复原）；Checklist・Task・Reminder・Timeline 手动记录・Document 等子资源的新增/修改由 BusinessAccessPolicy 拒绝（403）。只有 archive/restore/registration-status 允许执行。
- 不删除任何案件、子资源或历史；权限不变（担当外不可见、业务管理员不可改他人担当案件）。
- 前端：案件详情头部「アーカイブ」「復元」按钮、归档说明横幅；归档中隐藏编辑类按钮。

## 切片 3：权限感知的全局搜索（无 migration）

- `GET /api/search/?q=`（2 字以上，最多 100 字；每类最多 8 条）。资源 `global_search` 本身对业务利用者开放，各类结果仍分别经过 BusinessAccessPolicy（`policy.queryset`）和模块权限：
  - Case：案件番号・顾客名/カナ・公司名；只返回可见范围内的案件（番号、顾客名、进度、是否归档）。
  - Customer / Company：只按名称・カナ匹配；只返回 id・名称・カナ・表现级别；范围外（minimal）标记为不可打开、不给链接。
  - Document：标题・原文件名；返回标题・案件番号・分类・是否归档和案件链接，不返回保存路径、URL 或文件名以外的元数据。
  - RealEstateTransaction：番号・当事人・物件・房间；按不动产本人担当/全件规则。
- 不按 My Number、证件号码、住所、电话、邮件、金额搜索，也不返回这些字段或会计金额（测试确认）。
- 审计：结果含顾客/公司时记录 `search.global_search_personal_results`（各类件数、minimal 件数、检索词长度），**不记录检索词本身**；普通搜索不记录。
- 前端：顶栏全局搜索框，按类别分组显示，可打开的结果点击跳转；范围外结果显示「範囲外（最小識別情報のみ）」且不可点击。

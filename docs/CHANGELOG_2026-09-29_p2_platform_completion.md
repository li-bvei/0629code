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

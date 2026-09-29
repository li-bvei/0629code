# 2026-09-29 P3 不动产（codex/p3-real-estate）

基于 `codex/p2-polish`。独立 app `apps/real_estate`，不并入 Case 或 Accounting。未推送、未部署、未连接生产，未执行真实 Excel 导入。

## 切片 1：后端核心（migration `real_estate/0001_initial`，只加结构）

- **RealEstateTransaction**：编号 `RE-YYYYMM-NNNN`、交易类型（rental 默认／sale 仅保留字段）、阶段（問い合わせ→内見→申込→審査→契約→完了／キャンセル）、轻量当事人名＋可选 Customer 参照、物件（名称・房间・所在地・种类・面积）、管理公司名＋可选 Company 参照、担当（Employee）、取引日、金额（赁料/价格、仲介手数料、广告料、手续费），以及 LIST.xlsx 三个相近请求金额**分别**作为原始来源金额保存；支払/振込状态、来源文件/工作表/行号/原值列（本版只供 dry-run 设计，不写入）。
- 首屏只需：当事人、物件名、房间号、管理公司、担当（默认本人）、交易类型（默认租赁）、阶段；一览返回「要補充」项目（取引日・担当・管理会社・支払状態），不推测填充。
- **TransactionParty**：贷主/借主/卖主/买主/代理人/媒介业者/共同宅建业者，可参照 Customer/Company（受控关联规则）。
- **LegalLedger**（每笔一份）：取引态样、类型、所在地・名称・房间・面积・建物概要、赁料/价格、报酬、广告费、手续费、特约、取引日、事业年度、年度关闭、保存年数（租赁默认 5 年；sale 本版不启用 10 年流程）、保存期限、legal hold、锁定与锁定快照、版本。
  - 锁定后直接修改被拒绝；「更正」需理由，版本+1，写 `LegalLedgerCorrection` 和 AuditLog。锁定后当事人不可增删。
  - 年度关闭：锁定该年度全部台账并记录关闭时间；到期只标记「到期复核」，**不自动删除**；台账无删除 API，有台账的交易也不能删除。
  - 事业年度按设置 `REAL_ESTATE_FISCAL_YEAR_END_MONTH`（默认 3 月）计算，上线前需确认公司实际决算月。
  - 导出 CSV（用于显示/打印）写审计。
- **RealEstateFile**：复用 Document 的上传检查（扩展名/文件头/危险前缀/大小）和受保护下载（新增 `subdir` 参数，保存在 `real_estate_files/`，UUID 保存名）；也可只参照既有案件 Document，不复制。
- **RealEstateAccountingLink**：引用会计的收入或请求书/领收书，不复制会计数据；创建需要对应会计权限，摘要只对有会计权限者显示。
- **InternalProfitDistribution**：分配对象、固定金额或比例、基准额、自动计算、草稿／結算済み、备注；结算后只能改备注，退回草稿需理由；不进入法定台账，不读取强哥表。
- **权限**（BusinessAccessPolicy，`access_rules.py`）：`real_estate.use_real_estate`（本人担当，staff/business_admin）、`real_estate_view_all`（business_admin）、`real_estate_change_all`・`manage_legal_ledger`（system_admin）、`manage_profit_distribution`（accounting_admin）。结果：一般用户只看本人担当；业务管理员看全部、只改本人担当；李看改全部并管理台账和利润分配。
- **审计**（module=`real_estate`）：交易/当事人/台账的创建更新、锁定、更正、年度关闭、legal hold、导出、拒绝的台账管理操作、文件上传与下载、会计引用、利润分配的查看（列表和详情）/创建/更新/结算/退回/删除。交易的「审计记录」接口只对有利润分配权限者包含利润分配记录。

## 验证（切片 1）

- 后端 `python manage.py test`：271 项全部通过（新增 11 项）；`makemigrations --check`：无差异。

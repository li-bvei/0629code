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

## 切片 2：LIST.xlsx / CSV dry-run（migration `real_estate/0002_import_runs`，只加结构）

- `apps/real_estate/list_import.py`、`POST /api/real-estate/imports/dry-run/`、`GET imports/`、`GET imports/{id}/`、`GET imports/{id}/error-report/`。**没有正式导入接口**，dry-run 不创建任何交易。
- XLSX 只读取 `工作表1`；`强哥` 不打开、不读取，也不出现在报告或工作表列表中（测试用哨兵字符串确认）。`工作表2` 也不读取。
- 每行保留来源文件、工作表、行号和原始值；`-`、空、0 分别规范化并按列统计；`-` 视为空但保留原值和注记，0 与空区分。
- `向SUNRISE請求書金額`・`向客人請求金額`・`SUNRISE請求書金額` 分别保存为原始来源金额，不合并。
- 没有年份的日期、无法解析的金额、未知状态值记为错误，不推测；日期・担当者・管理会社・支払い状態 缺失标为「要补充」；種類为空时注记“正式登记时按赁贷处理（待确认）”。
- 顾客、管理公司、物件（既有交易）、担当者只给候选（在操作者可见范围内），不自动关联。
- 重复检测：文件内（同番号，或同客名+物件+房间+日期）与已登记交易（同客名+物件+房间）。
- 同一文件可重复执行，结果一致；报告保存在执行履历中，并列出同一 SHA-256 的以前执行；错误报告 CSV；执行和下载错误报告写审计。
- 权限：只有 `real_estate_change_all`（李）可用；设置 `REAL_ESTATE_IMPORT_DRY_RUN_ENABLED` 默认等于 `DEBUG`，生产环境即使有权限也返回 403。
- 真实 `LIST.xlsx` 只读取了表头和列的值类型（用于设计映射），未执行导入，也未写入任何库。

## 验证（切片 2）

- `apps.real_estate` 16 项、策略防漏测试通过（全量结果见最后）。

## 切片 3：前端

- 菜单「不動産」：取引一覧（有 `use_real_estate`/`view_all`/`change_all` 时显示）、LIST 取込（dry-run，仅 `change_all`）。
- `/real-estate`：总览列表；筛选：担当・阶段・管理公司・付款状态・交易类型・要补充・关键词；列表显示要补充项和台账状态。新规对话框只有 7 项（当事人・物件名・房间号・管理公司・担当〔默认本人〕・交易类型〔默认赁贷〕・阶段），顾客主档参照可选且不自动关联。
- `/real-estate/:id`：单笔工作台，分区为 物件・金额（三个来源金额分别显示）、当事者、法定台帳（创建・编辑・锁定・更正〔理由必填・版本〕・legal hold・打印・更正履历・到期复核标记）、ファイル（受保护上传/下载）、会計参照（内容只对有会计权限者显示）、内部利益配分（仅权限者可见，自动计算、结算/退回草稿需理由）、監査記録。担当外记录只读并提示；sale 显示“仅记录”提示。
- `/real-estate/import`：dry-run 上传、汇总、列统计（空/-/0/值）、逐行原值・三个金额分别显示・错误・要补充・注记・重复・候选，错误报告 CSV，执行履历。

## 本地预览

- 新建本地预览库 `gyoseishoshi_erp_p3_preview`（从 `gyoseishoshi_erp_p2_preview` 克隆；P2 库未修改），执行 `real_estate.0001/0002` 与 `setup_access_roles --apply --yes`。
- 后端 `127.0.0.1:8031`、前端 `http://localhost:5201`（使用 localhost 以免与 127.0.0.1 上的 P2 预览共享登录 cookie）。
- 浏览器确认：李登录、菜单、列表、新规（创建 RE-202609-0001）、工作台各区、创建台账、dry-run 页面显示。dry-run 的文件上传未在浏览器中操作（后端测试覆盖）。真实 `LIST.xlsx` 只读取了表头和列类型，未导入任何库。

## 验证（最终）

- 后端 `python manage.py test`：276 项全部通过；`makemigrations --check`：无差异。
- 前端 `vue-tsc`、`npm run build`、`npm run test:unit`（10 项）：通过。

## 待确认

- 公司实际决算月（`REAL_ESTATE_FISCAL_YEAR_END_MONTH`，默认 3 月）。
- 三个相近请求金额的业务含义；正式迁移方案（dry-run 之后的人工确认、导入、对账、回滚）。
- 上线前以届时有效的国土交通省资料复核台账字段与保存期限。

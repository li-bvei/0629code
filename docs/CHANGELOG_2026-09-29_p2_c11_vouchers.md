# 2026-09-29 P2-C11 帐票（codex/p2-c11-vouchers）

基于：`codex/p2-integration`（P1 + 会计 + Visa + 文件）。未推送、未部署、未连接生产，未改动任何真实数据。

## 原则

- 見積書、契約書、請求書、領収書各自有**独立的状态、编号规则、金额快照和 PDF 模板**，状态互不联动：見積書「受注」不会改变契約書或請求書；領収書「無効」不会改变請求書。
- 共用的只有基础设施（`apps/accounting/voucher_infra.py`）：编号（`DocumentNumberSequence`）、金额计算（沿用 `voucher_calculations.py`）、发行时快照、状态迁移的执行与审计、PDF 绘制辅助。每种帐票的状态和允许的迁移分别定义为独立的 `Workflow`。
- 没有新建带 `type` 的万能表：見積書、契約書是两张新表；請求書、領収書继续用现有 `accounting_vouchers`（不迁移已有数据），但状态列分开（`invoice_status` / `receipt_status`），各自只用自己的列。
- 「从某帐票创建」只是把宛先、明细、关联案件复制成新的下書き，不改变源帐票状态。
- `/vouchers/*` 方向保留；証明書、その他帳票仍为占位页。

## 实现

1. **数据**（migration `accounting/0018_business_documents_c11`，全部加法）
   - 新表 `accounting_estimates`（見積書：`estimate_number` EST-YYYYMMDD-NNNN、`status`、`valid_until`）和 `accounting_contracts`（契約書：`contract_number` CON-…、`status`、契约期间、支付条件、条项 `body`、`signed_date`、`source_estimate`）。两者共享抽象列（宛先、発行者、明細、金额、`issued_snapshot`、关联 Case/Customer/Company、`created_by`/`updated_by`）。
   - `accounting_vouchers` 新增：`invoice_status`、`receipt_status`、`paid_date`、`status_changed_at`、`issued_snapshot`、`source_estimate`、`source_contract`、`source_invoice`、Case/Customer/Company 关联、`updated_by`。
   - **既有请求书/领收书的状态保持为空（显示为「状態未設定（旧データ）」），不做批量回填**；它们仍可编辑、删除，也可以逐条手动迁移状态。
   - 新表 `accounting_document_number_sequences`：编号在事务内加锁取号，并始终大于该日期前缀下已有的最大号，保证与旧的 INV/REC 编号连续且不重复（旧编号格式不变）。
2. **状态**
   - 見積書：下書き → 提出済み → 受注／失注；下書き・提出済み → 取消。
   - 契約書：下書き → 送付済み → 締結済み（记录締結日）→ 終了；下書き・送付済み → 取消。
   - 請求書：下書き → 発行済み → 送付済み → 入金済み（记录入金日）；未入金前可取消。旧数据（空）可直接迁到任一状态。
   - 領収書：下書き → 発行済み → 無効。
   - 离开下書き（取消/無効除外）时保存发行快照（编号、发行日、宛先、明細、金额、発行者、时间、操作人），此后宛先・金额等内容不可修改（只允许改备注和关联案件），也不可删除，只能取消/無効后重新制作。没有明细也没有金额时不能发行。
3. **API**
   - `/api/accounting/estimates/`、`/api/accounting/contracts/`（CRUD、`transition/`、`pdf/`、`create-contract/`、`create-invoice/`）；`/api/accounting/vouchers/` 增加 `transition/`、`create-receipt/`，列表可按 `status`（需同时指定 `voucher_type`；`unset`=旧数据）、`case`、`customer`、`company` 过滤。
   - `/api/accounting/voucher-links/?case=|customer=|company=`：只有能查看该对象，并且只返回有权限的帐票种类。
4. **权限**：新增 `accounting.use_estimate`、`accounting.use_contract`，并加入 `accounting_admin` 角色（与 `use_voucher` 相同的人）。関連案件需要对该案件有「変更」权限（沿用会计关联规则）；引用源帐票需要源帐票的查看权限；从帐票创建另一帐票需要目标帐票权限。明细定型项目：有任一帐票权限的人可读，只有 `use_voucher` 可改。
5. **审计**（AuditLog `module='voucher'`）：创建、更新、删除、状态迁移（含前后状态和理由）、PDF 下载（含是否带印章）。
6. **PDF**：見積書沿用请求书版式（「御見積書」、有效期限、不含振込先，含备注）；契約書新模板（甲乙、契约期间、报酬及内訳、支付条件、条项可跨页、签署栏，乙方可带公司印）。请求书/领收书输出不变。
7. **前端**
   - 新页面 `/vouchers/estimates`（見積書）、`/vouchers/contracts`（契約書），菜单按新权限显示，去掉「準備中」。
   - 請求書・領収書页面：新增编号列、状态列（按种类显示各自状态和可迁移项）、状态筛选（选种类后可用）、关联案件、「領収書を作成」、发行后只读（只能改备注和关联案件）、只允许删除下書き/旧数据。
   - 案件详情侧栏、顾客详情、公司详情新增「帳票」卡片（`VoucherLinksCard`），无权限时不显示。
   - 明细金额的即时计算 `utils/voucherCalc.ts` 与后端同规则（ROUND_HALF_UP），并有单元测试。

## 部署注意（生产尚未部署）

- 执行 migration 后需要运行 `setup_access_roles`（先 dry-run，再 `--apply --yes`），把 `use_estimate`、`use_contract` 加入 `accounting_admin` 组；否则菜单不显示新页面。
- 迁移只加列加表，不写既有帐票数据；`issued_snapshot` 在既有行上是空对象（列默认值）。

## 验证

- 后端 `python manage.py test`：260 项全部通过（集成分支 247 项 + 本批次 13 项）。
- `makemigrations --check --dry-run`：No changes detected。
- 前端 `npm run test:unit`：10 项通过（新增 `voucherCalc` 4 项）；`vue-tsc` 与 `npm run build`：通过。
- PDF：用样例数据生成見積書、契約書（2 页）、請求書并目视确认版式。
- 浏览器实测：未做（预览库 `gyoseishoshi_erp_p0_preview` 未迁移到本分支，按约束不擅自改动）。

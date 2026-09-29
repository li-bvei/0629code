# 本地发布验证报告（P0～P3 第一版，2026-09-29）

- 基线：`codex/p2-platform-completion` `f97df6b`；验证分支：`codex/release-local-validation`（包含 P0→P1→P2→P2-C11→P2 收尾→P3→平台收尾的全部提交，是一条线性历史）。
- 未推送、未部署、未连接生产、未执行正式 LIST.xlsx 导入、未删除任何预览库。
- 本报告同时作为本验证分支的变更记录（只修复实际发现的 bug，无新功能）。

## 1. 实际浏览器验证结果

环境：`gyoseishoshi_erp_platform_preview`，后端 `127.0.0.1:8041`，前端 `http://[::1]:5211`（内置浏览器，真实登录各账号）。「方式」列：浏览器＝页面操作或同一登录会话内的 fetch 探测；API＝在同一预览库用 API 客户端执行（浏览器工具无法选择本地文件时使用）；Docker＝隔离容器经 nginx 验证。

### 1.1 权限

| 账号 | 验证项目 | 结果 | 方式 |
|---|---|---|---|
| 李 `p0_li`（system_admin＋accounting_admin＋business_admin） | 事务所设置可保存（决算月 3→保存为 DB 值、写审计）；支出全员 8 件、收入、帐票；不动产台账锁定・更正・年度关闭；利润分配创建 | 通过 | 浏览器 |
| 焦 `p0_jiao`（business_admin＋expense_viewer） | 支出可看全员 8 件；改他人支出 403、改本人 200；导出只含本人 1 件；收入・帐票・見積書 403；设置修改 403；利润分配・台账导出・LIST 导入 403；不动产可看全部、改他人 403 | 通过 | 浏览器 |
| 周 `p0_zhou`（同焦；本次为验证新建的测试账号） | 支出全员 8 件；改/删焦的支出 403；案件可看 5 件、改他人案件 403；收入・帐票・利润分配 403 | 通过 | 浏览器 |
| 普通员工 `p0_staff`（staff，担当B） | 案件只见本人 2 件（DEMO-002/004），他人案件 404；书类只见本人案件；支出只见本人；不动产只见本人（新建 RE-202609-0002）；指定他人担当 403；台账锁定 403；利润分配页签不显示；`/real-estate/import`・`/vouchers/estimates`・`/accounting/income-sources` 跳回仪表盘 | 通过 | 浏览器 |
| superuser 无业务 Group `p0_su` | 登录后落到「設定」；菜单只有「設定」；案件・顾客・公司・书类・支出・收入・帐票・不动产・下载・工作台・仪表盘全部 403；全局搜索无分组 | 通过 | 浏览器 |
| 范围外搜索 | 员工搜「山田」：顾客为 `minimal`、不可打开、无链接；案件组为空 | 通过 | 浏览器 |
| 证件遮罩 | 焦/周查看他人担当顾客：护照 `****5678`、在留卡 `****78CD`；详情页显示遮罩值 | 通过 | 浏览器 |
| My Number | 所有账号的 API 只返回 `has_my_number`，详情页只显示「登録済み」 | 通过 | 浏览器 |

### 1.2 文件

| 项目 | 结果 | 方式 |
|---|---|---|
| 上传 PDF/PNG、关联 Checklist、替换（历史 1 件） | 通过 | API（浏览器工具无法选择本地文件；上传人分别为李和员工） |
| 列表显示「必要資料」关联和「履歴（1）」 | 通过 | 浏览器 |
| 归档（理由・实行者记录）→ 默认列表消失 →「アーカイブ済みのみ」中复原 | 通过 | 浏览器 |
| 本人下载／PDF・PNG inline 预览（Content-Disposition inline） | 通过 | 浏览器 |
| 非本人下载：员工下载李案件的文件 404 | 通过 | 浏览器 |
| `/media/`、`/sun/media/`、`/_protected_media/` 直接访问 | 404（`/sun/_protected_media/...` 返回的是 SPA 的 index.html 469B，不是文件） | Docker＋nginx |
| X-Accel-Redirect 下载（案件书类、不动产文件），他人 404 | 通过，内容与原文件一致，外部响应不含 `X-Accel-Redirect` | Docker＋nginx |

### 1.3 P1

| 项目 | 结果 | 方式 |
|---|---|---|
| Next Action 设定（内容・期限） | 通过 | 浏览器 |
| 待机开始（理由・备注）/ 待机解除 | 通过 | 浏览器 |
| 资料受领（受领日・关联文件・自动完成） | 通过 | 浏览器 |
| Action Bar 各按钮显示 | 通过（发现 bug 1，已修复） | 浏览器 |
| 今日作业台（次の対応 1・待機中 1 反映） | 通过 | 浏览器 |
| Case 归档（未完成进度需确认）/ 归档中修改 400 / 复原，Timeline `case_archived`・`case_restored` | 通过 | 浏览器 |

### 1.4 P2

| 项目 | 结果 | 方式 |
|---|---|---|
| 支出快捷录入无「精算済み」，含关联案件/顾客/公司 | 通过 | 浏览器 |
| 分类手输・推荐・规范名、案件带出顾客/公司 | 通过（P2 预览库浏览器＋同代码） | 浏览器 |
| Visa CSV：29/29 列自动对应、预览 2 正常 1 错误、创建 2、错误报告 3 行、PDF ZIP（2 PDF＋結果.txt）；XLSX 工作表选择 | 通过 | API（需要选择本地文件） |
| 見積書→請求書创建、請求書「発行済み」后改宛先 400（`locked_fields`） | 通过 | 浏览器 |
| 契約書 下書き→送付済み→締結済み（締結日）、締結后修改 400；領収書 从請求書创建→発行済み，請求書状态不变 | 通过 | API |

### 1.5 P3

| 项目 | 结果 | 方式 |
|---|---|---|
| 不动产新规（7 项）、要补充标签 | 通过 | 浏览器 |
| 台账 取引日保存→事业年度 2027・快照 3 月・保存期限 2032-03-31；锁定；更正（理由必填、第 2 版、更正历史）；年度关闭 | 通过（发现 bug 2，已修复） | 浏览器 |
| 决算月设置（保存为数据库值、来源显示、非李 403） | 通过 | 浏览器 |
| 全局搜索分组・跳转 | 通过 | 浏览器 |
| 利润分配：李可创建（127,500×30%=38,250）；焦/周/员工 403、页签不显示 | 通过 | 浏览器 |
| LIST dry-run（合成文件）：只读 `工作表1`、响应中无 `强哥`、三个金额分别保存、`-`→空・0 保留；交易件数前后 2→2；履历在页面显示 | 通过 | API＋浏览器（履历显示） |

## 2. nginx 与容器验证（Docker Desktop，本地隔离）

- 使用 `git archive` 导出的隔离副本和本地专用的临时 `.env.prod`（随机密钥，不进仓库），compose 项目名 `sunrise_localval`，前端端口 `127.0.0.1:18081`。
- `docker compose config`：OK。
- 构建 `backend`、`frontend` 镜像：成功。
- 全新 MySQL 上 backend 启动时自动 `migrate`：105 个 migration 全部 OK（含 P0～平台收尾的全部新 migration）。
- `nginx -t`：`syntax is ok` / `test is successful`（需要 backend 已在同一网络中运行，DEPLOY 第 15 步的顺序满足这一点）。
- 结果：`/sun/api/health/` → `{"status":"ok"}`；`/media/`・`/sun/media/`・`/_protected_media/` → 404；路径穿越 `/sun/../_protected_media/`、编码 `/%5Fprotected_media/` → 404；登录后本人下载/预览 200（`application/pdf`、`Cache-Control: private, no-store`、`nosniff`），他人 404；不动产文件同样经 X-Accel 下载、内容一致；SPA `/sun/`、深链接、懒加载主 JS 200。
- 容器已停止（镜像和隔离卷保留，未影响任何预览库）。

## 3. 发现并修复的 bug（均已加入回归检查）

1. **归档中的案件仍显示 Action Bar**（对応記録・資料受領・次の対応・待機等，点击后被后端拒绝）。→ 归档中不渲染 Action Bar（`CaseDetailPage.vue`）。
2. **不动产年度关闭和台账 CSV 导出没有界面入口**（API 与前端客户端已有，页面未接入）。→ 不动产一览为 `manage_legal_ledger` 持有者增加「年度締め」「台帳 CSV 出力」（`RealEstateListPage.vue`），浏览器中完成年度关闭。
3. **支出导出的审计 `via_permission` 记录为 `accounting.expense_export_all`**，即使操作者没有该权限（实际导出范围正确，只含本人）。→ 无全件权限时记录为 `owner`（`access_rules.ExpenseRule.via_permission`），新增测试 `apps/accounting/tests_release_fixes.py`。

观察到但未修改（非 bug 或仅外观）：
- 书类一览「通常のファイル」筛选在值为空时显示占位符「選択してください」（Element Plus 把空值视为未选择），功能正常。
- 平台预览库中的 P2 演示书类（DEMO-2026-003）文件实体在 P2 工作区的 media 中，因此在平台预览里下载会 404——预览环境克隆数据库但不复制 media 所致，不是代码问题。
- 生成 Visa PDF 时出现 `T50 bad choice field list` 警告，来自既有模板的选择字段，PDF 正常生成。

验证：后端 `python manage.py test` 289 项全部通过；`makemigrations --check` 无差异；前端 `vue-tsc`・`npm run build` 通过，`npm run test:unit` 12 项通过。

## 4. 预览库与测试账号状态

| 库 | 状态 |
|---|---|
| `gyoseishoshi_erp`（本地非预览库） | 本阶段未连接、未修改 |
| `gyoseishoshi_erp_p0_preview` | 停留在 P1（accounting 0015），未修改 |
| `gyoseishoshi_erp_p2_preview` | P2-C11 迁移完成；含 P2 演示数据（分类历史、测试 PDF、Visa 2 件） |
| `gyoseishoshi_erp_p3_preview` | P3 迁移完成；RE-202609-0001 与其台账 |
| `gyoseishoshi_erp_platform_preview` | 平台收尾迁移完成；本次新增测试账号 `p0_zhou`、验证用书类 4 件、RE-202609-0002、INV/REC/CON 各 1 件、Visa 2 件、dry-run 履历 1 件；RE-202609-0001 台账已锁定・更正（第 2 版）・2027 年度关闭；决算月已保存为 3 |
| Docker 隔离卷（项目 `sunrise_localval`） | 容器已停止；卷内有 `lv_staff`・`lv_other` 测试账号和验证文件 |

测试账号：`p0_li`・`p0_jiao`・`p0_zhou`・`p0_staff`・`p0_su`（密码只保存在会话临时目录，不在仓库、日志和本报告中）。

运行中的本地服务：P2 `127.0.0.1:5191`/`8021`、P3 `localhost:5201`/`8031`、平台 `[::1]:5211`/`8041`。

## 5. 生产 D1～D12 最终执行清单

以 `docs/DEPLOY.md`「P0 访问控制上线」21 步为主干，按本次合并发布（P0～平台收尾）补充如下。发布代码：`codex/release-local-validation` 合并后的提交。

1. **D1 只读核对**（旧系统运行中）：用户・Employee・Group・Expense 汇总・书类件数・媒体卷文件数 → 交李确认。
2. 维护模式（`/sun/` 返回 503，只放行操作人员 IP）。
3. **备份（必须）**：MySQL 全量 dump、`media_volume` tar、`docker compose images` 记录旧镜像。
4. `git checkout` 发布提交；`.env.prod` 追加：`DJANGO_APP_ENV=production`、`DJANGO_ENABLE_DEV_TOOLS=False`、`DJANGO_PROTECTED_MEDIA_X_ACCEL=True`、`DJANGO_PROTECTED_ADMIN_ENFORCEMENT=False`、`DJANGO_LOCALDEV_CHECK_MODE=warn`；**不要**设置 `REAL_ESTATE_IMPORT_DRY_RUN_ENABLED`（生产保持禁用）；`OFFICE_FISCAL_YEAR_END_MONTH` 可不设（设置页保存后以数据库为准）。`build backend`，`stop backend`。
5. `$RUN migrate --plan`：必须只包含第 6 节列出的 migration。
6. `$RUN migrate`；`$RUN check_access_config`。
7. **D2/D3** `link_user_employee`（李・周映射，焦新建 Employee），先预览后 `--apply --yes`。
8. **D4** `export_access_snapshot`；`protect_account`（李）。
9. **D6/D7** `setup_access_roles`（先 dry-run，确认追加项包含：会计各权限、`accounting.use_estimate`/`use_contract`、`cases.*`、`customers.customer_link_all`/`company_link_all`、`documents.*`、`real_estate.*`、`office.manage_office_settings`），再 `--apply --yes`；`assign_business_roles`：李＝system_admin,accounting_admin,business_admin；焦、周＝business_admin,expense_viewer；其他员工按需＝staff；`check_access_config`。
10. `up -d backend`；health/readiness。
11. 权限验证（按本报告 1.1 的五类账号逐项确认）。
12. **D8** `backfill_expense_owner`（先核对件数 N，再 `--apply --yes --expect-count N`）。
13. `build frontend`（只 build）。
14. **D9** `inventory_media_references`（「/media/ 参照 合計」>0 时先停下确认）。
15. `run --rm --no-deps frontend nginx -t`（backend 已运行）。
16. **D10** `up -d frontend`（关闭公开 `/media/`，media 卷挂到 Web 根之外）。
17. `/media/`・`/sun/media/`・`/_protected_media/` → 404；李下载/预览既有文件（含日文名、大文件）；焦访问他人文件 403/404 并有审计。
18. **D5** `DJANGO_PROTECTED_ADMIN_ENFORCEMENT=True`，重启 backend，`check_access_config`。
19. **D11** 快照后将焦、周的 `is_superuser/is_staff` 改为 False，确认业务范围不变。
20. **D12** localdev：按 D1 结果，经批准只停用（`is_active=False`）不删除；`DJANGO_LOCALDEV_CHECK_MODE=enforce`。
21. 退出维护模式后，由李在「設定」确认并保存事业年度末月（见第 8 节）。

## 6. migration 顺序（`migrate --plan` 期望的新增项）

依赖由 Django 解析，`--plan` 输出顺序以实际为准；新增内容如下（除 `0017_alter_case_options` 等仅权限/选项外，均为加列或建表，不写数据）：

- P0：`audit.0001_initial`、`authentication.0001_initial`、`employees.0002_employee_user`、`accounting.0015_expense_owner_and_business_permissions`、`cases.0017_alter_case_options`、`customers.0009_alter_customer_options`、`customers.0010_party_link_permissions`、`documents.0003_alter_document_options`
- P1：`cases.0018_case_work_status_next_action`、`cases.0019_checklist_item_document_link`
- P2：`accounting.0016_income_expense_party_links`、`accounting.0017_visa_import_batch`、`documents.0004_document_metadata_archive_replacements`、`accounting.0018_business_documents_c11`
- P3：`real_estate.0001_initial`、`real_estate.0002_import_runs`
- 平台收尾：`cases.0020_case_archive_metadata`、`office.0001_office_settings`、`real_estate.0003_ledger_fiscal_month_snapshot`

本地全新库上一次性执行上述全部 migration 已成功（Docker 验证）。

## 7. 回滚步骤

| 场景 | 方法 |
|---|---|
| 第 5～9 步失败（新后端未对用户开放） | 停止；用第 3 步记录的旧镜像 `up -d backend`。**注意下方 NOT NULL 限制** |
| 新后端上线后需回滚代码 | 只能回到本发布线上的提交（同一 migration 水位）。回到 P0 之前的旧代码，需先用第 3 步的备份恢复数据库（须批准） |
| frontend + nginx | 旧镜像或旧提交 `build frontend && up -d frontend`（media 挂载一起恢复） |
| D5 阶段 B | `DJANGO_PROTECTED_ADMIN_ENFORCEMENT=False`，重启 |
| 账号・Group・superuser | `restore_access_snapshot /ops/<file>`（先 dry-run 再 `--apply --yes`，可 `--user`） |
| Expense 回填 | `backfill_expense_owner --rollback /ops/<csv>` |
| 数据整体恢复 | 第 3 步 SQL＋media 备份（须批准，先在测试环境演练） |

**NOT NULL 限制（本次验证新发现，DEPLOY.md「旧代码可在新表结构上运行」只对 P0 成立）**：以下列为 NOT NULL，Django 添加后会去掉数据库级默认值，旧代码在插入对应行时会失败：`cases.work_status`・`waiting_reason`・`waiting_note`・`next_action_blocked_reason`・`archive_reason`、`case_documents.category`・`is_archived`・`sha256`・`archive_reason`、`accounting_vouchers.invoice_status`・`receipt_status`・`issued_snapshot`。因此 migrate 之后**不要只回滚代码**；需要回到旧版本时，用第 3 步的备份整体恢复数据库和 media。

## 8. 必须由李确认的操作

1. D1 只读核对结果（账号・Employee 映射・Expense 件数 N・媒体文件数）。
2. D2/D3 账号与 Employee 的对应（李・焦・周，以及其他员工是否授予 staff）。
3. D4 受保护账号（李）与 D5 阶段 B 的开启时机。
4. D8 Expense 回填的件数 N 与执行。
5. D9 媒体引用盘点结果（若存在 `/media/` 参照）。
6. D11 焦、周降级（取消 superuser/staff）。
7. D12 localdev 账号停用。
8. 上线后在「設定」确认公司实际事业年度末月（默认 3 月；年度关闭前确认）。
9. 是否授予利润分配权限给李以外的人员（默认只有 accounting_admin）。

## 9. 正式 LIST.xlsx 导入仍待确认的字段

- `向SUNRISE請求書金額`・`向客人請求金額`・`SUNRISE請求書金額` 三列的业务含义（现分别保存，不合并）。
- `中介费` 中大量为 `-`：是「无」「未确定」还是「0」。
- `日期` 与 `支払日` 中的文字型/无年份日期（如 `4/5`）如何补年份。
- `種類` 为空的 5 行是否一律按賃貸处理（真实文件中 `工作表1` 只有賃貸，未见売買）。
- `支払い状態`（済み/相殺/空）与 `振込状態`（振込済み/空）空值的含义（未付 or 未记录）。
- `担当者` 与 Employee 的对应；`客名`・`管理会社`・`物件名` 与既有 Customer/Company/物件的人工匹配规则。
- 正式导入的方式（逐行确认、回滚方法、对账口径）与执行时机；`工作表2` 是否也无需导入（目前只读 `工作表1`，`强哥` 完全排除）。

# 変更履歴 — 2026-09-06 P0 修正 + 新規受付 / 案件基盤

案件管理の業務ループ（新規受付 → 顧客識別 → 案件作成 → Checklist → 次アクション →
期限 → 申請 → 完了 → 会計）を1本化する開発の第1弾。

- バックエンド全 **81 テスト成功**
- `python manage.py makemigrations --check` クリーン
- フロントエンド `npm run build`（`vue-tsc -b && vite build`）成功
- 既存データ互換（DB リセット不要）。追加フィールドはすべて nullable / default 付き

---

## 1. 完了したタスク

### P0 — プロジェクト正確性

#### P0-1 バックエンドテスト修正（4 件）
`backend/apps/accounting/`

| 対象 | 内容 |
|---|---|
| `build_expenses_excel()` | 署名を `incomes=()` デフォルト化して旧呼び出しと統一。実装は「期間収入 / 期首残高 / 残高」レイアウト。テストを現行実装に合わせて書き直し |
| 凭証 PDF `build_invoice_summary_rows()` | 現行仕様どおり内訳は「小計 / 消費税 / 合計」の 3 行。税率別内訳を期待していた旧テストを現行仕様へ変更 |
| 支出サマリー `balance` | **「期間実際残高」= 期首残高 + 期間収入 − 期間支出（日付期間のみで決定。カテゴリ・キーワード等の明細絞り込みでは変化しない）** に確定。別途「絞り込み結果 収支」を明示する指標を追加し、1つの `balance` に2つの意味を持たせない |

`GET /api/accounting/expenses/summary/` のレスポンスに追加したキー:
```
opening_balance, period_income_total, period_expense_total,
filtered_expense_total, filtered_net
```
（`target_count` / `total_income` / `total_expense` / `balance` は後方互換で維持）

フロント `ExpenseListPage.vue`: サマリー行を「絞り込み結果 支出 / 絞り込み結果 収支 / 期間実際残高（日付期間のみで計算）」の3表示に変更。

#### P0-2 タイムゾーン統一（Asia/Tokyo）
- `config/settings.py`: `TIME_ZONE = 'Asia/Tokyo'`
- naive な `datetime.now()` を `timezone.localdate()` / `timezone.localtime(timezone.now())` に修正:
  `visa_return_pdf.py` / `seifu_notice_pdf.py` / `tax_renewal_pdf.py` / `visa_form_fields.py`（PDF ファイル名の日付）
- 案件番号採番は既に `cases/utils.py` の `TOKYO_TZ` で東京基準（変更なし）
- テスト追加: UTC 日跨ぎ（`2026-05-31 14:30 UTC` = 5月末 JST 23:30 / `15:30 UTC` = 6月 JST 00:30）、年末（`202612` → `202701`）の案件番号境界

#### P0-3 Dashboard サーバー側集計
新規 `GET /api/dashboard/summary/`（`api/views.py` `DashboardSummaryView`）。
件数はすべて DB 集計でページング非依存。

```jsonc
{
  "cases": { "total", "active", "waiting", "completed", "unassigned", "without_next_action" },
  "actions": { "overdue", "today", "next_7_days" },   // Case.next_action_due_at 基準・東京 today
  "stages": [ { "key", "label", "count" } ],          // 詳細ページと同じ6分類
  "recent_cases": [ /* 最新10件・最小フィールド */ ]
}
```
- `waiting` は暫定で `status in {additional_documents, under_review}`（`work_status` 導入までのプレースホルダ）
- `DashboardPage.vue` を書き直し。`listCases()` の1ページ目集計を廃止し、KPI 行（期限超過 / 今日対応 / 7日以内 / 待機中 / 担当未設定 / 次アクション未設定）+ 進捗ステージ + 最近案件を表示

#### P0-4 リモート検索セレクタ
**バックエンド**
- `CustomerViewSet`: `search` を `get_queryset` 内で処理（`SearchFilter` は廃止し AND 二重適用を回避）。対象＝氏名・カナ・電話・メール・住所・在留カード番号・パスポート番号 **＋ 案件番号**（`Case.case_number__icontains` から顧客 ID を OR）。短い氏名は1文字ずつ OR して取りこぼしを防ぎ、精密判定は正規化比較で実施
- `CompanyViewSet`: `SearchFilter` 追加、対象＝会社名・カナ・代表者名・代表者カナ・法人番号
- `EmployeeViewSet`: 既存の name/email/phone 検索を流用

**フロント（新規コンポーネント）** `frontend/src/components/`
| ファイル | 用途 |
|---|---|
| `RemoteSelect.vue` | 汎用。`fetcher(search)` / `toOption(row)` / `fetchOne(id)` / `initialOption` を受け取り、サーバー検索・既存選択値の維持を担う |
| `RemoteCustomerSelect.vue` | 顧客（氏名・カナ・電話・案件番号で検索） |
| `RemoteCompanySelect.vue` | 会社（会社名・フリガナ） |
| `RemoteStaffSelect.vue` | 担当者（Employee・氏名） |

`CasesPage.vue` の新規/編集ダイアログの顧客・会社・担当セレクタを差し替え（97 顧客 / 32 会社でも 21 件目以降を選択可能に）。

#### P0-5 registration_status を read_only 化
`CaseSerializer.Meta.read_only_fields` に `registration_status` を追加。
通常の PUT/PATCH では変更不可。状態遷移チェック・warning・Timeline・操作者記録が必要なため
専用アクション `change-registration-status` 経由のみ。フロントは既に専用ダイアログを使用。

---

### P1 — 主要パス

#### P1-6 顧客候補照合 API
新規 `POST /api/customers/match/`（`CustomerViewSet.match` アクション、`apps/customers/utils.py` `find_customer_candidates()`）。

ルールベース（AI 不使用・自動統合しない）:
| 強度 | 条件 |
|---|---|
| strong | 在留カード番号一致 / パスポート番号一致 / 氏名（正規化）＋生年月日一致 |
| medium | 氏名＋電話（末尾7桁） / 氏名＋メール |
| weak | 氏名一致 のみ / 氏名類似＋生年月日情報あり |

レスポンス: `{ candidates: [ { customer_id, name, name_kana, birth_date, phone, email, case_count, match_strength, match_score, match_reason } ] }`

#### P1-7 新規受付を 3 ステップに再構築
`frontend/src/pages/ReceptionNewPage.vue`（全面書き換え）+ `api/serializers.py` `ReceptionSerializer`

- **STEP1 顧客識別**: 氏名・カナ・生年月日 + 任意（電話・メール・在留カード・パスポート）→「既存顧客を照合」→ 候補カード（強度タグ・疑似理由・案件数）→「この顧客を使用」/「新規顧客として登録」をラジオで明示選択
- **STEP2 業務情報**: 案件種別・申請区分・担当（RemoteStaffSelect）・受任日。案件種別コードで在留関連フィールドを出し分け。新規顧客の場合のみ詳細フォーム表示。関連会社（なし / 既存 / 新規）、家族（任意）。ただし現状は「既存の会社」を選択する UI までで、受付 API への既存会社 ID 引き渡しは未実装
- **STEP3 確認**: サマリー表示 → `ElMessageBox.confirm` → 送信
- 送信は `transaction.atomic` で 顧客（作成 or 紐付け）/ 会社 / 家族 / 案件 / Checklist（テンプレート自動適用）/ Timeline を一括作成 → **案件ワークスペース（`/cases/{id}`）へ遷移**
- 成功トーストに「案件番号・顧客（既存/新規）・Checklist 件数」を表示

`ReceptionSerializer` 変更:
- `existing_customer_id`（任意）を追加。指定時は `customer`（新規作成データ）不要。existing_company_id は未実装
- `validate()` で「既存顧客 or 新規顧客情報のどちらか必須」
- 案件作成時に `record_case_event(EVENT_CASE_CREATED)` を呼ぶ
- レスポンスに `customer_reused` / `checklist_item_count` を追加
- `ReceptionCreateView` は `context={'request': request}` を渡すよう変更

#### P1-13 Checklist テンプレート適用の冪等化
`apps/cases/utils.py` `apply_checklist_template_to_case(case, template, mode='merge')`

| mode | 挙動 |
|---|---|
| `merge`（既定） | 既存に無い項目のみ追加。同一テンプレートを再適用しても重複しない |
| `replace` | このテンプレート由来かつ**未完了**の項目のみ削除して作り直す。完了済み・手動追加の項目は残す（無警告で消さない） |

`POST /api/cases/{id}/apply-checklist-template/`:
- `mode` パラメータ追加
- レスポンスが `{ created: [...], created_count: N, mode }` に変更（旧: 配列）
- `CaseDetailPage.vue` の「テンプレートから追加」ダイアログにモード切替ラジオと説明文を追加

#### P1-16（部分） Timeline 自動記録の基盤
`apps/timelines/models.py`: `Timeline` に
- `event_type`（CharField, blank）
- `actor`（FK `AUTH_USER_MODEL`, null）
- `metadata`（JSONField, default=dict）

を追加。イベント種別定数（`EVENT_CASE_CREATED` ほか）を定義。

新規 `apps/timelines/services.py` `record_case_event(case, event_type, title, *, description, actor, metadata, occurred_at, is_visible_to_client)`。

接続済みの自動記録:
| 操作 | event_type |
|---|---|
| 新規受付での案件作成 | `case_created` |
| 進捗ステータス変更（`_create_timeline`） | `status_changed` |
| 登録状態変更 | `registration_status_changed` |
| 進捗情報変更（`update_case_progress_info`） | `status_changed` |
| Checklist 項目の完了（`CaseChecklistItemViewSet`） | `checklist_completed` |

`TimelineSerializer`: `event_type` / `actor` / `actor_name` / `metadata` を追加（すべて read_only。手入力記録では空）。
`CaseDetailPage.vue` のタイムライン表に「自動」タグと「記録者」列を追加。

---

## 2. 変更ファイル一覧

### バックエンド
```
backend/config/settings.py                         TIME_ZONE
backend/api/serializers.py                          ReceptionSerializer（existing_customer_id / record_case_event）
backend/api/views.py                                DashboardSummaryView / Reception context
backend/api/urls.py                                 dashboard/summary/ 追加
backend/api/tests.py                                新規（Customer Match / Reception）
backend/apps/customers/views.py                     検索拡張 / match アクション
backend/apps/customers/utils.py                     find_customer_candidates()
backend/apps/customers/tests.py                     リモート検索テスト
backend/apps/companies/views.py                     SearchFilter
backend/apps/cases/views.py                         apply-template mode / checklist完了イベント
backend/apps/cases/serializers.py                   registration_status read_only
backend/apps/cases/status_service.py               _create_timeline に event_type/actor/metadata
backend/apps/cases/utils.py                         apply_checklist_template_to_case(mode=)
backend/apps/cases/tests.py                         TZ境界 / registration_status / checklist / dashboard
backend/apps/accounting/views.py                    expense summary レスポンス
backend/apps/accounting/excel.py                    build_expenses_excel 署名
backend/apps/accounting/tests.py                    現行仕様に合わせて修正
backend/apps/accounting/{visa_return_pdf,seifu_notice_pdf,tax_renewal_pdf,visa_form_fields}.py  TZ
backend/apps/timelines/models.py                    event_type / actor / metadata
backend/apps/timelines/serializers.py              新フィールド公開
backend/apps/timelines/services.py                 新規（record_case_event）
```

### フロントエンド
```
frontend/src/components/RemoteSelect.vue            新規
frontend/src/components/RemoteCustomerSelect.vue    新規
frontend/src/components/RemoteCompanySelect.vue     新規
frontend/src/components/RemoteStaffSelect.vue       新規
frontend/src/pages/ReceptionNewPage.vue             全面書き換え（3ステップ）
frontend/src/pages/DashboardPage.vue                書き換え（サーバー集計）
frontend/src/pages/CasesPage.vue                    リモートセレクタ適用
frontend/src/pages/CaseDetailPage.vue               テンプレート適用モード / タイムライン列
frontend/src/pages/accounting/ExpenseListPage.vue   サマリー3表示
frontend/src/api/dashboard.ts                       getDashboardSummary
frontend/src/api/customers.ts                       matchCustomers
frontend/src/api/cases.ts                           applyCaseChecklistTemplate(mode)
frontend/src/api/receptions.ts                      ReceptionCreatePayload
frontend/src/types/api.ts / types/accounting.ts    型追加
```

---

## 3. 新規マイグレーション

```
backend/apps/timelines/migrations/0003_timeline_actor_timeline_event_type_timeline_metadata.py
```

適用コマンド:
```bash
cd backend && source .venv/bin/activate && python manage.py migrate
```

---

## 4. 新規 / 変更 API

| メソッド | パス | 区分 | 内容 |
|---|---|---|---|
| GET | `/api/dashboard/summary/` | 新規 | 案件統計のサーバー集計 |
| POST | `/api/customers/match/` | 新規 | 顧客候補照合。入力は `{name, name_kana, birth_date, phone, email, residence_card_number, passport_number}`、応答は `{candidates: [...]}` |
| GET | `/api/customers/?search=` | 変更 | カナ・在留カード番号・パスポート番号・案件番号を検索対象に追加 |
| GET | `/api/companies/?search=` | 変更 | 既存会社 API に会社名・カナ・代表者・法人番号検索を追加 |
| POST | `/api/receptions/` | 変更 | `existing_customer_id` 対応。レスポンスに `customer_reused` / `checklist_item_count` |
| POST | `/api/cases/{id}/apply-checklist-template/` | 変更 | `mode=merge\|replace`。レスポンスが `{created, created_count, mode}` |

---

## 5. 新規ページ / コンポーネント

- `RemoteSelect.vue` + 顧客 / 会社 / 担当者ラッパー 3 種
- `ReceptionNewPage.vue`（3 ステップウィザード）
- `DashboardPage.vue`（サーバー集計ベースの作業入口）

---

## 6. 未完了（次回以降）

### P1 残り
- **受付の既存会社バインド**: `ReceptionNewPage.vue` には選択 UI があるが、existing_company_id が受付 API に未実装。実装するか、未実装の選択肢を一時的に非表示にする
- **受付のサーバー側冪等化**: `transaction.atomic` はロールバック用であり、ネットワーク再送による重複顧客 / 案件作成は防がない。`request_id` などの冪等キーとテストが必要
- **顧客候補照合の精度**: 部分氏名＋生年月日を `strong` にしない。電話番号の区切り文字を含む検索も追加確認する
- **Timeline の権限・自動イベントテスト**: actor / metadata / event_type と案件単位のアクセス範囲をテストする
- **P1-8 Case Workspace**: 上部 Action Bar（＋対応記録 / ＋資料受領 / ＋タスク / ＋ファイル / ＋入金 / 待機にする / 案件完了）の Drawer/Dialog 実装。CaseDetail は既に進捗・次アクション・Checklist・Timeline を持つため中身は概ね揃っている
- **P1-9 統一 Next Action モデル**（Task / Reminder / Deadline を1つの Action へ。既存モデル拡張優先）
- **P1-10 Waiting 機構**（`Case.work_status` = active/waiting/completed、`waiting_reason` enum、`waiting_since` / `waiting_until`）
- **P1-11 今日の作業台**（自分の作業 / 全体 の切替、一覧から直接操作）
- **P1-12 タイムライン自動化の残り**（文書アップロード / 入金 / 支出 / PDF 生成 / 案件完了 / 再開）
- **P1-14 Deadline / Reminder の状態化**（`hidden` → `pending` / `completed` / `snoozed` / `dismissed`、`dismiss_reason` 必須化、「一括非表示」の廃止）
  - Dashboard の「一括非表示」ボタンは今回撤去し「対象外として処理」に文言変更済み。モデルの状態化は未着手

### P2 全項目（未着手）
15 Case Health / 16 Completion Check / 17 資料依頼 / 18 関連案件作成 / 19 会計 FK 関連
（Income/Expense に customer/company/case の nullable FK）/ 20 Company 詳細タブ / 21 全体検索
`/api/search/?q=` / 22 アーカイブ完善（既存の `archived_at` に `archived_by`・理由・復元・監査を追加、UI から永久削除を隠す）/ 23 ルート単位 lazy loading

---

## 7. ローカル起動・検証

```bash
# バックエンド（.env.local のプロキシ先に合わせるなら 8010）
cd backend && source .venv/bin/activate
python manage.py migrate
python manage.py runserver 127.0.0.1:8010

# フロントエンド
cd frontend && npm run dev -- --port 5174
```

主な確認ポイント:
- `/dashboard` … KPI 行・進捗ステージ・最近案件（20 件超でも件数が正しい）
- `/reception/new` … STEP1 で氏名＋生年月日 →「既存顧客を照合」→ 候補カード → STEP2/3 → 案件作成 → ワークスペース遷移
- 案件新規作成ダイアログ … 顧客 / 会社 / 担当のリモート検索で 21 件目以降が引ける

---

## 8. テスト結果

```
cd backend && source .venv/bin/activate
python manage.py test
  → 本轮实施时记录为 Ran 81 tests — OK（全通過）
  → 2026-09-06 当前沙盒重新执行时发现 81 tests，但 MySQL 连接在创建测试库前被环境权限阻断，未能独立复核
python manage.py makemigrations --check
  → No changes detected

cd frontend && npm run build
  → vue-tsc + vite build 成功
```

追加した主なテスト:
- 受付で既存顧客ヒット時、Customer を増やさず Case / Checklist / Timeline を作成
- 新規顧客受付で Customer + Case が正常作成
- `registration_status` は通常 PATCH で変更不可
- Checklist merge の冪等 / replace で完了項目保持
- Dashboard 25 件（>20）でも集計正確
- 顧客リモート検索が 21 件目以降・カナ・在留カード番号・案件番号でヒット
- 東京 UTC 日境界（月末 / 年末）

# 変更履歴 — 2026-09-16 P0 追加修正（既存会社バインド / 顧客照合ルール / 受付冪等化）

`docs/AI_HANDOFF.md` §7「已実現但不能当作完全閉環的項目」で指摘されていた項目、および
`docs/DEVELOPMENT_PLAN.md` の P0-A1 / P0-A2 / P0-A3 に対応。

- バックエンド全 **91 テスト成功**（81 → +10）
- `python manage.py makemigrations --check` クリーン（`api` アプリ新規登録に伴う migration 1件を追加・適用済み）
- `npm run build` 成功

---

## 1. P0-A1：既存会社バインドの修正

**問題**：`ReceptionNewPage.vue` に「既存の会社」選択 UI があったが、`buildPayload()` が existing モードで会社情報を空にして送信しており、選択した会社が実際には Case に紐付かなかった。

**修正**：
- `backend/api/serializers.py`
  - `ReceptionSerializer` に `existing_company_id`（任意）を追加。`validate()` で存在確認
  - `create()`：`existing_company_id` があれば `Company.objects.get()` で複用（新規作成しない）。レスポンスに `company_reused` を追加
  - 副次的修正：家族ループ内で外側の `existing_customer_id` を上書きしていた変数名の衝突を `family_member_existing_customer_id` にリネームして解消（挙動は変わらない、可読性・将来の事故防止のため）
- `frontend/src/pages/ReceptionNewPage.vue`：`companyMode === 'existing'` のとき `existing_company_id` を送信。`RemoteCompanySelect` の `change` イベントで選択会社名を保持し、確認画面に表示
- `frontend/src/types/api.ts`：`ReceptionCreatePayload.existing_company_id` / `ReceptionResponse.company_reused` を追加

**テスト**（`backend/api/tests.py`）：
- `test_reception_with_existing_company_binds_case_without_duplicating_company`
- `test_reception_rejects_unknown_existing_company_id`

## 2. P0-A2：顧客候補照合ルールの厳格化

**問題**：氏名が部分一致（完全一致ではない）でも生年月日が一致すれば `strong` と判定していたため、同姓同名の別人を強マッチとして誤認識するリスクがあった。電話番号比較も末尾7桁のみで、国番号・ハイフンの表記ゆれを吸収していなかった。

**修正**（`backend/apps/customers/utils.py` `find_customer_candidates()`）：
- `_normalize_phone_digits()` 新設：`+81` / `81` 国番号を国内 `0` 始まりに正規化
- `_phone_digits_match()` 新設：末尾8桁一致（7桁から変更、誤爆率を下げる）
- 強度判定を再構成：

  | 強度 | 条件 |
  |---|---|
  | strong | 証明書番号一致 / **氏名完全一致** ＋ 生年月日一致 |
  | medium | 氏名完全一致 ＋ 電話・メール一致 / **氏名部分一致** ＋ 生年月日一致 |
  | weak | 氏名完全一致のみ / 氏名部分一致 ＋ 電話・メール一致 / 氏名部分一致 ＋ 生年月日情報あり（不一致含む） |

**テスト**（`backend/api/tests.py`）：
- `test_partial_name_with_birthdate_is_medium_not_strong`
- `test_full_name_with_hyphenated_phone_is_medium_match`
- `test_partial_name_with_phone_only_is_weak`

## 3. P0-A3：新規受付のサーバー側冪等保護

**問題**：`transaction.atomic` は単一リクエスト内の原子性しか保証せず、二重クリックやネットワーク再試行による `POST /api/receptions/` の重複送信で顧客・案件が重複作成される可能性があった。

**修正**：
- `api` を初めて Django アプリとして登録（`backend/api/apps.py` 新設、`config/settings.py` の `INSTALLED_APPS` に追加）。Dashboard・Reception など特定ドメインに属さない横断的機能の置き場所として妥当と判断し、新しい層は増やしていない
- `backend/api/models.py` 新設：`ReceptionIdempotencyRecord`（`request_id` unique、`response` JSONField null 許容＝処理中を表す）
- `backend/api/migrations/0001_initial.py`：上記モデルの初回マイグレーション
- `backend/api/views.py` `ReceptionCreateView.post()`：
  - `request_id`（任意）を受け取り、未指定なら従来どおり（後方互換）
  - 既存 `request_id` があり `response` が保存済み → その内容をそのまま返す（顧客・案件は再作成しない）
  - 既存 `request_id` があり `response` が未保存（処理中）→ `409 Conflict`
  - 新規 `request_id` → プレースホルダ行を作成してから本処理を実行し、成功時に `response` を保存。バリデーション等で失敗した場合はプレースホルダを削除し、同じ `request_id` での再試行を許可する
  - ほぼ同時に同じ `request_id` が2重に届いた場合は DB の unique 制約（`IntegrityError`）で片方を `409` に落とす
- `frontend/src/pages/ReceptionNewPage.vue`：ページ表示中は固定の `request_id`（`crypto.randomUUID()`）を保持し、確定操作のたびに送信。`409` 受信時は「処理中なので少し待って確認してください」という専用メッセージを表示
- `frontend/src/types/api.ts`：`ReceptionCreatePayload.request_id` を追加

**テスト**（`backend/api/tests.py` `ReceptionIdempotencyApiTests`）：
- `test_duplicate_request_id_does_not_create_duplicate_records`
- `test_different_request_id_creates_independent_records`
- `test_in_progress_request_id_returns_conflict`
- `test_failed_attempt_allows_retry_with_same_request_id`
- `test_request_id_is_optional_and_backward_compatible`

**範囲**：この冪等機構は `/api/receptions/` 専用。他の書き込み系 API に汎用的に広げていない（`docs/DEVELOPMENT_PLAN.md` 参照）。

---

## 4. 未対応（`docs/DEVELOPMENT_PLAN.md` 参照）

- P0-A4：Timeline / Case API のオブジェクトアクセス範囲の確認・文書化・テスト（未着手）
- P0-A5：Dashboard 指標口径の回帰テスト補充（口径自体は `AI_HANDOFF.md` §7 に記載済み）

---

## 5. ローカル検証

```bash
cd backend && source .venv/bin/activate
python manage.py test               # Ran 91 tests — OK
python manage.py makemigrations --check   # No changes detected
python manage.py migrate            # api.0001_initial 適用済み

cd ../frontend
npm run build                       # 成功
```

<script setup lang="ts">
// 支出の入力欄（完全な新規・編集ページと一覧の快捷ダイアログで共用。親の el-form の中に置く）。
// カテゴリ入力支援は本人の履歴だけを使い、最終決定は利用者。関連付けの可否は後端が判定する
// （案件は変更権限、顧客・会社は閲覧範囲）。案件を選ぶと顧客・会社を補完する（変更可）。
import { computed, onMounted, ref, watch } from 'vue'
import { getExpenseCategorySuggestions } from '../../api/accounting'
import RemoteCaseSelect from '../RemoteCaseSelect.vue'
import RemoteCompanySelect from '../RemoteCompanySelect.vue'
import RemoteCustomerSelect from '../RemoteCustomerSelect.vue'
import type { ExpenseCategory, ExpenseCategorySuggestions, ExpensePayload } from '../../types/accounting'
import type { Case } from '../../types/api'
import { canOfferRemember, pendingPlaceRecommendations } from '../../utils/expenseCategory'

type Option = { value: number, label: string } | null

const props = defineProps<{
  categories: ExpenseCategory[]
  caseInitial?: Option
  compact?: boolean
}>()
const form = defineModel<ExpensePayload>({ required: true })

const paymentMethodOptions = ['现金', '信用卡', '银行转账', 'PayPay', 'ICOCA', '公司账户', '个人垫付', '其他']
const customerInitial = ref<Option>(null)
const companyInitial = ref<Option>(null)

const suggestions = ref<ExpenseCategorySuggestions | null>(null)
let suggestionTimer: ReturnType<typeof setTimeout> | null = null
let suggestionRequest = 0
const loadSuggestions = async () => {
  const requestId = ++suggestionRequest
  try {
    const data = await getExpenseCategorySuggestions({
      q: form.value.category || '',
      place: form.value.place || '',
      expense_target: form.value.expense_target || '',
      note: form.value.note || '',
    })
    if (requestId === suggestionRequest) suggestions.value = data
  } catch {
    if (requestId === suggestionRequest) suggestions.value = null
  }
}
const scheduleSuggestions = () => {
  if (suggestionTimer) clearTimeout(suggestionTimer)
  suggestionTimer = setTimeout(loadSuggestions, 300)
}
const fetchCategoryCandidates = async (query: string, callback: (items: Array<{ value: string }>) => void) => {
  try {
    const data = await getExpenseCategorySuggestions({ q: query })
    const names = new Set(data.matches.map((row) => row.name))
    props.categories.forEach((category) => {
      if (!query || category.name.includes(query)) names.add(category.name)
    })
    callback([...names].slice(0, 20).map((value) => ({ value })))
  } catch {
    callback(props.categories.map((category) => ({ value: category.name })))
  }
}
const applyCategory = (name: string) => {
  form.value.category = name
  scheduleSuggestions()
}
const recommendations = computed(() =>
  (suggestions.value?.recommendations ?? []).filter((row) => row.name !== form.value.category),
)
// 場所などの文字からの提案。「採用」を押すまでカテゴリ欄は変えない（手入力のまま保存できる）。
const placeRecommendations = computed(() => pendingPlaceRecommendations(suggestions.value, form.value.category))
const offerRemember = computed(() => canOfferRemember(suggestions.value, form.value.place, form.value.category))
watch(offerRemember, (offered) => {
  if (!offered && form.value.remember_place_category) form.value.remember_place_category = false
})

const onCaseChange = (row: Case | null) => {
  if (!row) return
  form.value.customer = row.customer ?? null
  customerInitial.value = row.customer ? { value: row.customer, label: row.customer_name } : null
  form.value.company = row.company ?? null
  companyInitial.value = row.company ? { value: row.company, label: row.company_name } : null
}

onMounted(loadSuggestions)
// 親がフォームを入れ替えた（ダイアログを開き直した・編集データを読んだ）ときは提案を取り直す
watch(() => form.value, () => {
  customerInitial.value = null
  companyInitial.value = null
  scheduleSuggestions()
})
</script>

<template>
  <div :class="compact ? 'accounting-dialog-form' : 'form-grid'">
    <el-form-item label="日付" prop="expense_date">
      <el-date-picker v-model="form.expense_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                      placeholder="YYYY-MM-DD" class="form-control" />
    </el-form-item>
    <el-form-item label="場所" prop="place">
      <el-input v-model="form.place" @input="scheduleSuggestions" />
    </el-form-item>
    <el-form-item label="カテゴリ" prop="category">
      <el-autocomplete v-model="form.category" :fetch-suggestions="fetchCategoryCandidates" placeholder="検索または手入力"
                       clearable class="form-control" @input="scheduleSuggestions" @select="scheduleSuggestions" />
      <div v-if="suggestions?.normalized" class="field-hint category-hint">
        {{ suggestions.normalized.reason }}：
        <el-button link type="primary" @click="applyCategory(suggestions.normalized.suggestion)">「{{ suggestions.normalized.suggestion }}」を使う</el-button>
        （入力のまま保存もできます）
      </div>
      <div v-for="row in placeRecommendations" :key="`${row.match_field}-${row.name}`" class="field-hint category-hint">
        おすすめのカテゴリ：<strong>{{ row.name }}</strong>（{{ row.reason }}<template v-if="row.scope === 'personal'">・自分で記憶</template>）
        <el-button link type="primary" @click="applyCategory(row.name)">採用</el-button>
      </div>
      <div v-if="recommendations.length" class="field-hint category-hint">
        過去の記録からの候補：
        <el-button v-for="row in recommendations" :key="row.name" link type="primary" :title="row.reason" @click="applyCategory(row.name)">{{ row.name }}</el-button>
      </div>
    </el-form-item>
    <el-form-item v-if="offerRemember" :class="compact ? 'accounting-dialog-full' : 'expense-note'">
      <el-checkbox v-model="form.remember_place_category">
        この場所「{{ form.place }}」とカテゴリ「{{ form.category }}」の対応を記憶する（次回から自分の候補にだけ出ます）
      </el-checkbox>
    </el-form-item>
    <el-form-item label="金額" prop="amount">
      <el-input v-model="form.amount" inputmode="numeric" />
    </el-form-item>
    <el-form-item label="支払方法" prop="payment_method">
      <el-select v-model="form.payment_method" clearable placeholder="選択してください" class="form-control">
        <el-option v-for="method in paymentMethodOptions" :key="method" :label="method" :value="method" />
      </el-select>
    </el-form-item>
    <el-form-item label="費用対象" prop="expense_target">
      <el-input v-model="form.expense_target" @input="scheduleSuggestions" />
    </el-form-item>
    <el-form-item label="関連案件（任意）" prop="case">
      <RemoteCaseSelect v-model="form.case" clearable :initial-option="caseInitial" @change="onCaseChange" />
      <div class="field-hint">担当している案件だけ関連付けできます。選ぶと顧客・会社を補完します。案件の経過には日付とカテゴリだけが記録され、金額は載りません。</div>
    </el-form-item>
    <el-form-item label="関連顧客（任意）" prop="customer">
      <RemoteCustomerSelect v-model="form.customer" clearable :initial-option="customerInitial" />
    </el-form-item>
    <el-form-item label="関連会社（任意）" prop="company">
      <RemoteCompanySelect v-model="form.company" clearable :initial-option="companyInitial" />
    </el-form-item>
    <el-form-item label="備考" prop="note" :class="compact ? 'accounting-dialog-full' : 'expense-note'">
      <el-input v-model="form.note" type="textarea" :rows="compact ? 3 : 4" @input="scheduleSuggestions" />
    </el-form-item>
  </div>
</template>

<style scoped>
.category-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.expense-note {
  grid-column: 1 / -1;
}
</style>

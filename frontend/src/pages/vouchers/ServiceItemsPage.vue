<script setup lang="ts">
// サービス価格マスタ（P4）。見積書・請求書の明細と新規受付で選ぶ項目と標準価格を管理する。
// 委託底価は外部専門家への基本費用（社内用）。底価権限者にだけ表示・入力欄を出す（後端でも項目ごと出し分ける）。
// 使われた項目は削除できない（無効化すると新しくは選べないが、過去の帳票・案件の内容はそのまま残る）。
// P6：基本項目は「暫定価格」で登録される。管理権限と底価権限の両方を持つ人が二段階の確認で「価格を確定」する。
// 確定後に価格・税区分・単位・底価を変えると暫定に戻る（後端が判定）。過去の帳票・案件の内容は変わらない。
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { confirmServiceItemPrice, deleteServiceItem, listServiceItems, saveServiceItem } from '../../api/serviceItems'
import { useAuthStore } from '../../stores/auth'
import type { ServiceItem, ServiceItemPayload } from '../../types/accounting'
import { apiErrorText } from '../../components/vouchers/voucherErrors'
import { formatYen } from '../../utils/voucherCalc'
import { formatDateTime } from '../../utils/date'
import '../accounting/accounting.css'

const auth = useAuthStore()
const canManage = computed(() => auth.can('accounting.manage_service_item'))
const canSeeFloor = computed(() => auth.can('accounting.view_service_floor_price'))
const canConfirmPrice = computed(() => canManage.value && canSeeFloor.value)

const PROFESSIONAL_OPTIONS = [
  { value: '', label: 'なし' }, { value: 'gyousei', label: '行政書士' }, { value: 'tax_accountant', label: '税理士' },
  { value: 'judicial_scrivener', label: '司法書士' }, { value: 'labor_consultant', label: '社会保険労務士' },
  { value: 'other', label: 'その他' },
] as const

const rows = ref<ServiceItem[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const errorMessage = ref('')
const filters = reactive({ search: '', active: '1' as '' | '1' | '0' })

const fetch = async (target = page.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listServiceItems({ search: filters.search || undefined, active: filters.active || undefined, page: target, page_size: 50 })
    rows.value = data.results
    total.value = data.count
    page.value = target
  } catch (error) {
    errorMessage.value = apiErrorText(error, 'サービス項目を読み込めませんでした。')
  } finally {
    loading.value = false
  }
}

const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref<ServiceItem | null>(null)
const emptyForm = () => ({
  category: '', name: '', default_price: '' as string | number, price_type: 'tax_included' as ServiceItem['price_type'],
  floor_price: '' as string | number, professional_type: '' as ServiceItem['professional_type'],
  tax_category: 'tax_10' as ServiceItem['tax_category'], unit: '件', note: '', sort_order: 0, is_active: true,
})
const form = reactive(emptyForm())

const openCreate = () => {
  editing.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}
const openEdit = (row: ServiceItem) => {
  editing.value = row
  Object.assign(form, emptyForm(), {
    category: row.category, name: row.name, default_price: row.default_price ?? '', price_type: row.price_type,
    floor_price: row.floor_price ?? '', professional_type: row.professional_type, tax_category: row.tax_category,
    unit: row.unit, note: row.note, sort_order: row.sort_order, is_active: row.is_active,
  })
  dialogVisible.value = true
}

const amountOrNull = (value: string | number) => (String(value).trim() === '' ? null : Number(value))

const submit = async () => {
  if (!form.name.trim()) return ElMessage.warning('項目名を入力してください。')
  for (const [label, value] of [['標準価格', form.default_price], ['委託底価', form.floor_price]] as const) {
    if (String(value).trim() !== '' && (!Number.isFinite(Number(value)) || Number(value) < 0)) {
      return ElMessage.warning(`${label}は 0 以上の数字で入力してください。`)
    }
  }
  const payload: ServiceItemPayload = {
    category: form.category.trim(), name: form.name.trim(), default_price: amountOrNull(form.default_price),
    price_type: form.price_type, professional_type: form.professional_type, tax_category: form.tax_category,
    unit: form.unit.trim(), note: form.note, sort_order: Number(form.sort_order) || 0, is_active: form.is_active,
  }
  // 底価は権限者だけが送る（権限の無い人が送ると後端が拒否する）
  if (canSeeFloor.value) payload.floor_price = amountOrNull(form.floor_price)
  if (editing.value) payload.version = editing.value.updated_at
  saving.value = true
  try {
    await saveServiceItem(editing.value?.id ?? null, payload)
    ElMessage.success('サービス項目を保存しました。')
    dialogVisible.value = false
    await fetch()
  } catch (error) {
    // 409（他の人が先に保存）でも入力は残す
    ElMessage.error({ message: apiErrorText(error, 'サービス項目を保存できませんでした。'), duration: 6000 })
  } finally {
    saving.value = false
  }
}

const toggleActive = async (row: ServiceItem) => {
  const next = !row.is_active
  try {
    await saveServiceItem(row.id, { is_active: next, version: row.updated_at })
    ElMessage.success(next ? '有効にしました。' : '無効にしました（過去の帳票・案件の内容はそのまま残ります）。')
  } catch (error) {
    ElMessage.error({ message: apiErrorText(error, '変更できませんでした。'), duration: 6000 })
  }
  await fetch()
}

const remove = async (row: ServiceItem) => {
  try {
    await ElMessageBox.confirm(`「${row.name}」を削除しますか？（帳票・案件で使われていない項目だけ削除できます）`, '削除の確認',
      { confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteServiceItem(row.id)
    ElMessage.success('削除しました。')
  } catch (error) {
    ElMessage.error({ message: apiErrorText(error, '削除できませんでした。'), duration: 6000 })
  }
  await fetch()
}

const confirmingId = ref<number | null>(null)
const confirmPrice = async (row: ServiceItem) => {
  if (confirmingId.value !== null) return
  if (row.default_price === null) return ElMessage.warning('標準価格が未入力のため確定できません。先に価格を入力してください。')
  const floor = row.floor_price === null || row.floor_price === undefined ? '未入力' : formatYen(row.floor_price)
  try {
    await ElMessageBox.confirm(
      `「${row.name}」の価格を確定します。\n標準価格：${priceText(row)}\n委託底価（社内）：${floor}\n税区分：${row.tax_category_display}　単位：${row.unit || '-'}`,
      '価格の確定（1/2）', { confirmButtonText: '次へ', cancelButtonText: 'キャンセル', type: 'warning' })
    await ElMessageBox.confirm(
      '確定すると「暫定価格」の表示がなくなり、操作者と日時が記録されます。すでに作成済みの帳票・案件の内容は変わりません。本当に確定しますか？',
      '価格の確定（2/2）', { confirmButtonText: '確定する', cancelButtonText: 'キャンセル', type: 'warning' })
  } catch {
    return
  }
  confirmingId.value = row.id
  try {
    await confirmServiceItemPrice(row.id, row.updated_at)
    ElMessage.success(`「${row.name}」の価格を確定しました。`)
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    const message = status === 409
      ? '他の人がこの項目を先に変更しました。最新の内容を読み直しました。内容を確認してからもう一度確定してください。'
      : apiErrorText(error, '価格を確定できませんでした。')
    ElMessage.error({ message, duration: 6000 })
  } finally {
    confirmingId.value = null
  }
  await fetch()
}

const priceText = (row: ServiceItem) => (row.default_price === null ? '-' : `${formatYen(row.default_price)}（${row.price_type_display}）`)

onMounted(() => fetch(1))
</script>

<template>
  <section class="accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>サービス項目・料金</h1>
          <p>見積書・請求書の明細と新規受付で選ぶ項目と標準価格です。選んだ時点の内容が帳票・案件に記録され、後から変更しても過去の帳票は変わりません。</p>
        </div>
        <div class="accounting-toolbar">
          <el-button v-if="canManage" type="primary" @click="openCreate">新規登録</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />
    <el-alert v-if="canSeeFloor" type="warning" :closable="false" show-icon class="page-alert"
              title="委託底価は社内用です（外部専門家への基本費用）。顧客向けの PDF・一般職員の画面には表示されません。" />

    <el-card class="accounting-filter-card" shadow="never">
      <div class="accounting-filter-row">
        <el-select v-model="filters.active" class="accounting-filter-select" @change="fetch(1)">
          <el-option label="有効のみ" value="1" /><el-option label="無効のみ" value="0" /><el-option label="すべて" value="" />
        </el-select>
        <el-input v-model="filters.search" clearable placeholder="項目名・分類" class="accounting-filter-search" @keyup.enter="fetch(1)" />
        <div class="accounting-filter-actions">
          <el-button type="primary" @click="fetch(1)">検索</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="accounting-card" shadow="never">
      <el-table v-loading="loading" :data="rows" stripe empty-text="サービス項目がありません">
        <el-table-column prop="category" label="分類" width="120" />
        <el-table-column label="項目名" min-width="200">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="row.price_status === 'provisional'" size="small" type="warning">暫定価格</el-tag>
            <el-tag v-if="!row.is_active" size="small" type="info">無効</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="標準価格（対客）" width="170" align="right"><template #default="{ row }">{{ priceText(row) }}</template></el-table-column>
        <el-table-column v-if="canSeeFloor" label="委託底価（社内）" width="140" align="right">
          <template #default="{ row }">{{ row.floor_price === null || row.floor_price === undefined ? '-' : formatYen(row.floor_price) }}</template>
        </el-table-column>
        <el-table-column prop="professional_type_display" label="委託専門家" width="130" />
        <el-table-column prop="tax_category_display" label="税区分" width="80" />
        <el-table-column prop="unit" label="単位" width="70" />
        <el-table-column label="価格状態" width="170">
          <template #default="{ row }">
            <template v-if="row.price_status === 'confirmed'">
              <span>確定</span>
              <div v-if="row.price_confirmed_at" class="price-confirmed-meta">{{ formatDateTime(row.price_confirmed_at) }} {{ row.price_confirmed_by_name }}</div>
            </template>
            <el-tag v-else size="small" type="warning">暫定価格</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新" width="150"><template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template></el-table-column>
        <el-table-column v-if="canManage" label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">編集</el-button>
            <el-button v-if="canConfirmPrice && row.price_status === 'provisional'" text type="warning"
                       :loading="confirmingId === row.id" :disabled="confirmingId !== null && confirmingId !== row.id"
                       @click="confirmPrice(row)">価格を確定</el-button>
            <el-button text @click="toggleActive(row)">{{ row.is_active ? '無効にする' : '有効にする' }}</el-button>
            <el-button v-if="!row.is_used" text type="danger" @click="remove(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination layout="prev, pager, next" :current-page="page" :page-size="50" :total="total" @current-change="fetch" />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? 'サービス項目を編集' : 'サービス項目を登録'" width="640px"
               :close-on-click-modal="false" :close-on-press-escape="false">
      <el-alert v-if="editing?.price_status === 'confirmed'" type="warning" :closable="false" show-icon class="dialog-alert"
                title="確定済みの価格です。標準価格・税込／税抜・委託底価・税区分・単位を変更すると「暫定価格」に戻り、もう一度確定が必要です。" />
      <el-alert v-if="editing?.is_used" type="info" :closable="false" show-icon class="dialog-alert"
                title="この項目は帳票・案件で使われています。変更は今後の選択にだけ反映され、過去の帳票・案件の内容は変わりません。" />
      <el-form label-position="top" class="accounting-dialog-form">
        <el-form-item label="分類"><el-input v-model="form.category" placeholder="例：入管・税務・翻訳" /></el-form-item>
        <el-form-item label="項目名" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="標準価格（対客・参考）">
          <div class="price-row">
            <el-input v-model="form.default_price" inputmode="numeric" placeholder="未定なら空欄" />
            <el-select v-model="form.price_type" :disabled="form.tax_category === 'non_taxable'" style="width: 100px">
              <el-option label="税込" value="tax_included" /><el-option label="税抜" value="tax_excluded" />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item v-if="canSeeFloor" label="委託底価（社内）">
          <el-input v-model="form.floor_price" inputmode="numeric" placeholder="外部専門家への基本費用" />
        </el-form-item>
        <el-form-item label="委託専門家">
          <el-select v-model="form.professional_type" class="form-control">
            <el-option v-for="o in PROFESSIONAL_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="税区分">
          <el-select v-model="form.tax_category" class="form-control">
            <el-option label="10％" value="tax_10" /><el-option label="8％" value="tax_8" /><el-option label="非課税" value="non_taxable" />
          </el-select>
        </el-form-item>
        <el-form-item label="単位"><el-input v-model="form.unit" placeholder="件" /></el-form-item>
        <el-form-item label="並び順"><el-input-number v-model="form.sort_order" :min="0" /></el-form-item>
        <el-form-item label="社内メモ（PDF には表示されません）" class="accounting-dialog-full">
          <el-input v-model="form.note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状態"><el-switch v-model="form.is_active" active-text="有効" inactive-text="無効" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.price-confirmed-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.price-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
</style>

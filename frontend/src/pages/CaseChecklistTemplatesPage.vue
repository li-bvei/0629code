<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createCaseChecklistTemplate,
  createCaseChecklistTemplateItem,
  listCaseChecklistDeletionHistory,
  listCaseChecklistTemplateItems,
  listCaseChecklistTemplates,
  restoreCaseChecklistTemplate,
  restoreCaseChecklistTemplateItem,
  seedStandardCaseChecklistTemplates,
  softDeleteCaseChecklistTemplate,
  softDeleteCaseChecklistTemplateItem,
  updateCaseChecklistTemplate,
  updateCaseChecklistTemplateItem,
} from '../api/cases'
import type {
  CaseChecklistDeletionHistoryItem,
  CaseChecklistItemType,
  CaseChecklistTemplate,
  CaseChecklistTemplateItem,
  CaseChecklistTemplateItemPayload,
  CaseChecklistTemplatePayload,
} from '../types/api'
import { formatDateTime } from '../utils/date'

const loading = ref(false)
const templates = ref<CaseChecklistTemplate[]>([])
const selectedTemplateId = ref<number | null>(null)
const templateSearch = ref('')
const templateActiveFilter = ref<'true' | 'false' | ''>('true')
const templateDialogVisible = ref(false)
const templateSubmitting = ref(false)
const templateFormRef = ref<FormInstance>()
const editingTemplateId = ref<number | null>(null)
const itemDialogVisible = ref(false)
const itemSubmitting = ref(false)
const itemFormRef = ref<FormInstance>()
const editingItemId = ref<number | null>(null)
const templateItems = ref<CaseChecklistTemplateItem[]>([])
const demoSeedSubmitting = ref(false)
const deletionHistory = ref<CaseChecklistDeletionHistoryItem[]>([])
const deletionHistoryLoading = ref(false)

const presetCategories = [
  '本人資料',
  '会社資料',
  '会社設立資料',
  '勤務先資料',
  '学歴・職歴資料',
  '事業計画資料',
  '事務所資料',
  '資本金・資金資料',
  '税務資料',
  '税務・届出資料',
  '社会保険資料',
  '年金・保険資料',
  '給与・税務資料',
  '経営状況資料',
  '職業・収入資料',
  '身元保証人資料',
  '在留履歴資料',
  'ポイント計算資料',
  '年収・契約資料',
  '雇用条件資料',
  '申請準備',
  'その他',
]

const itemTypeOptions = [
  { label: '手続事項', value: 'task' },
  { label: '必要資料', value: 'document' },
  { label: '確認事項', value: 'confirmation' },
] as const

const templateForm = ref<CaseChecklistTemplatePayload>({
  name: '',
  description: '',
  is_active: true,
  sort_order: 0,
})

const itemForm = ref<CaseChecklistTemplateItemPayload>({
  template: 0,
  category: '',
  name: '',
  item_type: 'document',
  quantity: null,
  unit: '',
  is_required: true,
  description: '',
  sort_order: 0,
  is_active: true,
})

const templateRules: FormRules<CaseChecklistTemplatePayload> = {
  name: [{ required: true, message: 'テンプレート名を入力してください。', trigger: 'blur' }],
}

const itemRules: FormRules<CaseChecklistTemplateItemPayload> = {
  name: [{ required: true, message: '項目名を入力してください。', trigger: 'blur' }],
  item_type: [{ required: true, message: '項目タイプを選択してください。', trigger: 'change' }],
}

const selectedTemplate = computed(() => (
  templates.value.find((template) => template.id === selectedTemplateId.value) || null
))

const sortedItems = computed(() => (
  [...templateItems.value].sort((left, right) => {
    if ((left.sort_order || 0) !== (right.sort_order || 0)) {
      return (left.sort_order || 0) - (right.sort_order || 0)
    }
    return left.id - right.id
  })
))

const categoryOptions = computed(() => {
  const loadedValues = templates.value.flatMap((template) => (
    template.items?.map((item) => item.category).filter(Boolean) || []
  ))
  const currentValues = templateItems.value.map((item) => item.category).filter(Boolean)
  const values = [...loadedValues, ...currentValues]
  return [...new Set([...presetCategories, ...values])]
})

const itemNameOptions = computed(() => {
  const loadedValues = templates.value.flatMap((template) => (
    template.items?.map((item) => item.name).filter(Boolean) || []
  ))
  const currentValues = templateItems.value.map((item) => item.name).filter(Boolean)
  const values = [...loadedValues, ...currentValues]
  return [...new Set(values)].sort((left, right) => left.localeCompare(right, 'ja'))
})

const getItemTypeLabel = (type: CaseChecklistItemType) => (
  itemTypeOptions.find((option) => option.value === type)?.label || type
)

const fetchTemplates = async () => {
  loading.value = true
  try {
    const data = await listCaseChecklistTemplates({
      search: templateSearch.value || undefined,
      is_active: templateActiveFilter.value || undefined,
    })
    templates.value = data.results
    if (selectedTemplateId.value && !data.results.some((template) => template.id === selectedTemplateId.value)) {
      selectedTemplateId.value = null
      templateItems.value = []
    }
    if (!selectedTemplateId.value && data.results.length) {
      selectedTemplateId.value = data.results[0].id
    }
    if (selectedTemplateId.value) {
      await fetchTemplateItems(selectedTemplateId.value)
    }
  } catch {
    ElMessage.error('案件事項テンプレートの取得に失敗しました。')
  } finally {
    loading.value = false
  }
}

const fetchDeletionHistory = async () => {
  deletionHistoryLoading.value = true
  try {
    deletionHistory.value = await listCaseChecklistDeletionHistory()
  } catch {
    ElMessage.error('削除履歴の取得に失敗しました。')
  } finally {
    deletionHistoryLoading.value = false
  }
}

const fetchTemplateItems = async (templateId: number) => {
  const data = await listCaseChecklistTemplateItems({ template: templateId })
  templateItems.value = data.results
}

const selectTemplate = async (template: CaseChecklistTemplate) => {
  selectedTemplateId.value = template.id
  await fetchTemplateItems(template.id)
}

const resetTemplateForm = () => {
  editingTemplateId.value = null
  templateForm.value = {
    name: '',
    description: '',
    is_active: true,
    sort_order: (templates.value.reduce((max, item) => Math.max(max, item.sort_order || 0), 0) || 0) + 1,
  }
  templateFormRef.value?.clearValidate()
}

const openCreateTemplateDialog = () => {
  resetTemplateForm()
  templateDialogVisible.value = true
}

const openEditTemplateDialog = (template: CaseChecklistTemplate) => {
  editingTemplateId.value = template.id
  templateForm.value = {
    name: template.name,
    description: template.description,
    is_active: template.is_active,
    sort_order: template.sort_order,
  }
  templateFormRef.value?.clearValidate()
  templateDialogVisible.value = true
}

const submitTemplate = async () => {
  if (!templateFormRef.value) return
  const valid = await templateFormRef.value.validate().catch(() => false)
  if (!valid) return

  templateSubmitting.value = true
  try {
    if (editingTemplateId.value) {
      await updateCaseChecklistTemplate(editingTemplateId.value, templateForm.value)
      ElMessage.success('テンプレートを更新しました。')
    } else {
      const created = await createCaseChecklistTemplate(templateForm.value)
      selectedTemplateId.value = created.id
      ElMessage.success('テンプレートを追加しました。')
    }
    templateDialogVisible.value = false
    await fetchTemplates()
  } catch {
    ElMessage.error(editingTemplateId.value ? 'テンプレートの更新に失敗しました。' : 'テンプレートの追加に失敗しました。')
  } finally {
    templateSubmitting.value = false
  }
}

const setTemplateActive = async (template: CaseChecklistTemplate, isActive: boolean) => {
  if (!isActive) {
    try {
      await ElMessageBox.confirm(
        'このテンプレートを無効にしますか？\n既存案件に追加済みの項目には影響しません。',
        '無効化確認',
        { confirmButtonText: '無効化', cancelButtonText: 'キャンセル', type: 'warning' },
      )
    } catch {
      return
    }
  }

  try {
    await updateCaseChecklistTemplate(template.id, { is_active: isActive })
    ElMessage.success(isActive ? '有効にしました。' : '無効にしました。')
    await fetchTemplates()
  } catch {
    ElMessage.error('テンプレート状態の更新に失敗しました。')
  }
}

const handleTemplateActionCommand = (template: CaseChecklistTemplate, command: string) => {
  if (command === 'edit') {
    openEditTemplateDialog(template)
    return
  }
  if (command === 'deactivate') {
    setTemplateActive(template, false)
    return
  }
  if (command === 'activate') {
    setTemplateActive(template, true)
    return
  }
  if (command === 'delete') {
    deleteTemplate(template)
  }
}

const resetItemForm = () => {
  editingItemId.value = null
  itemForm.value = {
    template: selectedTemplateId.value || 0,
    category: '',
    name: '',
    item_type: 'document',
    quantity: null,
    unit: '',
    is_required: true,
    description: '',
    sort_order: (templateItems.value.filter((item) => !item.deleted_at).reduce((max, item) => Math.max(max, item.sort_order || 0), 0) || 0) + 1,
    is_active: true,
  }
  itemFormRef.value?.clearValidate()
}

const openCreateItemDialog = () => {
  if (!selectedTemplateId.value) {
    ElMessage.warning('先にテンプレートを選択してください。')
    return
  }
  resetItemForm()
  itemDialogVisible.value = true
}

const openEditItemDialog = (item: CaseChecklistTemplateItem) => {
  editingItemId.value = item.id
  itemForm.value = {
    template: item.template,
    category: item.category,
    name: item.name,
    item_type: item.item_type,
    quantity: item.quantity,
    unit: item.unit,
    is_required: item.is_required,
    description: item.description,
    sort_order: item.sort_order,
    is_active: item.is_active,
  }
  itemFormRef.value?.clearValidate()
  itemDialogVisible.value = true
}

const submitItem = async () => {
  if (!itemFormRef.value || !selectedTemplateId.value) return
  const valid = await itemFormRef.value.validate().catch(() => false)
  if (!valid) return

  itemSubmitting.value = true
  try {
    const payload = {
      ...itemForm.value,
      template: selectedTemplateId.value,
      quantity: itemForm.value.quantity || null,
    }
    if (editingItemId.value) {
      await updateCaseChecklistTemplateItem(editingItemId.value, payload)
      ElMessage.success('項目を更新しました。')
    } else {
      await createCaseChecklistTemplateItem(payload)
      ElMessage.success('項目を追加しました。')
    }
    itemDialogVisible.value = false
    await fetchTemplateItems(selectedTemplateId.value)
    await fetchTemplates()
  } catch {
    ElMessage.error(editingItemId.value ? '項目の更新に失敗しました。' : '項目の追加に失敗しました。')
  } finally {
    itemSubmitting.value = false
  }
}

const setItemActive = async (item: CaseChecklistTemplateItem, isActive: boolean) => {
  if (!isActive) {
    try {
      await ElMessageBox.confirm(
        'この項目を無効にしますか？\n既存案件に追加済みの項目には影響しません。',
        '無効化確認',
        { confirmButtonText: '無効化', cancelButtonText: 'キャンセル', type: 'warning' },
      )
    } catch {
      return
    }
  }

  try {
    await updateCaseChecklistTemplateItem(item.id, { is_active: isActive })
    ElMessage.success(isActive ? '有効にしました。' : '無効にしました。')
    if (selectedTemplateId.value) await fetchTemplateItems(selectedTemplateId.value)
  } catch {
    ElMessage.error('項目状態の更新に失敗しました。')
  }
}

const handleItemActionCommand = (item: CaseChecklistTemplateItem, command: string) => {
  if (command === 'edit') {
    openEditItemDialog(item)
    return
  }
  if (command === 'move-up') {
    moveItem(item, -1)
    return
  }
  if (command === 'move-down') {
    moveItem(item, 1)
    return
  }
  if (command === 'deactivate') {
    setItemActive(item, false)
    return
  }
  if (command === 'activate') {
    setItemActive(item, true)
    return
  }
  if (command === 'delete') {
    deleteItem(item)
  }
}

const moveItem = async (item: CaseChecklistTemplateItem, direction: -1 | 1) => {
  const currentIndex = sortedItems.value.findIndex((row) => row.id === item.id)
  const target = sortedItems.value[currentIndex + direction]
  if (!target) return
  try {
    await Promise.all([
      updateCaseChecklistTemplateItem(item.id, { sort_order: target.sort_order }),
      updateCaseChecklistTemplateItem(target.id, { sort_order: item.sort_order }),
    ])
    if (selectedTemplateId.value) await fetchTemplateItems(selectedTemplateId.value)
  } catch {
    ElMessage.error('並び順の更新に失敗しました。')
  }
}

const deleteTemplate = async (template: CaseChecklistTemplate) => {
  try {
    await ElMessageBox.confirm(
      'このテンプレートを削除しますか？\nテンプレート内の項目も削除履歴へ移動します。\n既存案件に追加済みの項目には影響しません。',
      '削除確認',
      { confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning' },
    )
    await softDeleteCaseChecklistTemplate(template.id)
    ElMessage.success('削除しました。')
    if (selectedTemplateId.value === template.id) {
      selectedTemplateId.value = null
      templateItems.value = []
    }
    await fetchTemplates()
    await fetchDeletionHistory()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('削除に失敗しました。')
    }
  }
}

const deleteItem = async (item: CaseChecklistTemplateItem) => {
  try {
    await ElMessageBox.confirm(
      'このテンプレート項目を削除しますか？\n既存案件に追加済みの項目には影響しません。',
      '削除確認',
      { confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning' },
    )
    await softDeleteCaseChecklistTemplateItem(item.id)
    ElMessage.success('削除しました。')
    if (selectedTemplateId.value) await fetchTemplateItems(selectedTemplateId.value)
    await fetchDeletionHistory()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('削除に失敗しました。')
    }
  }
}

const restoreDeletedItem = async (row: CaseChecklistDeletionHistoryItem) => {
  try {
    if (row.object_type === 'template') {
      await restoreCaseChecklistTemplate(row.id)
    } else {
      await restoreCaseChecklistTemplateItem(row.id)
    }
    ElMessage.success('復元しました。')
    await fetchTemplates()
    await fetchDeletionHistory()
    if (selectedTemplateId.value) await fetchTemplateItems(selectedTemplateId.value)
  } catch (error) {
    ElMessage.error('復元に失敗しました。所属テンプレートが削除されている場合は、先にテンプレートを復元してください。')
  }
}

const generateDemoData = async () => {
  try {
    await ElMessageBox.confirm(
      '標準の案件事項テンプレートを取り込みます。\n既存のテンプレートや案件データは削除されません。\n既に登録済みのテンプレートと項目は重複登録されません。',
      '標準テンプレート取込',
      {
        confirmButtonText: '取り込む',
        cancelButtonText: 'キャンセル',
        type: 'info',
      },
    )
  } catch {
    return
  }

  demoSeedSubmitting.value = true
  try {
    const result = await seedStandardCaseChecklistTemplates()
    selectedTemplateId.value = result.template_ids[0] || null
    await fetchTemplates()
    const skippedMessage = result.templates_skipped_deleted || result.template_items_skipped_deleted
      ? `、削除履歴内のためスキップ：テンプレート${result.templates_skipped_deleted}件・項目${result.template_items_skipped_deleted}件`
      : ''
    ElMessage.success(
      `${result.message} テンプレート新規：${result.templates_created}件、テンプレート更新：${result.templates_updated}件、`
      + `項目新規：${result.template_items_created}件、項目更新：${result.template_items_updated}件${skippedMessage}`,
    )
  } catch {
    ElMessage.error('標準テンプレートの取込に失敗しました。')
  } finally {
    demoSeedSubmitting.value = false
  }
}

onMounted(() => {
  fetchTemplates()
  fetchDeletionHistory()
})
</script>

<template>
  <section class="page-section">
    <div class="page-header page-header-row">
      <div>
        <h1>案件事項管理</h1>
        <p>案件ごとの手続事項、必要資料、確認事項のテンプレートを管理します。</p>
        <p class="page-note">標準の案件事項テンプレートを一括で取り込めます。</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="demoSeedSubmitting" @click="generateDemoData">標準テンプレート取込</el-button>
        <el-button type="primary" @click="openCreateTemplateDialog">新規テンプレート追加</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-input
          v-model="templateSearch"
          clearable
          placeholder="テンプレート名で検索"
          @keyup.enter="fetchTemplates"
          @clear="fetchTemplates"
        />
        <el-select v-model="templateActiveFilter" class="status-filter" @change="fetchTemplates">
          <el-option label="すべて" value="" />
          <el-option label="有効" value="true" />
          <el-option label="無効" value="false" />
        </el-select>
        <el-button type="primary" @click="fetchTemplates">検索</el-button>
      </div>
    </el-card>

    <div class="checklist-layout" v-loading="loading">
      <el-card shadow="never">
        <template #header>テンプレート一覧</template>
        <el-table :data="templates" stripe highlight-current-row row-key="id" @row-click="selectTemplate">
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column label="項目数" width="90">
            <template #default="{ row }">{{ row.item_count }}</template>
          </el-table-column>
          <el-table-column label="状態" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '有効' : '無効' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="更新日時" width="160">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" align="center">
            <template #default="{ row }">
              <el-dropdown trigger="click" @command="handleTemplateActionCommand(row, $event)">
                <el-button text type="primary" class="table-action-trigger" @click.stop>
                  操作
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">編集</el-dropdown-item>
                    <el-dropdown-item v-if="row.is_active" command="deactivate" divided>無効化</el-dropdown-item>
                    <el-dropdown-item v-else command="activate" divided>有効化</el-dropdown-item>
                    <el-dropdown-item command="delete" divided class="danger-item">削除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="!templates.length" class="empty-text">テンプレートがありません</p>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>{{ selectedTemplate?.name || 'テンプレート項目' }}</span>
            <el-button type="primary" :disabled="!selectedTemplateId" @click="openCreateItemDialog">項目追加</el-button>
          </div>
        </template>
        <el-table :data="sortedItems" stripe row-key="id">
          <el-table-column label="順番" width="70">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column prop="category" label="分類" min-width="110">
            <template #default="{ row }">{{ row.category || '-' }}</template>
          </el-table-column>
          <el-table-column prop="name" label="項目名" min-width="180" />
          <el-table-column label="タイプ" width="110">
            <template #default="{ row }">{{ getItemTypeLabel(row.item_type) }}</template>
          </el-table-column>
          <el-table-column label="数量" width="90">
            <template #default="{ row }">
              {{ row.quantity ? `${row.quantity}${row.unit || ''}` : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="必須" width="80">
            <template #default="{ row }">{{ row.is_required ? '必須' : '任意' }}</template>
          </el-table-column>
          <el-table-column label="状態" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '有効' : '無効' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" align="center">
            <template #default="{ row }">
              <el-dropdown trigger="click" @command="handleItemActionCommand(row, $event)">
                <el-button text type="primary" class="table-action-trigger">
                  操作
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">編集</el-dropdown-item>
                    <el-dropdown-item command="move-up">上へ</el-dropdown-item>
                    <el-dropdown-item command="move-down">下へ</el-dropdown-item>
                    <el-dropdown-item v-if="row.is_active" command="deactivate" divided>無効化</el-dropdown-item>
                    <el-dropdown-item v-else command="activate" divided>有効化</el-dropdown-item>
                    <el-dropdown-item command="delete" divided class="danger-item">削除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="selectedTemplateId && !templateItems.length" class="empty-text">項目がありません</p>
        <p v-if="!selectedTemplateId" class="empty-text">テンプレートを選択してください</p>
      </el-card>
    </div>

    <el-card shadow="never" class="deletion-history-card">
      <template #header>削除履歴</template>
      <el-table v-loading="deletionHistoryLoading" :data="deletionHistory" stripe row-key="id">
        <el-table-column label="種別" width="130">
          <template #default="{ row }">{{ row.object_type === 'template' ? 'テンプレート' : 'テンプレート項目' }}</template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column label="所属テンプレート" min-width="180">
          <template #default="{ row }">{{ row.template_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="削除日時" width="170">
          <template #default="{ row }">{{ formatDateTime(row.deleted_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" :disabled="!row.can_restore" @click="restoreDeletedItem(row)">復元</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!deletionHistory.length" class="empty-text">削除履歴がありません</p>
    </el-card>

    <el-dialog
      v-model="templateDialogVisible"
      :title="editingTemplateId ? 'テンプレート編集' : 'テンプレート追加'"
      width="560px"
      @closed="resetTemplateForm"
    >
      <el-form ref="templateFormRef" :model="templateForm" :rules="templateRules" label-position="top">
        <el-form-item label="テンプレート名" prop="name">
          <el-input v-model="templateForm.name" />
        </el-form-item>
        <el-form-item label="説明" prop="description">
          <el-input v-model="templateForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="表示順" prop="sort_order">
            <el-input-number v-model="templateForm.sort_order" :min="1" :step="1" class="form-control" />
          </el-form-item>
          <el-form-item label="状態" prop="is_active">
            <el-switch v-model="templateForm.is_active" active-text="有効" inactive-text="無効" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="templateSubmitting" @click="submitTemplate">
          {{ editingTemplateId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="itemDialogVisible"
      :title="editingItemId ? '項目編集' : '項目追加'"
      width="680px"
      @closed="resetItemForm"
    >
      <el-form ref="itemFormRef" :model="itemForm" :rules="itemRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="分類" prop="category">
            <el-select
              v-model="itemForm.category"
              allow-create
              clearable
              default-first-option
              filterable
              placeholder="選択または入力してください"
              class="form-control"
            >
              <el-option v-for="category in categoryOptions" :key="category" :label="category" :value="category" />
            </el-select>
          </el-form-item>
          <el-form-item label="項目タイプ" prop="item_type">
            <el-select v-model="itemForm.item_type" class="form-control">
              <el-option
                v-for="option in itemTypeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="項目名" prop="name">
          <el-select
            v-model="itemForm.name"
            allow-create
            clearable
            default-first-option
            filterable
            placeholder="選択または入力してください"
            class="form-control"
          >
            <el-option v-for="name in itemNameOptions" :key="name" :label="name" :value="name" />
          </el-select>
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="数量" prop="quantity">
            <el-input-number v-model="itemForm.quantity" :min="1" class="form-control" />
          </el-form-item>
          <el-form-item label="単位" prop="unit">
            <el-input v-model="itemForm.unit" placeholder="通、份、部など" />
          </el-form-item>
          <el-form-item label="表示順" prop="sort_order">
            <el-input-number v-model="itemForm.sort_order" :min="1" :step="1" class="form-control" />
          </el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="必須" prop="is_required">
            <el-switch v-model="itemForm.is_required" active-text="必須" inactive-text="任意" />
          </el-form-item>
          <el-form-item label="状態" prop="is_active">
            <el-switch v-model="itemForm.is_active" active-text="有効" inactive-text="無効" />
          </el-form-item>
        </div>
        <el-form-item label="説明" prop="description">
          <el-input v-model="itemForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="itemSubmitting" @click="submitItem">
          {{ editingItemId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.checklist-layout {
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(520px, 1.4fr);
  gap: 16px;
}

.deletion-history-card {
  margin-top: 16px;
}

.filter-row {
  display: flex;
  gap: 12px;
}

.status-filter {
  max-width: 140px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.page-note {
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>

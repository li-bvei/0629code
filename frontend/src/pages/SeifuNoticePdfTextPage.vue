<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createSeifuNoticeRecord,
  deleteSeifuNoticeRecord,
  downloadSeifuNoticeRecordPdf,
  getSeifuNoticePreview,
  getSeifuNoticeTemplateInfo,
  listSeifuNoticeRecords,
  updateSeifuNoticeRecord,
} from '../api/accounting'
import type {
  SeifuNoticePdfRecord,
  SeifuNoticeRecordPayload,
  SeifuNoticeTemplateInfo,
  SeifuNoticeTextItem,
} from '../types/accounting'
import './accounting/accounting.css'

type EditableTextItem = Required<Pick<SeifuNoticeTextItem, 'id'>> & SeifuNoticeTextItem

const DEFAULT_FONT_SIZE = 18
const DEFAULT_COLOR = '#383737'
const DEFAULT_FONT_FAMILY = 'adobe_heiti'
const DEFAULT_FONT_WEIGHT = 'normal'

const records = ref<SeifuNoticePdfRecord[]>([])
const total = ref(0)
const listLoading = ref(false)
const saving = ref(false)
const generatingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const duplicatingId = ref<number | null>(null)
const drawerVisible = ref(false)
const templateInfo = ref<SeifuNoticeTemplateInfo | null>(null)
const previewLoading = ref(false)
const currentPage = ref(1)
const previewUrl = ref('')
const imageRef = ref<HTMLImageElement>()
const previewWrapRef = ref<HTMLDivElement>()
const imageSize = ref({ width: 0, height: 0 })
const selectedId = ref<string | number | null>(null)
const editingId = ref<number | null>(null)

const query = reactive({
  page: 1,
  page_size: 20,
  search: '',
})

const form = reactive<SeifuNoticeRecordPayload>({
  title: '',
  status: 'draft',
  text_items: [],
  note: '',
})

const currentPageInfo = computed(() => templateInfo.value?.pages.find((page) => page.page === currentPage.value))
const pageCount = computed(() => templateInfo.value?.page_count || 0)
const currentItems = computed(() => form.text_items.filter((item) => item.page === currentPage.value) as EditableTextItem[])
const fontStatusType = computed(() => (templateInfo.value?.font_available ? 'success' : 'danger'))
const fontStatusText = computed(() => {
  if (!templateInfo.value) return '確認中'
  return templateInfo.value.font_available ? 'Adobe 黑体 Std 已检测' : templateInfo.value.font_error || '缺少字体文件：Adobe 黑体 Std'
})

const normalizeItem = (item: SeifuNoticeTextItem, index = 0): EditableTextItem => ({
  id: item.id || `text-${Date.now()}-${index}`,
  page: Number(item.page) || 1,
  text: item.text || '',
  x: Number(item.x) || 0,
  y: Number(item.y) || 0,
  font_size: Number(item.font_size) || DEFAULT_FONT_SIZE,
  font_weight: item.font_weight === 'bold' ? 'bold' : DEFAULT_FONT_WEIGHT,
  color: item.color || DEFAULT_COLOR,
  font_family: DEFAULT_FONT_FAMILY,
})

const revokePreviewUrl = () => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

const updateImageSize = () => {
  const image = imageRef.value
  if (!image) return
  imageSize.value = {
    width: image.clientWidth,
    height: image.clientHeight,
  }
}

const loadRecords = async () => {
  listLoading.value = true
  try {
    const data = await listSeifuNoticeRecords(query)
    records.value = data.results
    total.value = data.count
  } catch {
    ElMessage.error('记录列表の取得に失敗しました。')
  } finally {
    listLoading.value = false
  }
}

const loadTemplateInfo = async () => {
  previewLoading.value = true
  try {
    templateInfo.value = await getSeifuNoticeTemplateInfo()
    if (templateInfo.value.template_error) {
      ElMessage.error(templateInfo.value.template_error)
      return
    }
    currentPage.value = templateInfo.value.pages[0]?.page || 1
    await loadPreview()
  } catch {
    ElMessage.error('テンプレート情報の取得に失敗しました。')
  } finally {
    previewLoading.value = false
  }
}

const loadPreview = async () => {
  if (!templateInfo.value?.page_count) return
  previewLoading.value = true
  try {
    const blob = await getSeifuNoticePreview(currentPage.value)
    revokePreviewUrl()
    previewUrl.value = URL.createObjectURL(blob)
    await nextTick()
    updateImageSize()
  } catch {
    ElMessage.error('PDFプレビューの取得に失敗しました。')
  } finally {
    previewLoading.value = false
  }
}

const scale = computed(() => {
  const page = currentPageInfo.value
  if (!page || !imageSize.value.width || !imageSize.value.height) {
    return { x: 1, y: 1 }
  }
  return {
    x: imageSize.value.width / page.width,
    y: imageSize.value.height / page.height,
  }
})

const itemStyle = (item: EditableTextItem) => ({
  left: `${item.x * scale.value.x}px`,
  top: `${item.y * scale.value.y}px`,
  color: item.color || DEFAULT_COLOR,
  fontSize: `${(item.font_size || DEFAULT_FONT_SIZE) * scale.value.y}px`,
  fontWeight: item.font_weight === 'bold' ? 700 : 400,
})

const resetForm = () => {
  editingId.value = null
  form.title = ''
  form.status = 'draft'
  form.text_items = []
  form.note = ''
  selectedId.value = null
  currentPage.value = templateInfo.value?.pages[0]?.page || 1
}

const openCreate = async () => {
  resetForm()
  drawerVisible.value = true
  await nextTick()
  if (!templateInfo.value) {
    await loadTemplateInfo()
  } else {
    await loadPreview()
  }
}

const openEdit = async (record: SeifuNoticePdfRecord) => {
  editingId.value = record.id
  form.title = record.title
  form.status = record.status
  form.note = record.note || ''
  form.text_items = (record.text_items || []).map(normalizeItem)
  selectedId.value = null
  currentPage.value = templateInfo.value?.pages[0]?.page || 1
  drawerVisible.value = true
  await nextTick()
  if (!templateInfo.value) {
    await loadTemplateInfo()
  } else {
    await loadPreview()
  }
}

const addItemAtEvent = (event: MouseEvent) => {
  const page = currentPageInfo.value
  const wrap = previewWrapRef.value
  if (!page || !wrap || !imageSize.value.width || !imageSize.value.height) return
  const rect = wrap.getBoundingClientRect()
  const x = ((event.clientX - rect.left) / imageSize.value.width) * page.width
  const y = ((event.clientY - rect.top) / imageSize.value.height) * page.height
  const item: EditableTextItem = {
    id: `text-${Date.now()}`,
    page: currentPage.value,
    text: '',
    x: Math.round(x * 10) / 10,
    y: Math.round(y * 10) / 10,
    font_size: DEFAULT_FONT_SIZE,
    font_weight: DEFAULT_FONT_WEIGHT,
    color: DEFAULT_COLOR,
    font_family: DEFAULT_FONT_FAMILY,
  }
  form.text_items.push(item)
  selectedId.value = item.id
}

const removeItem = (id: string | number) => {
  form.text_items = form.text_items.filter((item) => item.id !== id)
  if (selectedId.value === id) selectedId.value = null
}

const movePage = async (direction: number) => {
  const nextPage = currentPage.value + direction
  if (nextPage < 1 || nextPage > pageCount.value) return
  currentPage.value = nextPage
  selectedId.value = null
  await loadPreview()
}

const startDrag = (event: PointerEvent, item: EditableTextItem) => {
  event.preventDefault()
  event.stopPropagation()
  selectedId.value = item.id
  const page = currentPageInfo.value
  const wrap = previewWrapRef.value
  if (!page || !wrap || !imageSize.value.width || !imageSize.value.height) return

  const onMove = (moveEvent: PointerEvent) => {
    const rect = wrap.getBoundingClientRect()
    const rawX = ((moveEvent.clientX - rect.left) / imageSize.value.width) * page.width
    const rawY = ((moveEvent.clientY - rect.top) / imageSize.value.height) * page.height
    item.x = Math.round(Math.min(Math.max(rawX, 0), page.width) * 10) / 10
    item.y = Math.round(Math.min(Math.max(rawY, 0), page.height) * 10) / 10
  }
  const onUp = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

const extractFilename = (contentDisposition?: string) => {
  if (!contentDisposition) return '清風合格通知書.pdf'
  const encoded = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
  if (encoded?.[1]) return decodeURIComponent(encoded[1])
  const plain = contentDisposition.match(/filename="?([^";]+)"?/)
  return plain?.[1] || '清風合格通知書.pdf'
}

const downloadBlob = (blob: Blob, contentDisposition?: string) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = extractFilename(contentDisposition)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const buildPayload = (): SeifuNoticeRecordPayload => ({
  title: form.title.trim(),
  status: form.status,
  note: form.note || '',
  text_items: form.text_items.map((item) => ({
    id: item.id,
    page: item.page,
    text: item.text || '',
    x: Number(item.x) || 0,
    y: Number(item.y) || 0,
    font_size: Number(item.font_size) || DEFAULT_FONT_SIZE,
    font_weight: item.font_weight === 'bold' ? 'bold' : DEFAULT_FONT_WEIGHT,
    color: item.color || DEFAULT_COLOR,
    font_family: DEFAULT_FONT_FAMILY,
  })),
})

const saveRecord = async () => {
  if (!form.title.trim()) {
    ElMessage.error('记录名称を入力してください。')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateSeifuNoticeRecord(editingId.value, buildPayload())
    } else {
      const created = await createSeifuNoticeRecord(buildPayload())
      editingId.value = created.id
    }
    ElMessage.success('保存しました。')
    await loadRecords()
  } catch {
    ElMessage.error('保存に失敗しました。')
  } finally {
    saving.value = false
  }
}

const generateRecordPdf = async (record: SeifuNoticePdfRecord) => {
  if (!templateInfo.value) {
    await loadTemplateInfo()
  }
  if (!templateInfo.value?.font_available) {
    ElMessage.error(templateInfo.value?.font_error || '缺少字体文件：Adobe 黑体 Std')
    return
  }
  generatingId.value = record.id
  try {
    const { blob, contentDisposition } = await downloadSeifuNoticeRecordPdf(record.id)
    downloadBlob(blob, contentDisposition)
  } catch {
    ElMessage.error('PDF生成に失敗しました。')
  } finally {
    generatingId.value = null
  }
}

const duplicateRecord = async (record: SeifuNoticePdfRecord) => {
  duplicatingId.value = record.id
  try {
    await createSeifuNoticeRecord({
      title: `${record.title} - コピー`,
      status: 'draft',
      note: record.note || '',
      text_items: (record.text_items || []).map((item, index) => ({
        ...normalizeItem(item, index),
        id: `text-${Date.now()}-${index}`,
      })),
    })
    ElMessage.success('コピーしました。')
    await loadRecords()
  } catch {
    ElMessage.error('コピーに失敗しました。')
  } finally {
    duplicatingId.value = null
  }
}

const deleteRecord = async (record: SeifuNoticePdfRecord) => {
  try {
    await ElMessageBox.confirm(`「${record.title}」を削除しますか？`, '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
  } catch {
    return
  }
  deletingId.value = record.id
  try {
    await deleteSeifuNoticeRecord(record.id)
    ElMessage.success('削除しました。')
    await loadRecords()
  } catch {
    ElMessage.error('削除に失敗しました。')
  } finally {
    deletingId.value = null
  }
}

const handleSearch = () => {
  query.page = 1
  loadRecords()
}

const formatDateTime = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

onMounted(() => {
  loadRecords()
  loadTemplateInfo()
  window.addEventListener('resize', updateImageSize)
})

onBeforeUnmount(() => {
  revokePreviewUrl()
  window.removeEventListener('resize', updateImageSize)
})
</script>

<template>
  <section class="accounting-page seifu-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>清風合格通知書</h1>
          <p>文字位置とスタイルを記録として保存し、同じ配置で PDF を生成できます。</p>
        </div>
        <div class="accounting-toolbar">
          <el-tag :type="fontStatusType">{{ fontStatusText }}</el-tag>
          <el-button type="primary" @click="openCreate">新建</el-button>
        </div>
      </div>
    </div>

    <el-card class="accounting-card" shadow="never">
      <div class="seifu-list-toolbar">
        <el-input
          v-model="query.search"
          class="seifu-search"
          clearable
          placeholder="记录名称 / 备注"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        />
        <el-button @click="handleSearch">検索</el-button>
      </div>

      <el-table v-loading="listLoading" :data="records" row-key="id">
        <el-table-column prop="title" label="记录名称" min-width="220" />
        <el-table-column prop="text_count" label="文字数量" width="110" align="center" />
        <el-table-column label="更新时间" width="190">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button text type="primary" class="table-action-trigger">
                操作
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openEdit(row)">编辑</el-dropdown-item>
                  <el-dropdown-item :disabled="duplicatingId === row.id" @click="duplicateRecord(row)">复制</el-dropdown-item>
                  <el-dropdown-item :disabled="generatingId === row.id" @click="generateRecordPdf(row)">PDF生成</el-dropdown-item>
                  <el-dropdown-item divided class="danger-item" :disabled="deletingId === row.id" @click="deleteRecord(row)">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div class="seifu-pagination">
        <el-pagination
          v-model:current-page="query.page"
          :page-size="query.page_size"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="loadRecords"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawerVisible" :title="editingId ? '编辑清風合格通知書记录' : '新建清風合格通知書记录'" size="88%">
      <div class="seifu-drawer">
        <div class="seifu-form-bar">
          <el-form label-position="top">
            <el-row :gutter="12">
              <el-col :xs="24" :md="10">
                <el-form-item label="记录名称">
                  <el-input v-model="form.title" placeholder="例：王小明 合格通知書" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="5">
                <el-form-item label="状态">
                  <el-select v-model="form.status">
                    <el-option label="draft" value="draft" />
                    <el-option label="completed" value="completed" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="9">
                <el-form-item label="备注">
                  <el-input v-model="form.note" placeholder="备注" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>

        <div class="seifu-pager">
          <el-button :disabled="currentPage <= 1" @click="movePage(-1)">上一页</el-button>
          <strong>{{ currentPage }} / {{ pageCount || '-' }}</strong>
          <el-button :disabled="currentPage >= pageCount" @click="movePage(1)">下一页</el-button>
        </div>

        <div class="seifu-workspace">
          <div class="seifu-preview-panel" v-loading="previewLoading">
            <div v-if="previewUrl" ref="previewWrapRef" class="seifu-preview-wrap" @click="addItemAtEvent">
              <img ref="imageRef" :src="previewUrl" alt="清風合格通知書 PDF preview" @load="updateImageSize" />
              <button
                v-for="item in currentItems"
                :key="item.id"
                class="seifu-text-item"
                :class="{ selected: selectedId === item.id }"
                :style="itemStyle(item)"
                type="button"
                @click.stop="selectedId = item.id"
                @pointerdown="startDrag($event, item)"
              >
                {{ item.text || '文字' }}
              </button>
            </div>
            <el-empty v-else description="プレビューを読み込めません" />
          </div>

          <aside class="seifu-item-panel">
            <div class="seifu-panel-title">追加文字</div>
            <el-empty v-if="!form.text_items.length" description="PDF をクリックして文字を追加" />
            <div v-for="item in form.text_items" :key="item.id" class="seifu-editor-item">
              <div class="seifu-editor-header">
                <strong>文字 {{ item.id }}</strong>
                <el-button text type="danger" @click="removeItem(item.id as string | number)">削除</el-button>
              </div>
              <el-input v-model="item.text" placeholder="追加する文字" />
              <div class="seifu-editor-grid">
                <el-input-number v-model="item.page" :min="1" :max="pageCount || 1" size="small" controls-position="right" />
                <el-input-number v-model="item.x" :min="0" :precision="1" size="small" controls-position="right" />
                <el-input-number v-model="item.y" :min="0" :precision="1" size="small" controls-position="right" />
              </div>
              <div class="seifu-editor-labels">
                <span>page</span>
                <span>x</span>
                <span>y</span>
              </div>
              <div class="seifu-style-grid">
                <el-input-number
                  v-model="item.font_size"
                  :min="6"
                  :max="72"
                  size="small"
                  controls-position="right"
                />
                <el-select v-model="item.font_weight" size="small">
                  <el-option label="normal" value="normal" />
                  <el-option label="bold" value="bold" />
                </el-select>
                <el-color-picker v-model="item.color" size="small" />
                <el-select v-model="item.font_family" size="small">
                  <el-option label="Adobe 黑体 Std" value="adobe_heiti" />
                </el-select>
              </div>
              <div class="seifu-editor-labels seifu-style-labels">
                <span>size</span>
                <span>weight</span>
                <span>color</span>
                <span>font</span>
              </div>
            </div>
          </aside>
        </div>

        <div class="seifu-drawer-footer">
          <el-button @click="drawerVisible = false">关闭</el-button>
          <el-button type="primary" :loading="saving" @click="saveRecord">保存</el-button>
        </div>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.seifu-page {
  --seifu-text: #383737;
}

.seifu-list-toolbar {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.seifu-search {
  width: min(320px, 100%);
}

.seifu-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.seifu-drawer {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.seifu-form-bar {
  padding-right: 12px;
}

.seifu-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-bottom: 16px;
}

.seifu-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  gap: 18px;
  align-items: start;
}

.seifu-preview-panel {
  overflow: auto;
  max-height: calc(100vh - 270px);
  padding: 16px;
  background: #f6f8fb;
  border: 1px solid rgba(120, 150, 180, 0.2);
}

.seifu-preview-wrap {
  position: relative;
  width: fit-content;
  margin: 0 auto;
  background: #fff;
  box-shadow: 0 8px 24px rgba(43, 62, 90, 0.14);
  cursor: crosshair;
}

.seifu-preview-wrap img {
  display: block;
  max-width: min(100%, 920px);
  height: auto;
  user-select: none;
}

.seifu-text-item {
  position: absolute;
  padding: 1px 4px;
  font-family: sans-serif;
  line-height: 1.1;
  background: rgba(255, 255, 255, 0.52);
  border: 1px dashed rgba(56, 55, 55, 0.45);
  cursor: move;
  transform: translateY(-100%);
  white-space: pre;
}

.seifu-text-item.selected {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.18);
}

.seifu-item-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 270px);
  overflow: auto;
  padding-right: 8px;
}

.seifu-panel-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--sunrise-text);
}

.seifu-editor-item {
  padding: 12px;
  border: 1px solid rgba(120, 150, 180, 0.2);
  border-radius: 8px;
  background: #fff;
}

.seifu-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.seifu-editor-grid,
.seifu-editor-labels {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}

.seifu-style-grid,
.seifu-style-labels {
  display: grid;
  grid-template-columns: 76px 96px 54px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}

.seifu-editor-labels {
  margin-top: 4px;
  color: var(--sunrise-muted);
  font-size: 12px;
  text-align: center;
}

.seifu-drawer-footer {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 0 0;
  margin-top: 18px;
  background: #fff;
}

@media (max-width: 980px) {
  .seifu-workspace {
    grid-template-columns: 1fr;
  }

  .seifu-preview-panel,
  .seifu-item-panel {
    max-height: none;
  }
}
</style>

// 帳票一覧ページ共通の読み込み・PDF・削除・「元の帳票から作成」（状態の扱いは各帳票の後端 Workflow）。
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createDocumentFrom, deleteBusinessDocument, downloadBusinessDocumentPdf } from '../../api/accounting'
import type { AccountingListParams, AccountingPaginatedResponse, BusinessDocumentEndpoint } from '../../types/accounting'
import { apiErrorText, extractFilename, saveBlob } from './voucherErrors'

export const useDocumentList = <T extends { id: number }>(
  endpoint: BusinessDocumentEndpoint,
  label: string,
  lister: (params: AccountingListParams) => Promise<AccountingPaginatedResponse<T>>,
) => {
  const route = useRoute()
  const router = useRouter()
  const rows = ref<T[]>([]) as { value: T[] }
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const errorMessage = ref('')
  const filters = reactive({
    status: '',
    keyword: typeof route.query.keyword === 'string' ? route.query.keyword : '',
    issue_date_from: '',
    issue_date_to: '',
  })

  const fetch = async (target = page.value) => {
    loading.value = true
    errorMessage.value = ''
    try {
      const data = await lister({ page: target, ...filters })
      rows.value = data.results
      total.value = data.count
      page.value = target
    } catch (error) {
      errorMessage.value = apiErrorText(error, 'データの取得に失敗しました。')
    } finally {
      loading.value = false
    }
  }

  const resetFilters = () => {
    Object.assign(filters, { status: '', keyword: '', issue_date_from: '', issue_date_to: '' })
    fetch(1)
  }

  const downloadPdf = async (id: number, withSeal: boolean) => {
    try {
      const { blob, contentDisposition } = await downloadBusinessDocumentPdf(endpoint, id, withSeal)
      saveBlob(blob, extractFilename(contentDisposition, `${label}.pdf`))
    } catch (error) {
      ElMessage.error(apiErrorText(error, 'PDFのダウンロードに失敗しました。'))
    }
  }

  const remove = async (id: number, number: string) => {
    try {
      await ElMessageBox.confirm(`${label}「${number}」を削除します。よろしいですか？`, '削除確認', {
        confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning',
      })
    } catch {
      return
    }
    try {
      await deleteBusinessDocument(endpoint, id)
      ElMessage.success('削除しました。')
      await fetch()
    } catch (error) {
      ElMessage.error(apiErrorText(error, '削除できませんでした。'))
    }
  }

  // 元の帳票の内容を写した下書きを作り、作成先の一覧へ移動する（元の帳票の状態は変わらない）
  const createFrom = async (id: number, target: 'create-contract' | 'create-invoice' | 'create-receipt') => {
    const targetLabel = { 'create-contract': '契約書', 'create-invoice': '請求書', 'create-receipt': '領収書' }[target]
    try {
      await ElMessageBox.confirm(`この${label}の宛先・明細・関連案件を写して${targetLabel}の下書きを作成します。`, `${targetLabel}を作成`, {
        confirmButtonText: '作成', cancelButtonText: 'キャンセル',
      })
    } catch {
      return
    }
    try {
      const created = await createDocumentFrom(endpoint, id, target)
      ElMessage.success(`${targetLabel}の下書きを作成しました。`)
      const number = created.contract_number || created.voucher_number || ''
      const path = target === 'create-contract' ? '/vouchers/contracts' : '/vouchers/invoices'
      if (route.path === path) await fetch(1)
      else await router.push({ path, query: number ? { keyword: number } : {} })
    } catch (error) {
      ElMessage.error(apiErrorText(error, `${targetLabel}を作成できませんでした。`))
    }
  }

  return { rows, total, page, loading, errorMessage, filters, fetch, resetFilters, downloadPdf, remove, createFrom }
}

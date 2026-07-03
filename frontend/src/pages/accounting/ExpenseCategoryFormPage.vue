<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  createAccountingExpenseCategory,
  getAccountingExpenseCategory,
  updateAccountingExpenseCategory,
} from '../../api/accounting'
import type { ExpenseCategoryPayload } from '../../types/accounting'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)
const categoryId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => Boolean(categoryId.value))
const form = ref<ExpenseCategoryPayload>({
  name: '',
  is_active: true,
  sort_order: 0,
})

const rules: FormRules<ExpenseCategoryPayload> = {
  name: [{ required: true, message: 'カテゴリ名を入力してください。', trigger: 'blur' }],
}

const fetchCategory = async () => {
  if (!categoryId.value) return
  const category = await getAccountingExpenseCategory(categoryId.value)
  form.value = {
    name: category.name,
    is_active: category.is_active,
    sort_order: category.sort_order,
  }
}

const submit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (categoryId.value) {
      await updateAccountingExpenseCategory(categoryId.value, form.value)
      ElMessage.success('支出カテゴリを更新しました。')
    } else {
      await createAccountingExpenseCategory(form.value)
      ElMessage.success('支出カテゴリを作成しました。')
    }
    router.push('/accounting/expense-categories')
  } catch {
    ElMessage.error(isEdit.value ? '支出カテゴリの更新に失敗しました。' : '支出カテゴリの作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchCategory()
  } catch {
    ElMessage.error('データの取得に失敗しました。')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>{{ isEdit ? '支出カテゴリ編集' : '新規支出カテゴリ' }}</h1>
      <el-button @click="router.push('/accounting/expense-categories')">戻る</el-button>
    </div>

    <el-card v-loading="loading" shadow="never">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="カテゴリ名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="並び順" prop="sort_order">
          <el-input v-model.number="form.sort_order" inputmode="numeric" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.is_active">有効</el-checkbox>
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <el-button @click="router.push('/accounting/expense-categories')">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-card>
  </section>
</template>

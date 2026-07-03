<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { createAccountingProject, getAccountingProject, updateAccountingProject } from '../../api/accounting'
import type { AccountingProjectPayload } from '../../types/accounting'
import './accounting.css'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)
const projectId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => Boolean(projectId.value))
const form = ref<AccountingProjectPayload>({
  name: '',
  description: '',
  start_date: null,
  end_date: null,
  is_active: true,
  note: '',
})

const rules: FormRules<AccountingProjectPayload> = {
  name: [{ required: true, message: '项目名称を入力してください。', trigger: 'blur' }],
}

const fetchProject = async () => {
  if (!projectId.value) return
  const project = await getAccountingProject(projectId.value)
  form.value = {
    name: project.name,
    description: project.description || '',
    start_date: project.start_date || null,
    end_date: project.end_date || null,
    is_active: project.is_active,
    note: project.note || '',
  }
}

const submit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (projectId.value) {
      await updateAccountingProject(projectId.value, form.value)
      ElMessage.success('プロジェクト収支表を更新しました。')
      router.push(`/accounting/projects/${projectId.value}`)
    } else {
      const project = await createAccountingProject(form.value)
      ElMessage.success('プロジェクト収支表を作成しました。')
      router.push(`/accounting/projects/${project.id}`)
    }
  } catch {
    ElMessage.error(isEdit.value ? 'プロジェクト収支表の更新に失敗しました。' : 'プロジェクト収支表の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchProject()
  } catch {
    ElMessage.error('データの取得に失敗しました。')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>{{ isEdit ? 'プロジェクト収支表編集' : '新規プロジェクト収支表' }}</h1>
          <p>プロジェクト単位で収入と支出を管理します。</p>
        </div>
        <div class="accounting-toolbar">
          <el-button @click="router.push('/accounting/projects')">一覧へ戻る</el-button>
        </div>
      </div>
    </div>

    <el-card v-loading="loading" shadow="never" class="accounting-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="项目名称" prop="name">
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.is_active">是否启用</el-checkbox>
          </el-form-item>
          <el-form-item label="开始日期" prop="start_date">
            <el-date-picker
              v-model="form.start_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="结束日期" prop="end_date">
            <el-date-picker
              v-model="form.end_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="项目说明" prop="description" class="accounting-dialog-full">
            <el-input v-model="form.description" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="备注" prop="note" class="accounting-dialog-full">
            <el-input v-model="form.note" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>

      <div class="form-actions">
        <el-button @click="router.push('/accounting/projects')">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-card>
  </section>
</template>

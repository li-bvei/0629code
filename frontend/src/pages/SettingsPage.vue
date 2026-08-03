<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  changeOwnPassword,
  createUser,
  listUsers,
  resetUserPassword,
  setUserActive,
} from '../api/users'
import { useAuthStore } from '../stores/auth'
import type { SystemUser, SystemUserCreatePayload } from '../types/api'
import { formatDateTime } from '../utils/date'

const auth = useAuthStore()
const isSuperUser = computed(() => Boolean(auth.user?.is_superuser))

// --- パスワードを変更（本人） ---
const passwordFormRef = ref<FormInstance>()
const passwordSubmitting = ref(false)
const passwordForm = ref({
  old_password: '',
  new_password: '',
  new_password_confirm: '',
})

const passwordRules: FormRules = {
  old_password: [{ required: true, message: '現在のパスワードを入力してください。', trigger: 'blur' }],
  new_password: [
    { required: true, message: '新しいパスワードを入力してください。', trigger: 'blur' },
    { min: 8, message: '8文字以上で入力してください。', trigger: 'blur' },
  ],
  new_password_confirm: [
    { required: true, message: '確認のため再入力してください。', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== passwordForm.value.new_password) {
          callback(new Error('新しいパスワードと一致しません。'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

const submitPasswordChange = async () => {
  if (!passwordFormRef.value) return
  const valid = await passwordFormRef.value.validate().catch(() => false)
  if (!valid) return

  passwordSubmitting.value = true
  try {
    await changeOwnPassword(passwordForm.value.old_password, passwordForm.value.new_password)
    ElMessage.success('パスワードを変更しました。')
    passwordForm.value = { old_password: '', new_password: '', new_password_confirm: '' }
    passwordFormRef.value.clearValidate()
  } catch (error: any) {
    const detail =
      error?.response?.data?.old_password?.[0] ||
      error?.response?.data?.new_password?.[0] ||
      'パスワードの変更に失敗しました。'
    ElMessage.error(detail)
  } finally {
    passwordSubmitting.value = false
  }
}

// --- アカウント管理（root専用） ---
const usersLoading = ref(false)
const users = ref<SystemUser[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

const fetchUsers = async (page = currentPage.value) => {
  if (!isSuperUser.value) return
  usersLoading.value = true
  try {
    const data = await listUsers({ page })
    users.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    ElMessage.error('アカウント一覧の取得に失敗しました。')
  } finally {
    usersLoading.value = false
  }
}

const createDialogVisible = ref(false)
const createFormRef = ref<FormInstance>()
const createSubmitting = ref(false)
const createForm = ref<SystemUserCreatePayload>({
  username: '',
  password: '',
  first_name: '',
  last_name: '',
})

const createRules: FormRules = {
  username: [{ required: true, message: 'ユーザー名を入力してください。', trigger: 'blur' }],
  password: [
    { required: true, message: '初期パスワードを入力してください。', trigger: 'blur' },
    { min: 8, message: '8文字以上で入力してください。', trigger: 'blur' },
  ],
}

const resetCreateForm = () => {
  createForm.value = { username: '', password: '', first_name: '', last_name: '' }
  createFormRef.value?.clearValidate()
}

const openCreateDialog = () => {
  resetCreateForm()
  createDialogVisible.value = true
}

const submitCreateUser = async () => {
  if (!createFormRef.value) return
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid) return

  createSubmitting.value = true
  try {
    await createUser(createForm.value)
    ElMessage.success('アカウントを追加しました。')
    createDialogVisible.value = false
    await fetchUsers(1)
  } catch (error: any) {
    const detail =
      error?.response?.data?.username?.[0] ||
      error?.response?.data?.password?.[0] ||
      'アカウントの追加に失敗しました。'
    ElMessage.error(detail)
  } finally {
    createSubmitting.value = false
  }
}

const toggleUserActive = async (user: SystemUser) => {
  try {
    await setUserActive(user.id, !user.is_active)
    ElMessage.success(user.is_active ? 'アカウントを無効にしました。' : 'アカウントを有効にしました。')
    await fetchUsers(currentPage.value)
  } catch {
    ElMessage.error('有効状態の更新に失敗しました。')
  }
}

const confirmResetPassword = async (user: SystemUser) => {
  try {
    const { value } = await ElMessageBox.prompt(
      `「${user.username}」の新しいパスワードを入力してください。`,
      'パスワードを再設定',
      {
        confirmButtonText: '再設定',
        cancelButtonText: 'キャンセル',
        inputPattern: /.{8,}/,
        inputErrorMessage: '8文字以上で入力してください。',
      },
    )
    await resetUserPassword(user.id, value)
    ElMessage.success('パスワードをリセットしました。')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('パスワードのリセットに失敗しました。')
    }
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>設定</h1>
    </div>

    <el-card shadow="never" class="settings-card">
      <template #header>パスワードを変更</template>
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-position="top"
        class="password-form"
      >
        <el-form-item label="現在のパスワード" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新しいパスワード" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新しいパスワード（確認）" prop="new_password_confirm">
          <el-input v-model="passwordForm.new_password_confirm" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="passwordSubmitting" @click="submitPasswordChange">
            変更する
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="isSuperUser" shadow="never" class="settings-card">
      <template #header>
        <div class="card-header-row">
          <span>アカウント管理</span>
          <el-button type="primary" size="small" @click="openCreateDialog">新規アカウント追加</el-button>
        </div>
      </template>

      <el-table v-loading="usersLoading" :data="users" stripe>
        <el-table-column prop="username" label="ユーザー名" min-width="140" />
        <el-table-column label="氏名" min-width="160">
          <template #default="{ row }">{{ `${row.last_name}${row.first_name}` || '-' }}</template>
        </el-table-column>
        <el-table-column label="権限" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_superuser" type="danger">root</el-tag>
            <el-tag v-else type="info">一般</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="有効状態" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '有効' : '無効' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最終ログイン" min-width="170">
          <template #default="{ row }">{{ row.last_login ? formatDateTime(row.last_login) : '-' }}</template>
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
                  <el-dropdown-item @click="confirmResetPassword(row)">パスワードを再設定</el-dropdown-item>
                  <el-dropdown-item divided @click="toggleUserActive(row)">
                    {{ row.is_active ? '無効化' : '有効化' }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchUsers"
        />
      </div>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新規アカウント追加" width="480px" @closed="resetCreateForm">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="ユーザー名" prop="username">
          <el-input v-model="createForm.username" />
        </el-form-item>
        <el-form-item label="姓" prop="last_name">
          <el-input v-model="createForm.last_name" />
        </el-form-item>
        <el-form-item label="名" prop="first_name">
          <el-input v-model="createForm.first_name" />
        </el-form-item>
        <el-form-item label="初期パスワード" prop="password">
          <el-input v-model="createForm.password" type="password" show-password />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreateUser">追加</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.settings-card {
  margin-bottom: 20px;
}

.password-form {
  max-width: 420px;
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>

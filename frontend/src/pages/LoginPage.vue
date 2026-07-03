<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: 'ユーザー名を入力してください', trigger: 'blur' }],
  password: [{ required: true, message: 'パスワードを入力してください', trigger: 'blur' }],
}

const submit = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true

  try {
    await auth.login(form.username, form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    router.replace(redirect)
  } catch {
    ElMessage.error('ユーザー名またはパスワードが正しくありません')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-brand">
        <div class="login-brand-mark">S</div>
        <div>
          <h1>SUNRISE</h1>
          <p>バックオフィス管理システム</p>
        </div>
      </div>

      <el-card class="login-card">
        <template #header>
          <div class="login-card-title">ログイン</div>
        </template>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
          <el-form-item label="ユーザー名" prop="username">
            <el-input v-model="form.username" autocomplete="username" />
          </el-form-item>

          <el-form-item label="パスワード" prop="password">
            <el-input v-model="form.password" type="password" autocomplete="current-password" show-password />
          </el-form-item>

          <el-button class="login-submit" type="primary" :loading="submitting" @click="submit">
            ログイン
          </el-button>
        </el-form>
      </el-card>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(170, 212, 244, 0.32), rgba(226, 197, 221, 0.28)),
    var(--sunrise-bg);
}

.login-panel {
  width: min(100%, 420px);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
}

.login-brand-mark {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 10px;
  color: var(--sunrise-text);
  background: linear-gradient(135deg, var(--sunrise-blue), var(--sunrise-pink));
  font-size: 20px;
  font-weight: 700;
}

.login-brand h1 {
  margin: 0;
  color: var(--sunrise-text);
  font-size: 26px;
  letter-spacing: 0;
}

.login-brand p {
  margin: 2px 0 0;
  color: var(--sunrise-muted);
  font-size: 13px;
}

.login-card-title {
  color: var(--sunrise-text);
  font-weight: 700;
}

.login-submit {
  width: 100%;
  margin-top: 6px;
}
</style>

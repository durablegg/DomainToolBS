<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>DomainToolBS</h2>
      <el-alert
        v-if="mode === 'init'"
        type="info"
        :closable="false"
        title="首次使用：创建超级管理员账号"
        style="margin-bottom: 12px"
      />
      <el-form :model="form" @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item v-if="mode === 'init'">
          <el-input v-model="form.display_name" placeholder="显示名称（可选）" :prefix-icon="Edit" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="密码"
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">
          {{ mode === 'init' ? '创建并进入' : '登录' }}
        </el-button>
      </el-form>
      <div class="switch">
        <el-link type="primary" @click="mode = mode === 'init' ? 'login' : 'init'">
          {{ mode === 'init' ? '已有账号？去登录' : '首次使用？初始化平台' }}
        </el-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Edit } from '@element-plus/icons-vue'
import { login, bootstrap } from '@/api/auth'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()
const mode = ref<'login' | 'init'>('login')
const loading = ref(false)
const form = reactive({ username: '', password: '', display_name: '' })

async function onSubmit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    if (mode.value === 'init') {
      await bootstrap({ username: form.username, password: form.password, display_name: form.display_name })
      ElMessage.success('超级管理员已创建')
    }
    const resp = await login({ username: form.username, password: form.password })
    userStore.setToken(resp.access_token)
    await userStore.fetchMe()
    router.replace('/')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '用户名或密码错误')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e3a8a, #065f46);
}
.login-card {
  width: 360px;
}
.login-card h2 {
  text-align: center;
  margin: 0 0 16px;
  color: #1e3a8a;
}
.switch {
  text-align: right;
  margin-top: 8px;
}
</style>

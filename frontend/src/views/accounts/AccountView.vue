<template>
  <div>
    <el-card>
      <div class="toolbar">
        <span class="tip">账户管理（超级管理员专用，不可创建/编辑/删除超级管理员）</span>
        <el-button type="success" @click="openCreate">新增账户</el-button>
      </div>
      <el-table :data="accounts" v-loading="loading" border>
        <el-table-column prop="username" label="用户名" width="160" />
        <el-table-column prop="display_name" label="显示名" width="160" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'warning' : row.role === 'auditor' ? 'success' : 'info'">
              {{ roleLabels[row.role] || row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" :disabled="row.id === currentId" @click="doDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showForm" :title="form.id ? '编辑账户' : '新增账户'" width="480px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item label="显示名"><el-input v-model="form.display_name" /></el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="form.role" style="width: 200px">
            <el-option v-for="r in assignableRoles" :key="r" :label="roleLabels[r]" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item :label="form.id ? '重置密码' : '密码'" required>
          <el-input v-model="form.password" type="password" show-password :placeholder="form.id ? '留空则不修改' : '必填'" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createAccount, deleteAccount, listAccounts, updateAccount, type Account } from '@/api/accounts'
import { useUserStore } from '@/store/user'
import { ASSIGNABLE_ROLES, ROLE_LABELS } from '@/utils/roles'
import { formatDateTime } from '@/utils/datetime'

const userStore = useUserStore()
const currentId = userStore.user?.id ?? -1
const roleLabels = ROLE_LABELS
const assignableRoles = ASSIGNABLE_ROLES

const accounts = ref<Account[]>([])
const loading = ref(false)
const showForm = ref(false)
const saving = ref(false)
const form = reactive({ id: 0, username: '', display_name: '', role: 'user', password: '', is_active: true })

async function load() {
  loading.value = true
  try {
    accounts.value = await listAccounts()
  } finally {
    loading.value = false
  }
}
function openCreate() {
  Object.assign(form, { id: 0, username: '', display_name: '', role: 'user', password: '', is_active: true })
  showForm.value = true
}
function openEdit(row: Account) {
  Object.assign(form, { id: row.id, username: row.username, display_name: row.display_name, role: row.role, password: '', is_active: row.is_active })
  showForm.value = true
}
async function doSave() {
  if (!form.username || !form.role) {
    ElMessage.warning('请填写用户名与角色')
    return
  }
  if (!form.id && !form.password) {
    ElMessage.warning('新增账户需填写密码')
    return
  }
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      display_name: form.display_name,
      role: form.role,
      is_active: form.is_active,
    }
    if (form.password) payload.password = form.password
    if (form.id) {
      await updateAccount(form.id, payload)
    } else {
      await createAccount({ username: form.username, password: form.password, display_name: form.display_name, role: form.role })
    }
    ElMessage.success('已保存')
    showForm.value = false
    load()
  } finally {
    saving.value = false
  }
}
async function doDelete(row: Account) {
  await ElMessageBox.confirm(`确认删除账户 ${row.username}？`, '警告', { type: 'warning' })
  await deleteAccount(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.tip {
  color: #909399;
}
</style>

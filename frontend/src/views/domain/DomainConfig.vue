<template>
  <div>
    <el-card>
      <div class="toolbar">
        <span class="tip">域控配置（多域）</span>
        <el-button v-if="writable" type="success" @click="openCreate">新增域</el-button>
      </div>
      <el-table :data="domains" v-loading="loading" border>
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="host" label="主机" width="160" />
        <el-table-column prop="port" label="端口" width="80" />
        <el-table-column prop="base_dn" label="Base DN" min-width="180" show-overflow-tooltip />
        <el-table-column prop="bind_dn" label="绑定账号" min-width="180" show-overflow-tooltip />
        <el-table-column label="SSL" width="70">
          <template #default="{ row }"><el-tag :type="row.use_ssl ? 'success' : 'info'">{{ row.use_ssl ? '开' : '关' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="默认" width="70">
          <template #default="{ row }"><el-tag v-if="row.is_default" type="warning">默认</el-tag><span v-else>—</span></template>
        </el-table-column>
        <el-table-column prop="description" label="描述" />
        <el-table-column label="证书通道" width="150">
          <template #default="{ row }">
            <el-tag v-if="!row.ca_enabled" type="info">CA关闭(不限制)</el-tag>
            <el-tooltip v-else-if="row.cert_not_after && (row.cert_trust === 'expiring_soon' || row.cert_trust === 'expired')" :content="`到期：${row.cert_not_after}`">
              <el-tag :type="trustTag(row.cert_trust).type">{{ trustTag(row.cert_trust).label }}</el-tag>
            </el-tooltip>
            <el-tag v-else :type="trustTag(row.cert_trust).type">{{ trustTag(row.cert_trust).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="writable" label="操作" min-width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="doTest(row)">连通测试</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="doDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showForm" :title="form.id ? '编辑域' : '新增域'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="主机" required><el-input v-model="form.host" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="form.port" :min="1" :max="65535" /></el-form-item>
        <el-form-item label="SSL"><el-switch v-model="form.use_ssl" /></el-form-item>
        <el-form-item label="Base DN" required><el-input v-model="form.base_dn" placeholder="DC=corp,DC=local" /></el-form-item>
        <el-form-item label="绑定账号" required><el-input v-model="form.bind_dn" placeholder="admin@corp.local 或 DN" /></el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.bind_password" type="password" show-password :placeholder="form.id && form.has_password ? '留空表示不修改' : '必填'" />
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="CA 认证" v-if="isSuper">
          <el-switch v-model="form.ca_enabled" active-text="启用" inactive-text="关闭" @change="onCaToggle" />
          <div class="ca-hint">关闭后不启用任何 CA 相关限制，管理员可自由操作（仅超级管理员可切换）</div>
        </el-form-item>
        <el-form-item label="CA 证书" v-if="writable && form.ca_enabled">
          <el-input v-model="form.ca_cert" type="textarea" :rows="4" placeholder="粘贴域控自签名证书 PEM（可选）；导入后走更安全的校验通道，证书过期将暂停写操作" />
          <div v-if="form.id && form.cert_trust" class="ca-hint">
            当前通道：<el-tag size="small" :type="trustTag(form.cert_trust).type">{{ trustTag(form.cert_trust).label }}</el-tag>
            <span v-if="form.cert_not_after">（到期：{{ form.cert_not_after }}）</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="info" :loading="testing" @click="doTestForm">连通测试</el-button>
        <el-button v-if="writable && form.id && form.ca_enabled" type="warning" :loading="verifying" @click="doImportCa">导入并验证 CA</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createDomain, deleteDomain, listDomains, testDomain, testDomainById, updateDomain, updateDomainCa, toggleDomainCa, type DomainConfig } from '@/api/domain'
import { useUserStore } from '@/store/user'
import { canWrite } from '@/utils/roles'

const userStore = useUserStore()
const writable = computed(() => canWrite(userStore.user?.role))
const isSuper = computed(() => userStore.user?.role === 'super_admin')

const domains = ref<DomainConfig[]>([])
const loading = ref(false)
const showForm = ref(false)
const saving = ref(false)
const testing = ref(false)
const verifying = ref(false)
const form = reactive({
  id: 0, name: '', host: '', port: 636, use_ssl: true, base_dn: '', bind_dn: '', bind_password: '', description: '', has_password: false,
  ca_cert: '', cert_trust: 'none', cert_not_after: '', ca_enabled: true,
})

function trustTag(trust?: string): { type: string; label: string } {
  switch (trust) {
    case 'ok': return { type: 'success', label: '已信任' }
    case 'expiring_soon': return { type: 'warning', label: `即将到期(${daysLeft(form.cert_not_after)}天)` }
    case 'expired': return { type: 'danger', label: '已过期' }
    case 'untrusted': return { type: 'danger', label: '校验失败' }
    default: return { type: 'warning', label: '缺CA(不安全)' }
  }
}
function daysLeft(notAfter?: string): number | string {
  if (!notAfter) return '-'
  const ms = new Date(notAfter).getTime() - Date.now()
  return Math.max(0, Math.ceil(ms / 86400000))
}

async function load() {
  loading.value = true
  try {
    domains.value = await listDomains()
  } finally {
    loading.value = false
  }
}
function openCreate() {
  Object.assign(form, { id: 0, name: '', host: '', port: 636, use_ssl: true, base_dn: '', bind_dn: '', bind_password: '', description: '', has_password: false, ca_cert: '', cert_trust: 'none', cert_not_after: '', ca_enabled: true })
  showForm.value = true
}
function openEdit(row: DomainConfig) {
  Object.assign(form, { id: row.id, name: row.name, host: row.host, port: row.port, use_ssl: row.use_ssl, base_dn: row.base_dn, bind_dn: row.bind_dn, bind_password: '', description: row.description, has_password: row.has_password, ca_cert: row.ca_cert || '', cert_trust: row.cert_trust || 'none', cert_not_after: row.cert_not_after || '', ca_enabled: row.ca_enabled !== false })
  showForm.value = true
}
async function doImportCa() {
  verifying.value = true
  try {
    const r = await updateDomainCa(form.id, form.ca_cert)
    form.cert_trust = r.cert_trust || 'none'
    form.cert_not_after = (r.cert_not_after as string) || ''
    ElMessage.success(`CA 已更新：${trustTag(r.cert_trust).label}`)
  } finally {
    verifying.value = false
  }
}
async function onCaToggle(val: boolean) {
  // 新建域时随保存提交；编辑已有域则即时切换（仅超级管理员）
  if (!form.id) return
  try {
    const r = await toggleDomainCa(form.id, val)
    const i = domains.value.findIndex((d) => d.id === form.id)
    if (i >= 0) domains.value[i] = r
    ElMessage.success(val ? '已启用 CA 认证' : '已关闭 CA 认证，管理员操作不再受证书限制')
  } catch (e: any) {
    form.ca_enabled = !val
    ElMessage.error(e?.response?.data?.detail || '切换 CA 认证失败')
  }
}
async function doSave() {
  if (!form.name || !form.host || !form.base_dn || !form.bind_dn) {
    ElMessage.warning('请填写名称、主机、Base DN、绑定账号')
    return
  }
  if (!form.id && !form.bind_password) {
    ElMessage.warning('新增域需填写绑定密码')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name, host: form.host, port: form.port, use_ssl: form.use_ssl,
      base_dn: form.base_dn, bind_dn: form.bind_dn, bind_password: form.bind_password, description: form.description,
      ca_cert: form.ca_cert, ca_enabled: form.ca_enabled,
    }
    if (form.id) {
      await updateDomain(form.id, payload)
    } else {
      await createDomain(payload)
    }
    ElMessage.success('已保存')
    showForm.value = false
    load()
  } finally {
    saving.value = false
  }
}
async function doTest(row: DomainConfig) {
  testing.value = true
  try {
    const r = await testDomainById(row.id)
    if (r.ok) ElMessage.success(`连通成功：${r.domain_name || row.name}`)
    else ElMessage.error(`连通失败：${r.message}`)
  } finally {
    testing.value = false
  }
}
async function doTestForm() {
  if (!form.host || !form.bind_dn) {
    ElMessage.warning('请先填写主机与绑定账号')
    return
  }
  testing.value = true
  try {
    const r = await testDomain({ name: form.name, host: form.host, port: form.port, use_ssl: form.use_ssl, base_dn: form.base_dn, bind_dn: form.bind_dn, bind_password: form.bind_password, description: form.description })
    if (r.ok) ElMessage.success(`连通成功：${r.domain_name || ''}`)
    else ElMessage.error(`连通失败：${r.message}`)
  } finally {
    testing.value = false
  }
}
async function doDelete(row: DomainConfig) {
  await ElMessageBox.confirm(`确认删除域 ${row.name}？`, '警告', { type: 'warning' })
  await deleteDomain(row.id)
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
.ca-hint {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}
</style>

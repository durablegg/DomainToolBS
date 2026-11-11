<template>
  <div>
    <el-card>
      <template #header>委派管理员授权（域 + OU + 权限）</template>
      <el-alert type="info" :closable="false" title="仅超级管理员可在此为「管理员」角色分配一个或多个域控的管辖范围与权限；普通用户与审计员使用系统内置默认权限，无需分配。" />
      <el-form :inline="true" class="toolbar">
        <el-form-item label="管理员">
          <el-select v-model="selectedAdmin" placeholder="选择管理员" filterable style="width: 280px" @change="onAdminChange">
            <el-option v-for="a in admins" :key="a.id" :label="`${a.display_name || a.username}（${roleLabels[a.role] || a.role}）`" :value="a.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <div v-if="selectedAdmin && isDelegable" class="scopes">
        <div v-for="(row, idx) in scopes" :key="idx" class="scope-card">
          <div class="scope-head">
            <el-select v-model="row.domain_id" placeholder="选择域" style="width: 220px" @change="onDomainChange(idx)">
              <el-option v-for="d in domains" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
            <el-button link type="primary" @click="openOuPicker(idx)">选择 OU</el-button>
            <el-button link type="info" @click="setWholeDomain(idx)">设为整个域</el-button>
            <span class="ou-dn">{{ row.base_dn || '未选择 OU' }}</span>
            <el-button link type="danger" @click="removeScope(idx)">删除</el-button>
          </div>
          <table class="perm-table">
            <thead>
              <tr><th>资源</th><th>操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in matrixResources" :key="r.key">
                <td :title="r.key">{{ r.label }}</td>
                <td>
                  <el-checkbox
                    v-for="a in r.actions"
                    :key="a.key"
                    :model-value="permChecked(row, a.key)"
                    :label="a.label"
                    @change="togglePerm(row, a.key, ($event as boolean))"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="scope-actions">
          <el-button type="dashed" @click="addScope">+ 新增授权范围</el-button>
          <el-button type="primary" :loading="saving" @click="saveScopes">保存授权</el-button>
        </div>
      </div>

      <div v-else-if="selectedAdmin" class="default-perms">
        <el-alert type="success" :closable="false" show-icon :title="defaultPerms.title" />
        <ul class="perm-list">
          <li v-for="(t, i) in defaultPerms.items" :key="i">{{ t }}</li>
        </ul>
      </div>
    </el-card>

    <el-dialog v-model="showSave" title="确认保存" width="420px">
      <span>将覆盖该管理员的全部授权范围，是否继续？</span>
      <template #footer>
        <el-button @click="showSave = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="ouTreeOpen" title="选择 OU" width="420px">
      <el-tree :data="ouOptions" :props="{ label: 'label', children: 'children' }" node-key="value" highlight-current @current-change="onOuPick" />
      <template #footer>
        <el-button @click="ouTreeOpen = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getScopes, listAdmins, putScopes, type AdminBrief, type AdminScope } from '@/api/rbac'
import { listDomains, type DomainConfig } from '@/api/domain'
import { listOus, type OU } from '@/api/ou'
import { ROLE_ADMIN, ROLE_LABELS } from '@/utils/roles'

const roleLabels = ROLE_LABELS
const selectedAdmin = ref<number | null>(null)
const admins = ref<AdminBrief[]>([])
const domains = ref<DomainConfig[]>([])
const scopes = ref<{ domain_id: number | null; base_dn: string; permissions: string[] }[]>([])

const selectedRole = computed(() => admins.value.find((a) => a.id === selectedAdmin.value)?.role || '')
// 仅「管理员」需要（且允许）分配域 + OU + 权限；其余角色使用内置默认权限
const isDelegable = computed(() => selectedRole.value === ROLE_ADMIN)

// 各角色的内置默认权限（只读展示，无需分配）
const DEFAULT_PERMISSIONS: Record<string, { title: string; items: string[] }> = {
  user: {
    title: '普通用户：使用系统内置默认权限，无需额外授权',
    items: [
      '全部域只读：可查看域配置、用户、用户组、计算机、组织单位',
      '无写入 / 删除权限',
      '无授权管理、账户管理权限',
      '无审计日志查看权限',
      '查看域详情时连接凭据（主机 / 绑定账号）脱敏显示',
    ],
  },
  auditor: {
    title: '审计员：使用系统内置默认权限，无需额外授权',
    items: [
      '仅可查看 / 导出审计日志',
      '无域目录访问权限（不可查看域、用户、用户组、计算机）',
      '无写入 / 删除 / 授权 / 账户管理权限',
    ],
  },
}
const defaultPerms = computed(
  () => DEFAULT_PERMISSIONS[selectedRole.value] || { title: '该角色无额外授权项', items: [] },
)

interface OuOpt { value: string; label: string; children: OuOpt[] }
const ouOptions = ref<OuOpt[]>([])
const ouTreeOpen = ref(false)
let ouPickIndex = 0

const showSave = ref(false)
const saving = ref(false)

const matrixResources = [
  { key: 'user', label: '用户', actions: [
    { key: 'user:write', label: '写' },
    { key: 'user:delete', label: '删除' },
    { key: 'user:reset_password', label: '重置密码' },
  ] },
  { key: 'group', label: '用户组', actions: [
    { key: 'group:write', label: '写' },
    { key: 'group:delete', label: '删除' },
  ] },
  { key: 'computer', label: '计算机', actions: [
    { key: 'computer:write', label: '写' },
    { key: 'computer:delete', label: '删除' },
  ] },
  { key: 'ou', label: '组织单位', actions: [
    { key: 'ou:write', label: '写/删' },
  ] },
]

function permChecked(row: { permissions: string[] }, key: string) {
  return row.permissions.includes(key)
}
function togglePerm(row: { permissions: string[] }, key: string, checked: boolean) {
  if (checked && !row.permissions.includes(key)) row.permissions.push(key)
  if (!checked) row.permissions = row.permissions.filter((p) => p !== key)
}
function buildPermissions(row: { permissions: string[] }) {
  return row.permissions
}

async function loadAdmins() {
  admins.value = await listAdmins()
}
async function loadDomains() {
  domains.value = await listDomains()
}
const domainMap = ref<Record<number, DomainConfig>>({})
function rebuildDomainMap() {
  domainMap.value = Object.fromEntries(domains.value.map((d) => [d.id, d]))
}

async function onAdminChange() {
  if (!selectedAdmin.value) return
  // 非管理员角色不涉及域/OU 授权，只展示默认权限
  if (!isDelegable.value) {
    scopes.value = []
    return
  }
  const data = await getScopes(selectedAdmin.value)
  scopes.value = data.map((s: AdminScope) => ({ domain_id: s.domain_id, base_dn: s.base_dn, permissions: [...s.permissions] }))
  if (!scopes.value.length) addScope()
}
function addScope() {
  scopes.value.push({ domain_id: domains.value.length ? domains.value[0].id : null, base_dn: '', permissions: [] })
}
function removeScope(idx: number) {
  scopes.value.splice(idx, 1)
}
function onDomainChange(idx: number) {
  // 切换域后 OU 失效，清空 base_dn
  scopes.value[idx].base_dn = ''
}
async function openOuPicker(idx: number) {
  const domainId = scopes.value[idx].domain_id
  if (!domainId) {
    ElMessage.warning('请先选择域')
    return
  }
  ouPickIndex = idx
  const ous = await listOus(domainId)
  ouOptions.value = toOptions(ous)
  ouTreeOpen.value = true
}
function toOptions(ous: OU[]): OuOpt[] {
  return ous.map((o) => ({ value: o.dn, label: o.name, children: toOptions(o.sub_ous || []) }))
}
function onOuPick(node: { value: string }) {
  if (scopes.value[ouPickIndex]) scopes.value[ouPickIndex].base_dn = node.value
}
function setWholeDomain(idx: number) {
  const d = scopes.value[idx].domain_id
  if (!d) {
    ElMessage.warning('请先选择域')
    return
  }
  const cfg = domainMap.value[d]
  if (cfg) scopes.value[idx].base_dn = cfg.base_dn
}

function saveScopes() {
  if (!selectedAdmin.value) return
  for (const s of scopes.value) {
    if (!s.domain_id) {
      ElMessage.warning('存在未选择域的授权范围')
      return
    }
  }
  showSave.value = true
}
async function doSave() {
  if (!selectedAdmin.value) return
  saving.value = true
  try {
    await putScopes(
      selectedAdmin.value,
      scopes.value.map((s) => ({ domain_id: s.domain_id as number, base_dn: s.base_dn, permissions: buildPermissions(s) })),
    )
    ElMessage.success('授权已保存')
    showSave.value = false
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadAdmins()
  await loadDomains()
  rebuildDomainMap()
})
</script>

<style scoped>
.toolbar {
  margin: 12px 0;
}
.scopes {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.scope-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
}
.scope-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.scope-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.default-perms {
  margin-top: 4px;
}
.perm-list {
  margin: 12px 0 0;
  padding-left: 20px;
  color: #606266;
  line-height: 2;
  font-size: 13px;
}
.ou-dn {
  color: #909399;
  font-size: 12px;
  margin-left: 4px;
}
.perm-table {
  width: 100%;
  border-collapse: collapse;
}
.perm-table th,
.perm-table td {
  border: 1px solid #ebeef5;
  padding: 6px 10px;
  text-align: left;
}
.perm-table th {
  background: #f5f7fa;
}
</style>

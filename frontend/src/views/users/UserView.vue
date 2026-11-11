<template>
  <div>
    <el-alert
      v-if="!domainId"
      type="warning"
      :closable="false"
      title="请先在顶部选择要管理的域"
      style="margin-bottom: 12px"
    />
    <el-card>
      <el-form :inline="true" :model="query" class="toolbar">
        <el-form-item label="关键字">
          <el-input v-model="query.keyword" placeholder="登录名/姓名/邮箱" clearable @keyup.enter="load" />
        </el-form-item>
        <el-form-item label="OU 归属">
          <el-tree-select v-model="query.ou" :data="ouOptions" value-key="value" :props="{ label: 'label', children: 'children' }" check-strictly clearable placeholder="按 OU 过滤（默认全域）" style="width: 260px" @change="load" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="query.enabled" placeholder="全部" clearable style="width: 120px">
            <el-option label="启用" value="true" />
            <el-option label="禁用" value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="锁定">
          <el-select v-model="query.locked" placeholder="全部" clearable style="width: 120px">
            <el-option label="已锁定" value="true" />
            <el-option label="未锁定" value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
          <el-button v-if="writable" type="success" @click="openCreate">新建用户</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column prop="sAMAccountName" label="登录名" width="150" />
        <el-table-column prop="displayName" label="姓名" width="140" />
        <el-table-column prop="mail" label="邮箱" width="180" />
        <el-table-column prop="department" label="部门" width="120" />
        <el-table-column prop="title" label="职务" width="120" />
        <el-table-column prop="ou_dn" label="所在OU" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="锁定" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.locked" type="danger">
              已锁定<template v-if="row.lockout_remaining"> 剩{{ Math.ceil(row.lockout_remaining / 60) }}分</template>
            </el-tag>
            <el-tag v-else type="info" effect="plain">未锁定</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下次登录改密" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.must_change_password" type="warning">需改密</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_logon) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.when_created) }}</template>
        </el-table-column>
        <el-table-column v-if="writable" label="操作" min-width="320" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.enabled" link type="warning" @click="doDisable(row)">禁用</el-button>
            <el-button v-else link type="success" @click="doEnable(row)">启用</el-button>
            <el-button v-if="row.locked" link type="danger" @click="doUnlock(row)">解锁</el-button>
            <el-button link type="primary" @click="openReset(row)">重置密码</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="openMove(row)">移动</el-button>
            <el-button link type="danger" @click="doDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pager"
        layout="total, prev, pager, next"
        :total="total"
        :current-page="page"
        :page-size="size"
        @current-change="onPage"
      />
    </el-card>

    <!-- 新建 -->
    <el-dialog v-model="showCreate" title="新建域用户" width="520px">
      <el-form :model="createForm" label-width="110px">
        <el-form-item label="所属 OU" required>
          <el-tree-select v-model="createForm.ou_dn" :data="ouOptions" value-key="value" :props="{ label: 'label', children: 'children' }" check-strictly placeholder="选择 OU" />
        </el-form-item>
        <el-form-item label="登录名" required><el-input v-model="createForm.sAMAccountName" /></el-form-item>
        <el-form-item label="姓名" required><el-input v-model="createForm.displayName" /></el-form-item>
        <el-form-item label="初始密码" required><el-input v-model="createForm.password" show-password /></el-form-item>
        <el-form-item label="UPN"><el-input v-model="createForm.userPrincipalName" placeholder="user@corp.local" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="createForm.mail" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="createForm.department" /></el-form-item>
        <el-form-item label="职务"><el-input v-model="createForm.title" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="createForm.telephoneNumber" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="createForm.description" /></el-form-item>
        <el-form-item label="密码永不过期"><el-switch v-model="createForm.password_never_expires" /></el-form-item>
        <el-form-item label="下次登录改密"><el-switch v-model="createForm.must_change_next_logon" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑 -->
    <el-dialog v-model="showEdit" title="编辑用户" width="520px">
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="姓名"><el-input v-model="editForm.displayName" /></el-form-item>
        <el-form-item label="UPN"><el-input v-model="editForm.userPrincipalName" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="editForm.mail" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="editForm.department" /></el-form-item>
        <el-form-item label="职务"><el-input v-model="editForm.title" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="editForm.telephoneNumber" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="editForm.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="showReset" title="重置密码" width="420px">
      <el-form :model="resetForm" label-width="100px">
        <el-form-item label="新密码" required><el-input v-model="resetForm.new_password" show-password /></el-form-item>
        <el-form-item label="下次登录改密"><el-switch v-model="resetForm.must_change_next_logon" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReset = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doReset">确定</el-button>
      </template>
    </el-dialog>

    <!-- 移动 -->
    <el-dialog v-model="showMove" title="移动到 OU" width="420px">
      <el-tree-select v-model="moveTarget" :data="ouOptions" value-key="value" :props="{ label: 'label', children: 'children' }" check-strictly placeholder="选择目标 OU" />
      <template #footer>
        <el-button @click="showMove = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doMove">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, deleteUser, disableUser, enableUser, listUsers, moveUser, resetPassword, unlockUser, updateUser, type UserItem } from '@/api/users'
import { listOus, type OU } from '@/api/ou'
import { useDomainStore } from '@/store/domain'
import { useUserStore } from '@/store/user'
import { canWrite } from '@/utils/roles'
import { encodeDN } from '@/utils/dn'
import { formatDateTime } from '@/utils/datetime'

const domainStore = useDomainStore()
const userStore = useUserStore()
const domainId = computed(() => domainStore.currentDomainId)
const writable = computed(() => canWrite(userStore.user?.role))

const rows = ref<UserItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const query = reactive({ keyword: '', ou: '', enabled: '', locked: '' })

interface OuOpt { value: string; label: string; children: OuOpt[] }
const ouOptions = ref<OuOpt[]>([])
const ouFlat = ref<OU[]>([])

function flatten(ous: OU[]): OU[] {
  return ous.flatMap((o) => [o, ...flatten(o.sub_ous || [])])
}
function toOptions(ous: OU[]): OuOpt[] {
  return ous.map((o) => ({ value: o.dn, label: o.name, children: toOptions(o.sub_ous || []) }))
}

async function loadOus() {
  if (!domainId.value) return
  try {
    const ous = await listOus(domainId.value)
    ouFlat.value = flatten(ous)
    ouOptions.value = toOptions(ous)
  } catch {
    /* 未配置域时忽略 */
  }
}

async function load() {
  if (!domainId.value) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const data = await listUsers({ ...query, page: page.value, size: size.value }, domainId.value)
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.keyword = ''
  query.ou = ''
  query.enabled = ''
  query.locked = ''
  page.value = 1
  load()
}
function onPage(p: number) {
  page.value = p
  load()
}

// 新建
const showCreate = ref(false)
const saving = ref(false)
const createForm = reactive({
  ou_dn: '', sAMAccountName: '', displayName: '', password: '',
  userPrincipalName: '', mail: '', department: '', title: '', telephoneNumber: '', description: '',
  password_never_expires: false, must_change_next_logon: true,
})
function openCreate() {
  Object.assign(createForm, {
    ou_dn: '', sAMAccountName: '', displayName: '', password: '',
    userPrincipalName: '', mail: '', department: '', title: '', telephoneNumber: '', description: '',
    password_never_expires: false, must_change_next_logon: true,
  })
  showCreate.value = true
}
async function doCreate() {
  if (!domainId.value) return
  if (!createForm.ou_dn || !createForm.sAMAccountName || !createForm.displayName || !createForm.password) {
    ElMessage.warning('请填写所属 OU、登录名、姓名与初始密码')
    return
  }
  saving.value = true
  try {
    await createUser({ ...createForm }, domainId.value)
    ElMessage.success('已创建')
    showCreate.value = false
    load()
  } finally {
    saving.value = false
  }
}

// 编辑
const showEdit = ref(false)
const editForm = reactive({ dn: '', displayName: '', userPrincipalName: '', mail: '', department: '', title: '', telephoneNumber: '', description: '' })
function openEdit(row: UserItem) {
  editForm.dn = row.dn
  editForm.displayName = row.displayName || ''
  editForm.userPrincipalName = row.userPrincipalName || ''
  editForm.mail = row.mail || ''
  editForm.department = row.department || ''
  editForm.title = row.title || ''
  editForm.telephoneNumber = row.telephoneNumber || ''
  editForm.description = row.description || ''
  showEdit.value = true
}
async function doEdit() {
  if (!domainId.value) return
  saving.value = true
  try {
    await updateUser(encodeDN(editForm.dn), {
      displayName: editForm.displayName,
      userPrincipalName: editForm.userPrincipalName,
      mail: editForm.mail,
      department: editForm.department,
      title: editForm.title,
      telephoneNumber: editForm.telephoneNumber,
      description: editForm.description,
    }, domainId.value)
    ElMessage.success('已保存')
    showEdit.value = false
    load()
  } finally {
    saving.value = false
  }
}

// 重置密码
const showReset = ref(false)
const resetForm = reactive({ dn: '', new_password: '', must_change_next_logon: true })
function openReset(row: UserItem) {
  resetForm.dn = row.dn
  resetForm.new_password = ''
  resetForm.must_change_next_logon = true
  showReset.value = true
}
async function doReset() {
  if (!domainId.value) return
  if (!resetForm.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  saving.value = true
  try {
    await resetPassword(encodeDN(resetForm.dn), {
      new_password: resetForm.new_password,
      must_change_next_logon: resetForm.must_change_next_logon,
    }, domainId.value)
    ElMessage.success('密码已重置')
    showReset.value = false
  } finally {
    saving.value = false
  }
}

// 移动
const showMove = ref(false)
const moveTarget = ref('')
let moveDn = ''
function openMove(row: UserItem) {
  moveDn = row.dn
  moveTarget.value = ''
  showMove.value = true
}
async function doMove() {
  if (!domainId.value) return
  if (!moveTarget.value) {
    ElMessage.warning('请选择目标 OU')
    return
  }
  saving.value = true
  try {
    await moveUser(encodeDN(moveDn), moveTarget.value, domainId.value)
    ElMessage.success('已移动')
    showMove.value = false
    load()
  } finally {
    saving.value = false
  }
}

// 启停 / 解锁 / 删除
async function doEnable(row: UserItem) {
  if (!domainId.value) return
  await enableUser(encodeDN(row.dn), domainId.value)
  ElMessage.success('已启用')
  load()
}
async function doDisable(row: UserItem) {
  if (!domainId.value) return
  await disableUser(encodeDN(row.dn), domainId.value)
  ElMessage.success('已禁用')
  load()
}
async function doUnlock(row: UserItem) {
  if (!domainId.value) return
  await unlockUser(encodeDN(row.dn), domainId.value)
  ElMessage.success('已解锁')
  load()
}
async function doDelete(row: UserItem) {
  if (!domainId.value) return
  await ElMessageBox.confirm(`确认删除用户 ${row.sAMAccountName}？`, '警告', { type: 'warning' })
  await deleteUser(encodeDN(row.dn), domainId.value)
  ElMessage.success('已删除')
  load()
}

watch(() => domainStore.currentDomainId, () => {
  page.value = 1
  loadOus()
  load()
})

onMounted(() => {
  loadOus()
  load()
})
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.ml {
  margin-left: 4px;
}
</style>

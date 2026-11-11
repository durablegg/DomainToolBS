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
          <el-input v-model="query.keyword" placeholder="组名/登录名" clearable @keyup.enter="load" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="query.security" placeholder="全部" clearable style="width: 130px">
            <el-option label="安全组" value="true" />
            <el-option label="通讯组" value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
          <el-button v-if="writable" type="success" @click="showCreate = true">新建组</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column prop="sAMAccountName" label="登录名" width="160" />
        <el-table-column prop="displayName" label="显示名" width="160" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_security ? '' : 'info'">{{ row.is_security ? '安全组' : '通讯组' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="member_count" label="成员数" width="80" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="when_created" label="创建时间" width="170" />
        <el-table-column v-if="writable" label="操作" min-width="230" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openMembers(row)">成员</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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
    <el-dialog v-model="showCreate" title="新建组" width="520px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="所属 OU" required>
          <el-tree-select v-model="createForm.ou_dn" :data="ouOptions" value-key="value" :props="{ label: 'label', children: 'children' }" check-strictly placeholder="选择 OU" />
        </el-form-item>
        <el-form-item label="登录名" required><el-input v-model="createForm.sAMAccountName" /></el-form-item>
        <el-form-item label="显示名" required><el-input v-model="createForm.displayName" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="邮件"><el-input v-model="createForm.mail" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="createForm.description" /></el-form-item>
        <el-form-item label="管理者"><el-input v-model="createForm.managedBy" placeholder="管理者 DN" /></el-form-item>
        <el-form-item label="作用域">
          <el-select v-model="createForm.scope">
            <el-option label="全局" value="global" />
            <el-option label="域本地" value="domainlocal" />
            <el-option label="通用" value="universal" />
          </el-select>
        </el-form-item>
        <el-form-item label="安全组"><el-switch v-model="createForm.security" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑 -->
    <el-dialog v-model="showEdit" title="编辑组" width="520px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="显示名"><el-input v-model="editForm.displayName" /></el-form-item>
        <el-form-item label="邮件"><el-input v-model="editForm.mail" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="editForm.description" /></el-form-item>
        <el-form-item label="管理者"><el-input v-model="editForm.managedBy" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 成员 -->
    <el-dialog v-model="showMembers" title="组成员" width="640px">
      <div style="margin-bottom: 8px">
        <el-button type="primary" @click="openAddMember">添加成员</el-button>
        <span style="color: #909399; margin-left: 8px">共 {{ memberTotal }} 个成员</span>
      </div>
      <el-table :data="members" border>
        <el-table-column prop="sAMAccountName" label="登录名" width="160" />
        <el-table-column prop="displayName" label="名称" width="160" />
        <el-table-column prop="kind" label="类型" width="100" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" @click="doRemoveMember(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="prev, pager, next"
        :total="memberTotal"
        :current-page="memberPage"
        :page-size="memberSize"
        @current-change="onMemberPage"
      />
    </el-dialog>

    <el-dialog v-model="showAddMember" title="添加成员" width="480px">
      <el-select v-model="addSelection" multiple filterable placeholder="选择用户/计算机" style="width: 100%">
        <el-option v-for="u in userOptions" :key="u.dn" :label="u.sAMAccountName" :value="u.dn" />
      </el-select>
      <template #footer>
        <el-button @click="showAddMember = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doAddMembers">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addMembers,
  createGroup,
  deleteGroup,
  listGroups,
  listMembers,
  removeMembers,
  updateGroup,
  type GroupItem,
  type GroupMemberItem,
} from '@/api/groups'
import { listOus, type OU } from '@/api/ou'
import { listUsers, type UserItem } from '@/api/users'
import { useDomainStore } from '@/store/domain'
import { useUserStore } from '@/store/user'
import { canWrite } from '@/utils/roles'
import { encodeDN } from '@/utils/dn'

const domainStore = useDomainStore()
const userStore = useUserStore()
const domainId = computed(() => domainStore.currentDomainId)
const writable = computed(() => canWrite(userStore.user?.role))

interface OuOpt { value: string; label: string; children: OuOpt[] }
const ouOptions = ref<OuOpt[]>([])
function toOptions(ous: OU[]): OuOpt[] {
  return ous.map((o) => ({ value: o.dn, label: o.name, children: toOptions(o.sub_ous || []) }))
}
async function loadOus() {
  if (!domainId.value) return
  try {
    ouOptions.value = toOptions(await listOus(domainId.value))
  } catch {
    /* 未配置域时忽略 */
  }
}

const rows = ref<GroupItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const query = reactive({ keyword: '', security: '' })

async function load() {
  if (!domainId.value) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const d = await listGroups({ ...query, page: page.value, size: size.value }, domainId.value)
    rows.value = d.items
    total.value = d.total
  } finally {
    loading.value = false
  }
}
function resetQuery() {
  query.keyword = ''
  query.security = ''
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
  ou_dn: '', sAMAccountName: '', displayName: '', name: '', mail: '',
  description: '', managedBy: '', scope: 'global', security: true,
})
async function doCreate() {
  if (!domainId.value) return
  if (!createForm.ou_dn || !createForm.sAMAccountName || !createForm.displayName) {
    ElMessage.warning('请填写所属 OU、登录名、显示名')
    return
  }
  saving.value = true
  try {
    await createGroup({ ...createForm }, domainId.value)
    ElMessage.success('已创建')
    showCreate.value = false
    load()
  } finally {
    saving.value = false
  }
}

// 编辑
const showEdit = ref(false)
const editForm = reactive({ dn: '', displayName: '', mail: '', description: '', managedBy: '' })
function openEdit(row: GroupItem) {
  editForm.dn = row.dn
  editForm.displayName = row.displayName || ''
  editForm.mail = row.mail || ''
  editForm.description = row.description || ''
  editForm.managedBy = row.managedBy || ''
  showEdit.value = true
}
async function doEdit() {
  if (!domainId.value) return
  saving.value = true
  try {
    await updateGroup(encodeDN(editForm.dn), {
      displayName: editForm.displayName,
      mail: editForm.mail,
      description: editForm.description,
      managedBy: editForm.managedBy,
    }, domainId.value)
    ElMessage.success('已保存')
    showEdit.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function doDelete(row: GroupItem) {
  if (!domainId.value) return
  await ElMessageBox.confirm(`确认删除组 ${row.sAMAccountName}？`, '警告', { type: 'warning' })
  await deleteGroup(encodeDN(row.dn), domainId.value)
  ElMessage.success('已删除')
  load()
}

// 成员
const showMembers = ref(false)
const members = ref<GroupMemberItem[]>([])
const memberTotal = ref(0)
const memberPage = ref(1)
const memberSize = ref(20)
let curGroupDn = ''
async function openMembers(row: GroupItem) {
  if (!domainId.value) return
  curGroupDn = row.dn
  memberPage.value = 1
  showMembers.value = true
  await loadMembers()
}
async function loadMembers() {
  if (!domainId.value) return
  const d = await listMembers(encodeDN(curGroupDn), { page: memberPage.value, size: memberSize.value }, domainId.value)
  members.value = d.items
  memberTotal.value = d.total
}
function onMemberPage(p: number) {
  memberPage.value = p
  loadMembers()
}
async function doRemoveMember(row: GroupMemberItem) {
  if (!domainId.value) return
  await removeMembers(encodeDN(curGroupDn), [row.dn], domainId.value)
  ElMessage.success('已移除')
  await loadMembers()
}

const showAddMember = ref(false)
const addSelection = ref<string[]>([])
const userOptions = ref<UserItem[]>([])
async function openAddMember() {
  if (!domainId.value) return
  try {
    const d = await listUsers({ page: 1, size: 200 }, domainId.value)
    userOptions.value = d.items
  } catch {
    /* ignore */
  }
  addSelection.value = []
  showAddMember.value = true
}
async function doAddMembers() {
  if (!domainId.value) return
  if (!addSelection.value.length) {
    ElMessage.warning('请选择成员')
    return
  }
  saving.value = true
  try {
    await addMembers(encodeDN(curGroupDn), addSelection.value, domainId.value)
    ElMessage.success('已添加')
    showAddMember.value = false
    await loadMembers()
  } finally {
    saving.value = false
  }
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
</style>

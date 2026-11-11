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
      <div class="toolbar">
        <el-radio-group v-model="action">
          <el-radio-button value="create">新增用户</el-radio-button>
          <el-radio-button value="delete">删除用户</el-radio-button>
          <el-radio-button value="update">修改用户</el-radio-button>
        </el-radio-group>
        <el-button type="primary" @click="downloadTemplate">下载模板</el-button>
        <el-upload
          :auto-upload="false"
          :show-file-list="true"
          :on-change="onFileChange"
          accept=".csv"
          style="display: inline-block; margin: 0 8px"
        >
          <el-button>选择 CSV</el-button>
        </el-upload>
        <el-select v-if="action === 'create'" v-model="importOu" placeholder="选择导入目标 OU" filterable style="width: 280px">
          <el-option v-for="o in ouOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-button type="success" :disabled="!canSubmit" :loading="importing" @click="doSubmit">开始执行</el-button>
        <el-button @click="doExport" :disabled="!domainId">导出当前域用户</el-button>
      </div>
      <el-alert type="info" :closable="false" :title="actionHint" />
      <el-alert
        v-if="action !== 'create' && domainId"
        type="warning"
        :closable="false"
        show-icon
        style="margin-top: 10px"
        :title="`本次操作仅作用于域：${currentDomainName}（CSV 仅按登录名定位，不区分 OU）`"
      />

      <div class="task-head">
        <h4>批量任务</h4>
        <el-button size="small" :loading="taskLoading" @click="refreshTasks()">
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>
      <el-table :data="tasks" v-loading="taskLoading" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="type" label="类型" width="140" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total" label="总数" width="80" />
        <el-table-column prop="ok_count" label="成功" width="80" />
        <el-table-column prop="fail_count" label="失败" width="80" />
        <el-table-column prop="created_by" label="操作人" width="120" />
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDetail" title="任务明细" width="640px">
      <el-table :data="taskItems" border>
        <el-table-column prop="target_name" label="对象" width="160" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ok' ? 'success' : 'danger'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="说明" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/datetime'
import {
  exportUsers,
  importUsers,
  deleteUsers,
  updateUsers,
  downloadUsersTemplate as downloadUsersTemplateApi,
  downloadDeleteTemplate,
  downloadUpdateTemplate,
  getTask,
  listTasks,
  type BatchTask,
} from '@/api/batch'
import { listOus, type OU } from '@/api/ou'
import { listDomains, type DomainConfig } from '@/api/domain'
import { useDomainStore } from '@/store/domain'
import { useUserStore } from '@/store/user'
import { canWrite } from '@/utils/roles'

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

const tasks = ref<BatchTask[]>([])
const taskLoading = ref(false)
const selectedFile = ref<File | null>(null)
const importOu = ref('')
const importing = ref(false)
const domains = ref<DomainConfig[]>([])
const currentDomainName = computed(
  () => domains.value.find((d) => d.id === domainId.value)?.name || `ID ${domainId.value}`,
)
const action = ref<'create' | 'delete' | 'update'>('create')
const canSubmit = computed(
  () =>
    !!selectedFile.value &&
    !!domainId.value &&
    (action.value !== 'create' || !!importOu.value),
)
const actionHint = computed(() => {
  if (action.value === 'create')
    return '新增：CSV 需含 sAMAccountName,displayName,password 等列（参照模板）。'
  if (action.value === 'delete') return '删除：CSV 仅需 sAMAccountName 列。'
  return '修改：CSV 需含 sAMAccountName，并可选 displayName/mail/department/title/password/enabled 等列。'
})

function onFileChange(file: UploadFile) {
  if (file.raw) selectedFile.value = file.raw
}
// 有任务处于 pending/running 时每 4 秒自动刷新，全部结束自动停止
const ACTIVE_STATUS = ['pending', 'running']
let pollTimer: ReturnType<typeof setInterval> | null = null

function hasActiveTask() {
  return tasks.value.some((t) => ACTIVE_STATUS.includes(t.status))
}
function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => refreshTasks(true), 4000)
}
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}
async function refreshTasks(silent = false) {
  if (!silent) taskLoading.value = true
  try {
    tasks.value = await listTasks()
    if (hasActiveTask()) startPolling()
    else stopPolling()
  } finally {
    if (!silent) taskLoading.value = false
  }
}
async function doSubmit() {
  if (!domainId.value || !selectedFile.value) return
  if (action.value === 'create' && !importOu.value) return
  if (action.value !== 'create') {
    try {
      await ElMessageBox.confirm(
        `即将在域「${currentDomainName.value}」执行${action.value === 'delete' ? '删除' : '修改'}操作：`
          + 'CSV 仅按登录名定位用户，不区分 OU。确认继续？',
        '确认操作域',
        { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }
  importing.value = true
  try {
    let res
    if (action.value === 'create') {
      res = await importUsers(selectedFile.value, importOu.value, domainId.value)
    } else if (action.value === 'delete') {
      res = await deleteUsers(selectedFile.value, domainId.value)
    } else {
      res = await updateUsers(selectedFile.value, domainId.value)
    }
    ElMessage.success(`已提交，任务 #${res.task_id}，共 ${res.total} 条`)
    selectedFile.value = null
    refreshTasks()
  } finally {
    importing.value = false
  }
}
async function doExport() {
  if (!domainId.value) return
  try {
    const blob = await exportUsers(undefined, domainId.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `users_${domainId.value}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('导出失败')
  }
}
async function downloadTemplate() {
  try {
    let tpl: Blob
    let name = 'users_template.csv'
    if (action.value === 'create') {
      tpl = await downloadUsersTemplateApi()
    } else if (action.value === 'delete') {
      tpl = await downloadDeleteTemplate()
      name = 'delete_users_template.csv'
    } else {
      tpl = await downloadUpdateTemplate()
      name = 'update_users_template.csv'
    }
    const url = URL.createObjectURL(new Blob([tpl], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('下载模板失败')
  }
}
const showDetail = ref(false)
const taskItems = ref<{ target_name: string; status: string; message: string }[]>([])
async function openDetail(row: BatchTask) {
  showDetail.value = true
  const d = await getTask(row.id)
  taskItems.value = d.items || []
}

watch(() => domainStore.currentDomainId, () => {
  loadOus()
})

onMounted(async () => {
  try {
    domains.value = await listDomains()
  } catch {
    /* 忽略 */
  }
  loadOus()
  refreshTasks()
})

onUnmounted(stopPolling)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
}
.task-head h4 {
  margin: 0;
}
</style>

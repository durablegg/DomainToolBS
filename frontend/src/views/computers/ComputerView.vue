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
          <el-input v-model="query.keyword" placeholder="计算机名" clearable @keyup.enter="load" />
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
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column label="计算机名" width="180">
          <template #default="{ row }">
            <span :title="row.sAMAccountName || ''">{{ computerName(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="dnsHostname" label="DNS 主机名" width="180" show-overflow-tooltip />
        <el-table-column prop="operatingSystem" label="操作系统" width="160" />
        <el-table-column prop="ou_dn" label="所在 OU" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_logon) }}</template>
        </el-table-column>
        <el-table-column v-if="writable" label="操作" min-width="240" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.enabled" link type="warning" @click="doDisable(row)">禁用</el-button>
            <el-button v-else link type="success" @click="doEnable(row)">启用</el-button>
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
import { deleteComputer, disableComputer, enableComputer, listComputers, moveComputer, type ComputerItem } from '@/api/computers'
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

/**
 * AD 计算机（机器）账户的登录名 sAMAccountName 约定以 `$` 结尾（与用户账户区分），
 * 页面展示用 cn/name，并去掉该技术性后缀；完整登录名放在悬浮提示中。
 */
function computerName(row: ComputerItem): string {
  const raw = row.cn || row.name || row.sAMAccountName || ''
  return raw.replace(/\$+$/, '')
}

const rows = ref<ComputerItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const query = reactive({ keyword: '', ou: '', enabled: '' })

async function load() {
  if (!domainId.value) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const d = await listComputers({ ...query, page: page.value, size: size.value }, domainId.value)
    rows.value = d.items
    total.value = d.total
  } finally {
    loading.value = false
  }
}
function resetQuery() {
  query.keyword = ''
  query.ou = ''
  query.enabled = ''
  page.value = 1
  load()
}
function onPage(p: number) {
  page.value = p
  load()
}

const showMove = ref(false)
const moveTarget = ref('')
const saving = ref(false)
let moveDn = ''
function openMove(row: ComputerItem) {
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
    await moveComputer(encodeDN(moveDn), moveTarget.value, domainId.value)
    ElMessage.success('已移动')
    showMove.value = false
    load()
  } finally {
    saving.value = false
  }
}
async function doEnable(row: ComputerItem) {
  if (!domainId.value) return
  await enableComputer(encodeDN(row.dn), domainId.value)
  ElMessage.success('已启用')
  load()
}
async function doDisable(row: ComputerItem) {
  if (!domainId.value) return
  await disableComputer(encodeDN(row.dn), domainId.value)
  ElMessage.success('已禁用')
  load()
}
async function doDelete(row: ComputerItem) {
  if (!domainId.value) return
  await ElMessageBox.confirm(`确认删除计算机 ${row.sAMAccountName}？`, '警告', { type: 'warning' })
  await deleteComputer(encodeDN(row.dn), domainId.value)
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
</style>

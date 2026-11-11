<template>
  <el-card>
    <template #header>审计日志</template>
    <el-form :inline="true" @submit.prevent>
      <el-form-item label="操作">
        <el-input v-model="filters.action" placeholder="如 user:create" clearable />
      </el-form-item>
      <el-form-item label="对象类型">
        <el-input v-model="filters.object_type" placeholder="user/group/ou" clearable />
      </el-form-item>
      <el-form-item label="操作人">
        <el-input v-model="filters.operator" placeholder="操作人" clearable />
      </el-form-item>
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="名称/DN/参数" clearable />
      </el-form-item>
      <el-form-item label="时间范围">
        <el-date-picker
          v-model="filters.timeRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          clearable
        />
      </el-form-item>
      <el-form-item v-if="!isAuditor" label="域">
        <el-select v-model="filters.domain_id" placeholder="全部域" clearable style="width: 160px" @change="refresh">
          <el-option v-for="d in domains" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="refresh">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
        <el-button @click="exportCsv" :loading="exporting">导出 CSV</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="operator" label="操作人" width="120" />
      <el-table-column prop="action" label="操作" width="170" />
      <el-table-column prop="object_type" label="对象类型" width="110" />
      <el-table-column prop="target_name" label="目标" width="160" />
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.result === 'ok' ? 'success' : 'danger'">{{ row.result }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="详情" width="80">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :page-size="size"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="refresh"
    />

    <el-drawer v-model="detailVisible" title="日志详情" size="440px">
      <el-descriptions :column="1" border v-if="current">
        <el-descriptions-item label="ID">{{ current.id }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ current.operator }}（{{ current.operator_ip }}）</el-descriptions-item>
        <el-descriptions-item label="操作">{{ current.action }}</el-descriptions-item>
        <el-descriptions-item label="对象类型">{{ current.object_type }}</el-descriptions-item>
        <el-descriptions-item label="目标名称">{{ current.target_name }}</el-descriptions-item>
        <el-descriptions-item label="对象 DN">{{ current.object_dn }}</el-descriptions-item>
        <el-descriptions-item label="参数">{{ current.params }}</el-descriptions-item>
        <el-descriptions-item label="结果">{{ current.result }}</el-descriptions-item>
        <el-descriptions-item label="错误信息">{{ current.error_msg || '—' }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatDateTime(current.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { exportAuditLogs, getAuditLog, listAuditLogs, type AuditLog } from '@/api/audit'
import { formatDateTime } from '@/utils/datetime'
import { listDomains, type DomainConfig } from '@/api/domain'
import { useUserStore } from '@/store/user'
import { ROLE_AUDITOR } from '@/utils/roles'

const userStore = useUserStore()
const isAuditor = computed(() => userStore.user?.role === ROLE_AUDITOR)

const domains = ref<DomainConfig[]>([])
const rows = ref<AuditLog[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const filters = reactive({ action: '', object_type: '', operator: '', keyword: '', domain_id: null as number | null, timeRange: null as [string, string] | null })
const exporting = ref(false)
const detailVisible = ref(false)
const current = ref<AuditLog | null>(null)

function resetQuery() {
  filters.action = ''
  filters.object_type = ''
  filters.operator = ''
  filters.keyword = ''
  filters.domain_id = null
  filters.timeRange = null
  page.value = 1
  refresh()
}

async function refresh() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { ...filters, page: page.value, size: size.value }
    delete (params as Record<string, unknown>).timeRange
    if (filters.domain_id == null) delete (params as Record<string, unknown>).domain_id
    if (filters.timeRange) {
      params.start = `${filters.timeRange[0]}T00:00:00`
      params.end = `${filters.timeRange[1]}T23:59:59`
    }
    const r = await listAuditLogs(params)
    rows.value = r.items
    total.value = r.total
  } finally {
    loading.value = false
  }
}

async function openDetail(row: AuditLog) {
  current.value = await getAuditLog(row.id)
  detailVisible.value = true
}

async function exportCsv() {
  exporting.value = true
  try {
    const params: Record<string, unknown> = { ...filters }
    delete (params as Record<string, unknown>).timeRange
    if (filters.domain_id == null) delete (params as Record<string, unknown>).domain_id
    if (filters.timeRange) {
      params.start = `${filters.timeRange[0]}T00:00:00`
      params.end = `${filters.timeRange[1]}T23:59:59`
    }
    const blob = (await exportAuditLogs(params)) as Blob
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  if (!isAuditor.value) {
    try {
      // silent：无域列表权限时（如审计员）403 不弹全局提示
      domains.value = await listDomains(true)
    } catch {
      /* 无域权限时忽略 */
    }
  }
  refresh()
})
</script>

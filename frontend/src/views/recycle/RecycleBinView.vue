<template>
  <el-card>
    <el-alert
      v-if="status && (!status.enabled || !status.functional_level_sufficient)"
      type="warning"
      :closable="false"
      show-icon
      :title="status.message || '域未启用回收站'"
      style="margin-bottom: 12px"
    />
    <el-alert
      v-else-if="status && status.enabled"
      type="success"
      :closable="false"
      show-icon
      title="AD 回收站已启用，可还原已删除对象"
      style="margin-bottom: 12px"
    />

    <div class="toolbar">
      <el-select v-model="typeFilter" placeholder="类型筛选" clearable style="width: 160px" @change="load">
        <el-option label="全部" value="" />
        <el-option label="用户" value="user" />
        <el-option label="组" value="group" />
        <el-option label="OU" value="ou" />
        <el-option label="计算机" value="computer" />
        <el-option label="其他" value="other" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-table :data="pagedItems" v-loading="loading" stripe>
      <el-table-column prop="name" label="原名称" min-width="160" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">{{ typeLabel(row.object_type) }}</template>
      </el-table-column>
      <el-table-column prop="parent" label="原父容器" min-width="260" />
      <el-table-column label="删除时间" width="200">
        <template #default="{ row }">{{ formatDateTime(row.when_deleted) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="!writable || !status?.enabled" @click="doRestore(row)">恢复</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div style="display: flex; justify-content: flex-end; margin-top: 12px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="items.length"
        layout="total, prev, pager, next"
      />
    </div>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="注意：恢复 OU 不会自动级联恢复其子对象（AD 原生行为），子对象需在主控恢复后再逐个恢复。"
      style="margin-top: 12px"
    />
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getRecycleStatus, listDeleted, restoreDeleted, type DeletedItem, type DelType } from '@/api/recyclebin'
import { useDomainStore } from '@/store/domain'
import { useUserStore } from '@/store/user'
import { canWrite } from '@/utils/roles'
import { encodeDN } from '@/utils/dn'
import { formatDateTime } from '@/utils/datetime'

const domainStore = useDomainStore()
const userStore = useUserStore()
const domainId = computed(() => domainStore.currentDomainId ?? 0)
const writable = computed(() => canWrite(userStore.user?.role))

const typeFilter = ref('')
const items = ref<DeletedItem[]>([])
const loading = ref(false)
const status = ref<{ enabled: boolean; functional_level_sufficient: boolean; message: string } | null>(null)
const page = ref(1)
const pageSize = ref(20)
const pagedItems = computed(() => items.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))

const TYPE_LABELS: Record<DelType, string> = {
  user: '用户',
  group: '组',
  ou: 'OU',
  computer: '计算机',
  other: '其他',
}
function typeLabel(t: DelType) {
  return TYPE_LABELS[t] || t
}

async function load() {
  if (!domainId.value) return
  loading.value = true
  page.value = 1
  try {
    const [st, list] = await Promise.all([
      getRecycleStatus(domainId.value),
      listDeleted(domainId.value, typeFilter.value),
    ])
    status.value = st
    items.value = list
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载回收站失败')
  } finally {
    loading.value = false
  }
}

async function doRestore(row: DeletedItem) {
  try {
    await ElMessageBox.confirm(
      `确认将「${row.name}」恢复到原父容器？\n原父容器：${row.parent}`,
      '恢复对象',
      { type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await restoreDeleted(encodeDN(row.dn), domainId.value)
    ElMessage.success('已发起恢复')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '恢复失败')
  }
}

onMounted(load)
watch(domainId, load)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
</style>

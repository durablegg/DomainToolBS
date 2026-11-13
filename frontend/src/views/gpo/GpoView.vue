<template>
  <el-card>
    <el-tabs v-model="tab">
      <el-tab-pane label="GPO 列表" name="list">
        <el-table :data="gpos" v-loading="loadingList" stripe>
          <el-table-column prop="display_name" label="显示名称" min-width="200" />
          <el-table-column prop="guid" label="GUID" min-width="300" />
          <el-table-column prop="when_changed" label="修改时间" width="180" />
          <el-table-column prop="description" label="描述" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="OU 关联 GPO" name="link">
        <el-tree-select
          v-model="selectedOu"
          :data="ouOptions"
          value-key="value"
          :props="{ label: 'label', children: 'children' }"
          check-strictly
          filterable
          clearable
          placeholder="选择 OU"
          style="width: 360px"
          @change="onOuChange"
        />
        <el-alert v-if="!selectedOu" type="info" :closable="false" show-icon title="请先选择 OU" style="margin: 12px 0" />
        <template v-else>
          <div class="toolbar">
            <span>阻止继承：</span>
            <el-switch v-model="blockInheritance" :disabled="!writable" />
            <el-select-v2
              v-model="toAdd"
              :options="visibleAddable"
              :props="{ label: 'display_name', value: 'guid' }"
              multiple
              filterable
              :filter-method="onGpoFilter"
              clearable
              placeholder="添加 GPO 到此 OU（可搜名称/描述/GUID）"
              style="width: 360px"
              @change="onAdd"
            >
              <template #default="{ item }">
                <div class="gpo-opt">
                  <span class="gpo-opt-name">{{ item.display_name }}</span>
                  <span class="gpo-opt-sub">{{ item.description || item.guid }}</span>
                </div>
              </template>
            </el-select-v2>
            <el-button type="primary" :loading="saving" :disabled="!writable" @click="save">保存</el-button>
          </div>
          <div v-if="pendingAdd.length" class="pending-row">
            <span class="pending-label">添加清单：</span>
            <el-tag
              v-for="g in pendingAdd"
              :key="g"
              type="success"
              closable
              @close="undoAdd(g)"
            >{{ gpoName(g) }}</el-tag>
          </div>
          <div v-if="pendingRemove.length" class="pending-row">
            <span class="pending-label">移除清单：</span>
            <el-tag
              v-for="g in pendingRemove"
              :key="g"
              type="danger"
              closable
              @close="undoRemove(g)"
            >{{ gpoName(g) }}</el-tag>
          </div>
          <el-table :data="tableLinks" v-loading="loadingLink" stripe>
            <el-table-column label="GPO" min-width="220">
              <template #default="{ row }">{{ gpoName(row.guid) }}</template>
            </el-table-column>
            <el-table-column prop="guid" label="GUID" min-width="300" />
            <el-table-column label="已禁用" width="90">
              <template #default="{ row }"><el-switch v-model="row.disabled" :disabled="!writable" /></template>
            </el-table-column>
            <el-table-column label="强制(不覆盖)" width="120">
              <template #default="{ row }"><el-switch v-model="row.enforced" :disabled="!writable" /></template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button link type="danger" :disabled="!writable" @click="removeLink(row.guid)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            title="强制(不覆盖)会忽略上层 OU 的“阻止继承”；禁用则该链接不生效。保存后将直接写入 AD。"
            style="margin-top: 12px"
          />
        </template>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listGpos, getOuGplinks, setOuGplinks, type Gpo, type GpoLink } from '@/api/gpo'
import { listOus, type OU } from '@/api/ou'
import { useDomainStore } from '@/store/domain'
import { useUserStore } from '@/store/user'
import { canWrite } from '@/utils/roles'
import { encodeDN } from '@/utils/dn'

const domainStore = useDomainStore()
const userStore = useUserStore()
const domainId = computed(() => domainStore.currentDomainId ?? 0)
const writable = computed(() => canWrite(userStore.user?.role))

const tab = ref('list')
const gpos = ref<Gpo[]>([])
const loadingList = ref(false)
const gpoMap = computed(() => Object.fromEntries(gpos.value.map((g) => [g.guid, g.display_name])))

const ouOptions = ref<{ value: string; label: string; children: any[] }[]>([])
function toOptions(ous: OU[]): any[] {
  return ous.map((o) => ({ value: o.dn, label: o.name, children: toOptions(o.sub_ous || []) }))
}

const selectedOu = ref('')
const prevOu = ref('')
const blockInheritance = ref(false)
const links = ref<GpoLink[]>([])
const loadingLink = ref(false)
const saving = ref(false)
const toAdd = ref<string[]>([])
const pendingAdd = ref<string[]>([])
const pendingRemove = ref<string[]>([])

// 表格显示 = 当前已绑定且未进入移除清单的链接；待添加项只在上方“添加清单”标签显示
const tableLinks = computed(() => links.value.filter((l) => !pendingRemove.value.includes(l.guid)))
// 下拉可选 = 既未绑定、也未进入添加清单的 GPO（按显示名排序）
const addableGpos = computed(() =>
  gpos.value
    .filter((g) => !links.value.some((l) => l.guid === g.guid) && !pendingAdd.value.includes(g.guid))
    .sort((a, b) => a.display_name.localeCompare(b.display_name, 'zh')),
)
// 搜索：匹配名称/描述/GUID（el-select-v2 设了 filter-method 后需自行过滤）
const gpoQuery = ref('')
const visibleAddable = computed(() => {
  const q = gpoQuery.value.trim().toLowerCase()
  if (!q) return addableGpos.value
  return addableGpos.value.filter(
    (g) =>
      g.display_name.toLowerCase().includes(q) ||
      (g.description || '').toLowerCase().includes(q) ||
      g.guid.toLowerCase().includes(q),
  )
})
function onGpoFilter(query: string) {
  gpoQuery.value = query
}
function gpoName(guid: string) {
  return gpoMap.value[guid] || guid
}

async function loadGpos() {
  if (!domainId.value) return
  loadingList.value = true
  try {
    gpos.value = await listGpos(domainId.value)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载 GPO 失败')
  } finally {
    loadingList.value = false
  }
}
async function loadOus() {
  if (!domainId.value) return
  try {
    ouOptions.value = toOptions(await listOus(domainId.value))
  } catch {
    /* 未配置域时忽略 */
  }
}
async function onOuChange() {
  const nextOu = selectedOu.value
  if (pendingAdd.value.length || pendingRemove.value.length) {
    try {
      await ElMessageBox.confirm('切换 OU 将丢弃未保存的增删清单，确定继续？', '提示', {
        type: 'warning',
      })
    } catch {
      selectedOu.value = prevOu.value // 取消则还原选择，保留原 OU 与清单
      return
    }
  }
  prevOu.value = nextOu
  toAdd.value = []
  pendingAdd.value = []
  pendingRemove.value = []
  if (!selectedOu.value) {
    links.value = []
    return
  }
  loadingLink.value = true
  try {
    const r = await getOuGplinks(encodeDN(selectedOu.value), domainId.value)
    links.value = r.links
    blockInheritance.value = r.block_inheritance
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载 OU GPO 失败')
  } finally {
    loadingLink.value = false
  }
}
// 增量添加：只把新选的 GPO 放入“添加清单”，绝不覆盖已有链接；
// 若勾选的项恰在“移除清单”里，则视为撤销移除
function onAdd(val: string[]) {
  for (const guid of val) {
    if (links.value.some((l) => l.guid === guid)) continue
    pendingRemove.value = pendingRemove.value.filter((g) => g !== guid)
    if (!pendingAdd.value.includes(guid)) pendingAdd.value.push(guid)
  }
  toAdd.value = [] // 清空选择器，避免重复添加
}
function removeLink(guid: string) {
  // 仅暂存到“移除清单”，表格按 tableLinks 自动隐藏该行
  if (!pendingRemove.value.includes(guid)) pendingRemove.value.push(guid)
}
function undoAdd(guid: string) {
  pendingAdd.value = pendingAdd.value.filter((g) => g !== guid)
}
function undoRemove(guid: string) {
  pendingRemove.value = pendingRemove.value.filter((g) => g !== guid)
}
async function save() {
  if (!selectedOu.value) return
  if (!pendingAdd.value.length && !pendingRemove.value.length) {
    ElMessage.info('没有待应用的增删变更')
    return
  }
  saving.value = true
  try {
    const finalLinks = links.value
      .filter((l) => !pendingRemove.value.includes(l.guid))
      .map((l) => ({ guid: l.guid, disabled: l.disabled, enforced: l.enforced }))
    for (const guid of pendingAdd.value) {
      finalLinks.push({ guid, disabled: false, enforced: false })
    }
    await setOuGplinks(encodeDN(selectedOu.value), domainId.value, {
      links: finalLinks,
      block_inheritance: blockInheritance.value,
    })
    ElMessage.success('已保存 OU 的 GPO 关联')
    pendingAdd.value = []
    pendingRemove.value = []
    await onOuChange()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadGpos()
  loadOus()
})
watch(domainId, () => {
  loadGpos()
  loadOus()
  selectedOu.value = ''
  links.value = []
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
  flex-wrap: wrap;
}
.pending-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0;
}
.pending-label {
  color: #909399;
  font-size: 13px;
}
</style>

<style>
/* el-select-v2 虚拟列表行高固定 34px，选项必须单行：名称左、副标题右，超长省略 */
.gpo-opt {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  width: 100%;
}
.gpo-opt-name {
  font-size: 14px;
  color: #303133;
  flex-shrink: 0;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gpo-opt-sub {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

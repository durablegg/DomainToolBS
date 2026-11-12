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
            <el-select
              v-model="toAdd"
              multiple
              filterable
              placeholder="添加 GPO 到此 OU"
              style="width: 320px"
              @change="onAdd"
            >
              <el-option v-for="g in addableGpos" :key="g.guid" :label="g.display_name" :value="g.guid" />
            </el-select>
            <el-button type="primary" :loading="saving" :disabled="!writable" @click="save">保存</el-button>
          </div>
          <el-table :data="links" v-loading="loadingLink" stripe>
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
import { ElMessage } from 'element-plus'
import { listGpos, getOuGplinks, setOuGplinks, type Gpo, type GpoLink } from '@/api/gpo'
import { listOus, type OU } from '@/api/ou'
import { useDomainStore } from '@/store/domain'
import { useUserStore } from '@/store/user'
import { canWrite } from '@/utils/roles'
import { encodeDN } from '@/utils/dn'

const domainStore = useDomainStore()
const userStore = useUserStore()
const domainId = computed(() => domainStore.currentDomainId)
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
const blockInheritance = ref(false)
const links = ref<GpoLink[]>([])
const loadingLink = ref(false)
const saving = ref(false)
const toAdd = ref<string[]>([])

const addableGpos = computed(() => gpos.value.filter((g) => !links.value.some((l) => l.guid === g.guid)))
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
  toAdd.value = []
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
function onAdd(val: string[]) {
  for (const guid of val) {
    if (!links.value.some((l) => l.guid === guid)) {
      links.value.push({ guid, dn: '', disabled: false, enforced: false })
    }
  }
  links.value = links.value.filter((l) => val.includes(l.guid))
}
function removeLink(guid: string) {
  links.value = links.value.filter((l) => l.guid !== guid)
}
async function save() {
  if (!selectedOu.value) return
  saving.value = true
  try {
    const payload = {
      links: links.value.map((l) => ({ guid: l.guid, disabled: l.disabled, enforced: l.enforced })),
      block_inheritance: blockInheritance.value,
    }
    await setOuGplinks(encodeDN(selectedOu.value), domainId.value, payload)
    ElMessage.success('已保存 OU 的 GPO 关联')
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
</style>

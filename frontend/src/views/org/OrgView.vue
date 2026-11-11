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
        <span class="tip">组织单元（OU）树 —— 点击节点查看其下的用户 / 计算机 / 组</span>
        <el-button v-if="writable" type="success" @click="showCreate = true">新建 OU</el-button>
      </div>
      <el-tree
        v-loading="loading"
        :data="tree"
        :props="{ label: 'name', children: 'sub_ous' }"
        node-key="dn"
        default-expand-all
        highlight-current
        @current-change="onSelect"
      >
        <template #default="{ data }">
          <span class="ou-node">
            <span>{{ data.name }}</span>
            <span v-if="writable" class="ops">
              <el-button link type="primary" @click.stop="openAddChild(data)">+子OU</el-button>
              <el-button link type="primary" @click.stop="openMove(data)">移动</el-button>
              <el-button link type="danger" @click.stop="doDelete(data)">删除</el-button>
            </span>
          </span>
        </template>
      </el-tree>
    </el-card>

    <el-dialog v-model="showCreate" title="新建 OU" width="460px">
      <el-form :model="ouForm" label-width="90px">
        <el-form-item label="父 OU">
          <el-input :model-value="ouForm.parentLabel" disabled />
        </el-form-item>
        <el-form-item label="名称" required><el-input v-model="ouForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="ouForm.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showMove" title="移动 OU" width="420px">
      <el-tree-select v-model="moveTarget" :data="treeOptions" value-key="value" :props="{ label: 'label', children: 'children' }" check-strictly placeholder="选择目标 OU" />
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
import { createOu, deleteOu, listOus, moveOu, type OU } from '@/api/ou'
import { useDomainStore } from '@/store/domain'
import { useUserStore } from '@/store/user'
import { canWrite } from '@/utils/roles'
import { encodeDN } from '@/utils/dn'

const domainStore = useDomainStore()
const userStore = useUserStore()
const domainId = computed(() => domainStore.currentDomainId)
const writable = computed(() => canWrite(userStore.user?.role))

const tree = ref<OU[]>([])
const loading = ref(false)
const selected = ref<OU | null>(null)

interface OuOpt { value: string; label: string; children: OuOpt[] }
const treeOptions = ref<OuOpt[]>([])
function toOptions(ous: OU[]): OuOpt[] {
  return ous.map((o) => ({ value: o.dn, label: o.name, children: toOptions(o.sub_ous || []) }))
}

async function load() {
  if (!domainId.value) {
    tree.value = []
    treeOptions.value = []
    return
  }
  loading.value = true
  try {
    const ous = await listOus(domainId.value)
    tree.value = ous
    treeOptions.value = toOptions(ous)
  } finally {
    loading.value = false
  }
}
function onSelect(data: OU) {
  selected.value = data
}

const showCreate = ref(false)
const saving = ref(false)
const ouForm = reactive({ parentDn: '', parentLabel: '', name: '', description: '' })
function openAddChild(data: OU) {
  ouForm.parentDn = data.dn
  ouForm.parentLabel = data.name
  ouForm.name = ''
  ouForm.description = ''
  showCreate.value = true
}
async function doCreate() {
  if (!domainId.value) return
  if (!ouForm.parentDn || !ouForm.name) {
    ElMessage.warning('请选择父 OU 并填写名称')
    return
  }
  saving.value = true
  try {
    await createOu({ parent_dn: ouForm.parentDn, name: ouForm.name, description: ouForm.description }, domainId.value)
    ElMessage.success('已创建')
    showCreate.value = false
    load()
  } finally {
    saving.value = false
  }
}

const showMove = ref(false)
const moveTarget = ref('')
let moveDn = ''
function openMove(data: OU) {
  moveDn = data.dn
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
    await moveOu(encodeDN(moveDn), moveTarget.value, domainId.value)
    ElMessage.success('已移动')
    showMove.value = false
    load()
  } finally {
    saving.value = false
  }
}
async function doDelete(data: OU) {
  if (!domainId.value) return
  await ElMessageBox.confirm(`确认删除 OU ${data.name}？`, '警告', { type: 'warning' })
  await deleteOu(encodeDN(data.dn), domainId.value)
  ElMessage.success('已删除')
  load()
}

watch(() => domainStore.currentDomainId, () => load())

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
.ou-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.ops {
  margin-left: 16px;
}
</style>

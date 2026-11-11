<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="isAuditor ? 24 : 8">
        <el-card>
          <template #header>域状态</template>
          <div v-if="info">
            <p>域名：{{ info.domain_name || '—' }}</p>
            <p>Base DN：{{ info.base_dn || '—' }}</p>
            <p>功能级别：{{ info.domain_functional_level || '—' }}</p>
            <p>域控数：{{ (info.domain_controllers || []).length }}</p>
          </div>
          <el-empty v-else :description="isAuditor ? '审计员无目录访问权限，仅可查看审计日志' : '尚未配置域'" />
        </el-card>
      </el-col>
      <el-col v-if="!isAuditor" :span="16">
        <el-card>
          <template #header>快捷入口</template>
          <el-space wrap>
            <el-button type="primary" @click="go('/domain')">域配置</el-button>
            <el-button type="success" @click="go('/org')">组织与用户</el-button>
          </el-space>
          <p style="margin-top: 12px; color: #909399">
            精简版域管平台：管理组织单元、域用户、用户组、计算机账号，并支持批量操作与审计。
          </p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getDomainInfo, type DomainInfo } from '@/api/domain'
import { useDomainStore } from '@/store/domain'
import { useUserStore } from '@/store/user'
import { ROLE_AUDITOR } from '@/utils/roles'

const router = useRouter()
const domainStore = useDomainStore()
const userStore = useUserStore()
const info = ref<DomainInfo | null>(null)
const isAuditor = computed(() => userStore.user?.role === ROLE_AUDITOR)

async function loadInfo() {
  const id = domainStore.currentDomainId
  if (!id || isAuditor.value) {
    info.value = null
    return
  }
  try {
    // silent：无目录权限（如审计员）后端返回 403，页面已有占位，无需全局弹错
    info.value = await getDomainInfo(id, true)
  } catch {
    info.value = null
  }
}

onMounted(loadInfo)
watch(() => domainStore.currentDomainId, loadInfo)

function go(path: string) {
  router.push(path)
}
</script>

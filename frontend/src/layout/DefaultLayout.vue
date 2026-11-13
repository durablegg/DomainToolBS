<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">DomainToolBS</div>
      <el-menu :default-active="activeMenu" router>
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon><span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">{{ currentTitle }}</span>
        <div class="right">
          <el-select
            v-if="!isAuditor"
            v-model="domainStore.currentDomainId"
            placeholder="选择域"
            style="width: 220px"
            @change="onDomainChange"
          >
            <el-option v-for="d in domainStore.domains" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
          <el-tag :type="roleTagType" effect="dark" size="small">{{ roleLabel }}</el-tag>
          <el-dropdown trigger="click" @command="onCommand">
            <span class="user-name">
              {{ userStore.user?.display_name || userStore.user?.username }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="changepwd">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>

    <el-dialog v-model="pwdVisible" title="修改密码" width="440px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="至少 8 位，且包含大写字母、小写字母、数字与符号；不能与当前密码或最近 3 次使用过的密码相同"
        style="margin-bottom: 12px"
      />
      <el-form :model="pwdForm" label-width="90px">
        <el-form-item label="原密码" required>
          <el-input v-model="pwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="pwdForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码" required>
          <el-input v-model="pwdForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdSaving" @click="doChangePwd">保存</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  DataLine,
  Connection,
  Folder,
  User,
  UserFilled,
  Monitor,
  Upload,
  Document,
  Lock,
  Avatar,
  ArrowDown,
  SetUp,
  Delete,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import { useDomainStore } from '@/store/domain'
import { changePassword } from '@/api/auth'
import { ElMessage } from 'element-plus'
import { ROLE_AUDITOR, ROLE_LABELS, ROLE_SUPER } from '@/utils/roles'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const domainStore = useDomainStore()

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => (route.meta.title as string) || '')

const role = computed(() => userStore.user?.role || userStore.role)
const roleLabel = computed(() => (role.value ? ROLE_LABELS[role.value] || role.value : ''))
const roleTagType = computed(() =>
  role.value === ROLE_SUPER ? 'danger' : role.value === 'admin' ? 'warning' : role.value === 'auditor' ? 'success' : 'info',
)
const isAuditor = computed(() => role.value === ROLE_AUDITOR)

interface MenuDef {
  path: string
  title: string
  icon: unknown
  roles: string[]
}
const ALL = ['super_admin', 'admin', 'user', 'auditor']
const MENUS: MenuDef[] = [
  { path: '/dashboard', title: '概览', icon: DataLine, roles: ALL },
  { path: '/domain', title: '域配置', icon: Connection, roles: ['super_admin', 'admin', 'user'] },
  { path: '/org', title: '组织与用户', icon: Folder, roles: ['super_admin', 'admin', 'user'] },
  { path: '/users', title: '域用户', icon: User, roles: ['super_admin', 'admin', 'user'] },
  { path: '/groups', title: '用户组', icon: UserFilled, roles: ['super_admin', 'admin', 'user'] },
  { path: '/computers', title: '计算机', icon: Monitor, roles: ['super_admin', 'admin', 'user'] },
  { path: '/batch', title: '批量任务', icon: Upload, roles: ['super_admin', 'admin'] },
  { path: '/gpo', title: '组策略 GPO', icon: SetUp, roles: ['super_admin', 'admin'] },
  { path: '/recycle', title: '回收站', icon: Delete, roles: ['super_admin', 'admin', 'auditor'] },
  { path: '/audit', title: '审计日志', icon: Document, roles: ['super_admin', 'admin', 'auditor'] },
  { path: '/rbac', title: '授权管理', icon: Lock, roles: ['super_admin'] },
  { path: '/accounts', title: '账户管理', icon: Avatar, roles: ['super_admin'] },
]
const menus = computed(() => MENUS.filter((m) => !role.value || m.roles.includes(role.value)))

function onDomainChange() {
  // 视图各自 watch currentDomainId 重新加载
}

// 修改密码
const pwdVisible = ref(false)
const pwdSaving = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })
function openChangePwd() {
  pwdForm.old_password = ''
  pwdForm.new_password = ''
  pwdForm.confirm = ''
  pwdVisible.value = true
}
// 前端预校验密码策略（与后端一致，最终以后端为准）
function validatePwd(pwd: string): string | null {
  if (pwd.length < 8) return '新密码长度至少 8 位'
  if (!/[a-z]/.test(pwd)) return '新密码必须包含小写字母'
  if (!/[A-Z]/.test(pwd)) return '新密码必须包含大写字母'
  if (!/[0-9]/.test(pwd)) return '新密码必须包含数字'
  if (!/[^A-Za-z0-9]/.test(pwd)) return '新密码必须包含符号'
  return null
}

async function doChangePwd() {
  if (!pwdForm.old_password || !pwdForm.new_password) {
    ElMessage.warning('请填写原密码与新密码')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  const pwdErr = validatePwd(pwdForm.new_password)
  if (pwdErr) {
    ElMessage.warning(pwdErr)
    return
  }
  pwdSaving.value = true
  try {
    await changePassword({ old_password: pwdForm.old_password, new_password: pwdForm.new_password })
    pwdVisible.value = false
    ElMessage.success('密码已修改，请使用新密码重新登录')
    // 改密后作废当前会话，强制重新登录
    userStore.clear()
    router.replace('/login')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '修改失败')
  } finally {
    pwdSaving.value = false
  }
}

// 无操作自动退出：5 分钟无鼠标/键盘活动即清除会话并跳登录
const IDLE_MS = 5 * 60 * 1000
const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click']
let idleTimer: ReturnType<typeof setTimeout> | null = null

function onIdle() {
  if (!userStore.token) return
  userStore.clear()
  ElMessage.warning('长时间未操作，已自动退出，请重新登录')
  router.replace('/login')
}

function resetIdle() {
  if (idleTimer) clearTimeout(idleTimer)
  idleTimer = setTimeout(onIdle, IDLE_MS)
}

onMounted(async () => {
  if (userStore.token && !userStore.user) {
    try {
      await userStore.fetchMe()
    } catch {
      userStore.clear()
    }
  }
  try {
    await domainStore.fetchDomains()
  } catch {
    /* 审计员等无域访问权限时忽略 */
  }
  ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, resetIdle, { passive: true }))
  resetIdle()
})

onUnmounted(() => {
  ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, resetIdle))
  if (idleTimer) clearTimeout(idleTimer)
})

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.clear()
    router.replace('/login')
  } else if (cmd === 'changepwd') {
    openChangePwd()
  }
}
</script>

<style scoped>
.layout {
  height: 100%;
}
.aside {
  background: #001529;
  color: #fff;
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #fff;
  background: #000c17;
}
.aside .el-menu {
  border-right: none;
  background: #001529;
}
.aside .el-menu-item {
  color: #c0c4cc;
}
.aside .el-menu-item.is-active {
  color: #fff;
  background: #1890ff;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}
.title {
  font-weight: 600;
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-name {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}
</style>

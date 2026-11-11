import { createRouter, createWebHistory } from 'vue-router'
import DefaultLayout from '@/layout/DefaultLayout.vue'
import Login from '@/views/Login.vue'

const routes = [
  { path: '/login', component: Login, meta: { public: true } },
  {
    path: '/',
    component: DefaultLayout,
    // 审计员只允许概览/审计日志，默认进审计日志；其余角色进组织与用户
    redirect: () => (sessionStorage.getItem('role') === 'auditor' ? '/audit' : '/org'),
    children: [
      { path: 'dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '概览' } },
      { path: 'domain', component: () => import('@/views/domain/DomainConfig.vue'), meta: { title: '域配置' } },
      { path: 'org', component: () => import('@/views/org/OrgView.vue'), meta: { title: '组织与用户' } },
      { path: 'users', component: () => import('@/views/users/UserView.vue'), meta: { title: '域用户' } },
      { path: 'groups', component: () => import('@/views/groups/GroupView.vue'), meta: { title: '用户组' } },
      { path: 'computers', component: () => import('@/views/computers/ComputerView.vue'), meta: { title: '计算机' } },
      { path: 'batch', component: () => import('@/views/batch/BatchView.vue'), meta: { title: '批量任务' } },
      { path: 'audit', component: () => import('@/views/audit/AuditLogView.vue'), meta: { title: '审计日志' } },
      { path: 'rbac', component: () => import('@/views/rbac/ScopeView.vue'), meta: { title: '授权管理' } },
      { path: 'accounts', component: () => import('@/views/accounts/AccountView.vue'), meta: { title: '账户管理' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 审计员无权访问目录类页面，仅放行概览与审计日志
const AUDITOR_ALLOWED_PATHS = ['/dashboard', '/audit']

router.beforeEach((to) => {
  const token = sessionStorage.getItem('token')
  if (!to.meta.public && !token) return '/login'
  if (to.path === '/login' && token) return '/'
  const role = sessionStorage.getItem('role')
  if (!to.meta.public && role === 'auditor' && !AUDITOR_ALLOWED_PATHS.includes(to.path)) {
    return '/audit'
  }
})

export default router

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMe, type Admin } from '@/api/auth'

// token / role 存 sessionStorage：关闭标签页或浏览器后自动失效，须重新登录
export const useUserStore = defineStore('user', () => {
  const user = ref<Admin | null>(null)
  const token = ref(sessionStorage.getItem('token') || '')
  const role = ref(sessionStorage.getItem('role') || '')

  function setToken(value: string) {
    token.value = value
    sessionStorage.setItem('token', value)
  }

  function setRole(value: string) {
    role.value = value
    sessionStorage.setItem('role', value)
  }

  function clear() {
    token.value = ''
    user.value = null
    role.value = ''
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('role')
  }

  async function fetchMe() {
    user.value = await getMe()
    if (user.value?.role) setRole(user.value.role)
    return user.value
  }

  return { user, token, role, setToken, setRole, clear, fetchMe }
})

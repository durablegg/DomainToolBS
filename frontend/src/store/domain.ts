import { defineStore } from 'pinia'
import { ref } from 'vue'
import { listDomains, type DomainConfig } from '@/api/domain'

const STORAGE_KEY = 'currentDomainId'

export const useDomainStore = defineStore('domain', () => {
  const domains = ref<DomainConfig[]>([])
  const currentDomainId = ref<number | null>(
    Number(localStorage.getItem(STORAGE_KEY)) || null,
  )

  async function fetchDomains() {
    // silent：审计员等无域列表权限时后端返回 403，交由调用方兜底，不弹全局提示
    domains.value = await listDomains(true)
    const valid = domains.value.some((d) => d.id === currentDomainId.value)
    if (!valid) {
      currentDomainId.value = domains.value.length ? domains.value[0].id : null
    }
    if (currentDomainId.value) {
      localStorage.setItem(STORAGE_KEY, String(currentDomainId.value))
    }
  }

  function setCurrent(id: number) {
    currentDomainId.value = id
    localStorage.setItem(STORAGE_KEY, String(id))
  }

  return { domains, currentDomainId, fetchDomains, setCurrent }
})

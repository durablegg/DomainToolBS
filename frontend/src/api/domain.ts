import request from '@/utils/request'

export interface DomainConfig {
  id: number
  name: string
  host: string
  port: number
  use_ssl: boolean
  base_dn: string
  bind_dn: string
  is_default: boolean
  has_password: boolean
  description: string
  ca_cert?: string
  cert_not_after?: string
  cert_trust?: string
  ca_enabled?: boolean
  updated_at?: string
}

export interface DomainBrief {
  id: number
  name: string
  description: string
  base_dn: string
}

export interface TestResult {
  ok: boolean
  message: string
  base_dn?: string
  domain_name?: string
  domain_controllers?: string[]
  cert_not_after?: string
  cert_issuer?: string
  cert_trust?: string
}

export interface DomainInfo {
  domain_name?: string
  base_dn?: string
  configuration_naming_context?: string
  domain_functional_level?: string
  domain_controllers?: string[]
}

// 多域列表（按角色脱敏：普通用户仅返回 DomainBrief 字段子集，但结构兼容 DomainConfig）
export const listDomains = (silent = false) =>
  request.get<DomainConfig[]>('/domains', { silent })
export const getDomain = (id: number) =>
  request.get<DomainConfig>(`/domains/${id}`)
export const createDomain = (data: Record<string, unknown>) =>
  request.post<DomainConfig>('/domains', data)
export const updateDomain = (id: number, data: Record<string, unknown>) =>
  request.put<DomainConfig>(`/domains/${id}`, data)
export const deleteDomain = (id: number) => request.delete(`/domains/${id}`)
export const testDomain = (data: Record<string, unknown>) =>
  request.post<TestResult>('/domains/test', data)
export const testDomainById = (id: number) =>
  request.post<TestResult>(`/domains/${id}/test`)
export const updateDomainCa = (id: number, caCert: string) =>
  request.put<DomainConfig>(`/domains/${id}/ca`, { ca_cert: caCert })
// 超级管理员专用：开启/关闭域的 CA 认证总开关
export const toggleDomainCa = (id: number, enabled: boolean) =>
  request.put<DomainConfig>(`/domains/${id}/ca-mode`, { enabled })
export const getDomainInfo = (id: number, silent = false) =>
  request.get<DomainInfo>(`/domains/${id}/info`, { silent })

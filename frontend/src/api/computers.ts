import request from '@/utils/request'

export interface ComputerItem {
  dn: string
  ou_dn?: string | null
  sAMAccountName?: string
  cn?: string
  displayName?: string
  name?: string
  description?: string
  operatingSystem?: string
  operatingSystemVersion?: string
  dnsHostname?: string | null
  enabled: boolean
  when_created?: string | null
  last_logon?: string | null
}

export interface ComputerPage {
  total: number
  page: number
  size: number
  items: ComputerItem[]
}

export const listComputers = (params: Record<string, unknown>, domainId: number) =>
  request.get<ComputerPage>('/computers', { params: { ...params, domain_id: domainId } })
export const getComputer = (dnB64: string, domainId: number) =>
  request.get<ComputerItem>(`/computers/${dnB64}`, { params: { domain_id: domainId } })
export const enableComputer = (dnB64: string, domainId: number) =>
  request.post(`/computers/${dnB64}/enable`, {}, { params: { domain_id: domainId } })
export const disableComputer = (dnB64: string, domainId: number) =>
  request.post(`/computers/${dnB64}/disable`, {}, { params: { domain_id: domainId } })
export const moveComputer = (dnB64: string, targetOuDn: string, domainId: number) =>
  request.post(`/computers/${dnB64}/move`, { target_ou_dn: targetOuDn }, { params: { domain_id: domainId } })
export const deleteComputer = (dnB64: string, domainId: number) =>
  request.delete(`/computers/${dnB64}`, { params: { domain_id: domainId } })

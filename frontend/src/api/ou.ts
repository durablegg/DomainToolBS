import request from '@/utils/request'

export interface OU {
  dn: string
  name: string
  ou?: string
  description?: string
  parent_dn?: string
  sub_ous: OU[]
  user_count?: number
}

export const listOus = (domainId: number) =>
  request.get<OU[]>('/ous', { params: { domain_id: domainId } })
export const createOu = (data: { parent_dn: string; name: string; description?: string }, domainId: number) =>
  request.post<OU>('/ous', data, { params: { domain_id: domainId } })
export const deleteOu = (dnB64: string, domainId: number) =>
  request.delete(`/ous/${dnB64}`, { params: { domain_id: domainId } })
export const moveOu = (dnB64: string, targetOuDn: string, domainId: number) =>
  request.post<OU>(`/ous/${dnB64}/move`, { target_ou_dn: targetOuDn }, { params: { domain_id: domainId } })

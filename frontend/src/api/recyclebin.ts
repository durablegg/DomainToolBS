import request from '@/utils/request'

export type DelType = 'user' | 'group' | 'ou' | 'computer' | 'other'

export interface DeletedItem {
  dn: string
  name: string
  last_known_rdn: string
  parent: string
  when_deleted: string
  object_type: DelType
}

export interface RecycleStatus {
  enabled: boolean
  functional_level_sufficient: boolean
  message: string
}

export const getRecycleStatus = (domainId: number) =>
  request.get<RecycleStatus>('/recyclebin/status', { params: { domain_id: domainId } })
export const listDeleted = (domainId: number, objectType = '') =>
  request.get<DeletedItem[]>('/recyclebin/deleted', { params: { domain_id: domainId, object_type: objectType } })
export const restoreDeleted = (dnB64: string, domainId: number) =>
  request.post('/recyclebin/restore', { dn: dnB64 }, { params: { domain_id: domainId } })

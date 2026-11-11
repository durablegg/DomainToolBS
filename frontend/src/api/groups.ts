import request from '@/utils/request'

export interface GroupItem {
  dn: string
  sAMAccountName?: string
  cn?: string
  displayName?: string
  name?: string
  mail?: string
  description?: string
  managedBy?: string
  group_type?: number | null
  is_security: boolean
  member_count: number
  when_created?: string | null
}

export interface GroupPage {
  total: number
  page: number
  size: number
  items: GroupItem[]
}

export interface GroupMemberItem {
  dn: string
  sAMAccountName?: string
  displayName?: string
  kind: string
}

export interface GroupMemberPage {
  total: number
  page: number
  size: number
  items: GroupMemberItem[]
}

export const listGroups = (params: Record<string, unknown>, domainId: number) =>
  request.get<GroupPage>('/groups', { params: { ...params, domain_id: domainId } })
export const getGroup = (dnB64: string, domainId: number) =>
  request.get<GroupItem>(`/groups/${dnB64}`, { params: { domain_id: domainId } })
export const createGroup = (data: Record<string, unknown>, domainId: number) =>
  request.post<GroupItem>('/groups', data, { params: { domain_id: domainId } })
export const updateGroup = (dnB64: string, data: Record<string, unknown>, domainId: number) =>
  request.patch<GroupItem>(`/groups/${dnB64}`, data, { params: { domain_id: domainId } })
export const deleteGroup = (dnB64: string, domainId: number) =>
  request.delete(`/groups/${dnB64}`, { params: { domain_id: domainId } })
export const listMembers = (dnB64: string, params: Record<string, unknown> = {}, domainId: number = 0) =>
  request.get<GroupMemberPage>(`/groups/${dnB64}/members`, { params: { ...params, domain_id: domainId } })
export const addMembers = (dnB64: string, members: string[], domainId: number) =>
  request.post(`/groups/${dnB64}/members`, { members }, { params: { domain_id: domainId } })
export const removeMembers = (dnB64: string, members: string[], domainId: number) =>
  request.delete(`/groups/${dnB64}/members`, { data: { members }, params: { domain_id: domainId } })

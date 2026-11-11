import request from '@/utils/request'

export interface UserItem {
  dn: string
  sAMAccountName: string
  cn?: string
  displayName?: string
  name?: string
  mail?: string
  userPrincipalName?: string
  description?: string
  department?: string
  title?: string
  telephoneNumber?: string
  memberOf: string[]
  enabled: boolean
  locked: boolean
  pwd_never_expires: boolean
  pwd_not_required: boolean
  must_change_password: boolean
  pwd_last_set?: string | null
  last_logon?: string | null
  account_expires?: string | null
  when_created?: string | null
}

export interface UserPage {
  total: number
  page: number
  size: number
  items: UserItem[]
}

export const listUsers = (params: Record<string, unknown>, domainId: number) =>
  request.get<UserPage>('/users', { params: { ...params, domain_id: domainId } })
export const getUser = (dnB64: string, domainId: number) =>
  request.get<UserItem>(`/users/${dnB64}`, { params: { domain_id: domainId } })
export const createUser = (data: Record<string, unknown>, domainId: number) =>
  request.post<UserItem>('/users', data, { params: { domain_id: domainId } })
export const updateUser = (dnB64: string, data: Record<string, unknown>, domainId: number) =>
  request.patch<UserItem>(`/users/${dnB64}`, data, { params: { domain_id: domainId } })
export const deleteUser = (dnB64: string, domainId: number) =>
  request.delete(`/users/${dnB64}`, { params: { domain_id: domainId } })
export const enableUser = (dnB64: string, domainId: number) =>
  request.post(`/users/${dnB64}/enable`, {}, { params: { domain_id: domainId } })
export const disableUser = (dnB64: string, domainId: number) =>
  request.post(`/users/${dnB64}/disable`, {}, { params: { domain_id: domainId } })
export const unlockUser = (dnB64: string, domainId: number) =>
  request.post(`/users/${dnB64}/unlock`, {}, { params: { domain_id: domainId } })
export const resetPassword = (
  dnB64: string,
  data: { new_password: string; must_change_next_logon: boolean },
  domainId: number,
) => request.post(`/users/${dnB64}/reset-password`, data, { params: { domain_id: domainId } })
export const moveUser = (dnB64: string, targetOuDn: string, domainId: number) =>
  request.post(`/users/${dnB64}/move`, { target_ou_dn: targetOuDn }, { params: { domain_id: domainId } })

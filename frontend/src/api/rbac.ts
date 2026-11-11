import request from '@/utils/request'

export interface AdminBrief {
  id: number
  username: string
  display_name: string
  role: string
  is_superuser: boolean
  is_active: boolean
}

export interface AdminScope {
  id: number
  admin_id: number
  domain_id: number | null
  base_dn: string
  permissions: string[]
}

export interface PermissionDef {
  key: string
  label: string
}

export interface ResourceDef {
  key: string
  label: string
  actions: PermissionDef[]
}

export interface PermissionsMatrix {
  resources: ResourceDef[]
}

export const getPermissions = () => request.get<PermissionsMatrix>('/rbac/permissions')
export const listAdmins = () => request.get<AdminBrief[]>('/rbac/admins')
export const getScopes = (adminId: number) =>
  request.get<AdminScope[]>(`/rbac/admins/${adminId}/scopes`)
export const putScopes = (
  adminId: number,
  scopes: { domain_id: number; base_dn: string; permissions: string[] }[],
) => request.put<AdminScope[]>(`/rbac/admins/${adminId}/scopes`, { scopes })

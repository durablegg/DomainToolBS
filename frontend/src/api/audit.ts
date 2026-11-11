import request from '@/utils/request'

export interface AuditLog {
  id: number
  operator: string
  operator_ip: string
  action: string
  object_type: string
  object_dn: string
  target_name: string
  params: string
  before: string
  after: string
  result: string
  error_msg: string
  created_at?: string | null
}

export interface AuditPage {
  total: number
  page: number
  size: number
  items: AuditLog[]
}

export const listAuditLogs = (params: Record<string, unknown>) =>
  request.get<AuditPage>('/audit/logs', { params })
export const getAuditLog = (id: number) => request.get<AuditLog>(`/audit/logs/${id}`)

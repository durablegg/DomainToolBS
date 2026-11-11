import request from '@/utils/request'

export interface BatchTask {
  id: number
  type: string
  status: string
  total: number
  ok_count: number
  fail_count: number
  created_by: string
  created_at?: string | null
  finished_at?: string | null
}

export interface BatchTaskItem {
  id: number
  task_id: number
  target_dn: string
  target_name: string
  status: string
  message: string
}

export interface BatchTaskDetail extends BatchTask {
  items: BatchTaskItem[]
}

// 返回 Blob（拦截器已解包为 resp.data）
export const downloadUsersTemplate = () =>
  request.get<Blob>('/batch/template/users', { responseType: 'blob' })
export const downloadDeleteTemplate = () =>
  request.get<Blob>('/batch/template/delete-users', { responseType: 'blob' })
export const downloadUpdateTemplate = () =>
  request.get<Blob>('/batch/template/update-users', { responseType: 'blob' })
export const importUsers = (file: File, targetOuDn: string, domainId: number) => {
  const form = new FormData()
  form.append('file', file)
  form.append('target_ou_dn', targetOuDn)
  form.append('domain_id', String(domainId))
  return request.post<{ task_id: number; total: number }>('/batch/import-users', form)
}
export const deleteUsers = (file: File, domainId: number) => {
  const form = new FormData()
  form.append('file', file)
  form.append('domain_id', String(domainId))
  return request.post<{ task_id: number; total: number }>('/batch/delete-users', form)
}
export const updateUsers = (file: File, domainId: number) => {
  const form = new FormData()
  form.append('file', file)
  form.append('domain_id', String(domainId))
  return request.post<{ task_id: number; total: number }>('/batch/update-users', form)
}
export const exportUsers = (ou: string | undefined, domainId: number) =>
  request.get<Blob>('/batch/export-users', {
    params: { domain_id: domainId, ...(ou ? { ou } : {}) },
    responseType: 'blob',
  })
export const listTasks = () => request.get<BatchTask[]>('/batch/tasks')
export const getTask = (id: number) => request.get<BatchTaskDetail>(`/batch/tasks/${id}`)

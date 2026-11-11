import request from '@/utils/request'

export interface Account {
  id: number
  username: string
  display_name: string
  role: string
  is_superuser: boolean
  is_active: boolean
  created_at?: string
  last_login_at?: string
}

export const listAccounts = () => request.get<Account[]>('/accounts')
export const createAccount = (data: {
  username: string
  password: string
  display_name?: string
  role?: string
}) => request.post<Account>('/accounts', data)
export const getAccount = (id: number) => request.get<Account>(`/accounts/${id}`)
export const updateAccount = (
  id: number,
  data: {
    display_name?: string
    role?: string
    password?: string
    is_active?: boolean
  },
) => request.patch<Account>(`/accounts/${id}`, data)
export const deleteAccount = (id: number) => request.delete(`/accounts/${id}`)

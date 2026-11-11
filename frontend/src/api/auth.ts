import request from '@/utils/request'

export interface Admin {
  id: number
  username: string
  display_name: string
  role: string
  is_superuser: boolean
  is_active: boolean
  scopes: string[]
}

export interface TokenResp {
  access_token: string
  token_type: string
  expires_in: number
  user: Admin
}

export const login = (data: { username: string; password: string }) =>
  request.post<TokenResp>('/auth/login', data, { silent: true })

export const bootstrap = (data: { username: string; password: string; display_name?: string }) =>
  request.post<Admin>('/auth/bootstrap', data)

export const getMe = () => request.get<Admin>('/auth/me')

export const changePassword = (data: { old_password: string; new_password: string }) =>
  request.post('/auth/change-password', data, { silent: true })

export interface ChangePasswordData {
  old_password: string
  new_password: string
}

// 平台四角色常量与辅助
export const ROLE_SUPER = 'super_admin'
export const ROLE_ADMIN = 'admin'
export const ROLE_USER = 'user'
export const ROLE_AUDITOR = 'auditor'

export const ROLE_LABELS: Record<string, string> = {
  [ROLE_SUPER]: '超级管理员',
  [ROLE_ADMIN]: '管理员',
  [ROLE_USER]: '普通用户',
  [ROLE_AUDITOR]: '审计员',
}

export const ASSIGNABLE_ROLES = [ROLE_ADMIN, ROLE_USER, ROLE_AUDITOR]

// 是否拥有目录写权限（超级管理员 + 管理员）
export function canWrite(role?: string | null): boolean {
  return role === ROLE_SUPER || role === ROLE_ADMIN
}

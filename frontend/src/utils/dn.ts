// DN 与 URL-safe base64 互转（与后端 core/dn.py 保持一致）
export function encodeDN(dn: string): string {
  return btoa(unescape(encodeURIComponent(dn)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

export function decodeDN(b64: string): string {
  const padded = b64.replace(/-/g, '+').replace(/_/g, '/')
  return decodeURIComponent(escape(atob(padded)))
}

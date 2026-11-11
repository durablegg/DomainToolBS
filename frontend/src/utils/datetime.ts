/**
 * 把后端返回的 ISO(UTC) 时间字符串格式化为本地时间 `YYYY-MM-DD HH:mm:ss`。
 * - 空值/未登录过（lastLogon 为 0）显示 `—`
 * - 兼容 6 位微秒（部分浏览器不识别，截断到毫秒）
 */
export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  let raw = String(value).replace(/(\.\d{3})\d+/, '$1')
  // 后端 DateTime 列是 naive UTC，序列化后不带时区后缀；
  // new Date 会误按本地时间解析，这里补 'Z' 标记为 UTC 后转换
  if (!/[Zz]$/.test(raw) && !/[+-]\d{2}:?\d{2}$/.test(raw)) {
    raw += 'Z'
  }
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return value
  const p = (n: number) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
    `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  )
}

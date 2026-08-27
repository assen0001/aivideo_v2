/** 通用格式化工具 */

/** 字节 → 可读大小 */
export function formatSize(bytes: number): string {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

/** 2026-08-20 14:22:53 → 08-20 14:22 */
export function formatTime(iso: string): string {
  if (!iso) return '-'
  const s = iso.replace('T', ' ').slice(0, 16)
  return s
}

/** 完整时间 */
export function formatTimeFull(iso: string): string {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 19)
}

/** 相对项目根的产物路径 → 完整 URL（一般后端已返回，此函数兜底） */
export function toFullUrl(url: string): string {
  if (!url) return ''
  if (url.startsWith('http') || url.startsWith('/')) return url
  return `/${url}`
}

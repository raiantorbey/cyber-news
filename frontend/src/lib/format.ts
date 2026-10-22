export function dateLabel(value: string | null, options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' }) {
  if (!value || Number.isNaN(Date.parse(value))) return 'Date unavailable'
  return new Intl.DateTimeFormat(undefined, options).format(new Date(value))
}

export function timeAgo(value: string | null) {
  if (!value || Number.isNaN(Date.parse(value))) return 'Time unavailable'
  const minutes = Math.max(0, Math.floor((Date.now() - Date.parse(value)) / 60_000))
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`
  if (minutes < 10_080) return `${Math.floor(minutes / 1440)}d ago`
  return dateLabel(value, { month: 'short', day: 'numeric' })
}

export const numberLabel = (value: number) => new Intl.NumberFormat(undefined).format(value)
export const titleCase = (value: string) => value.charAt(0).toUpperCase() + value.slice(1).toLowerCase()

export function sourceHealth(source: { enabled: boolean; latest_run_status: string | null; last_success_at: string | null }) {
  if (!source.enabled) return 'Paused'
  if (source.latest_run_status === 'failed') return 'Update failed'
  if (!source.last_success_at || Date.now() - Date.parse(source.last_success_at) > 6 * 3600_000) return 'Awaiting update'
  return 'Up to date'
}

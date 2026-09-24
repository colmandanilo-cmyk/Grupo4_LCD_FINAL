/** Formatos de fechas, numeros y duraciones en espanol (Peru). */

const LOCALE = 'es-PE'

/** El backend envia fechas locales sin zona: "2026-09-24T14:32:10". */
export function parseDate(value) {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDateTime(value) {
  const date = parseDate(value)
  if (!date) return '—'
  return date.toLocaleString(LOCALE, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
}

export function formatDate(value) {
  const date = parseDate(value)
  if (!date) return '—'
  return date.toLocaleDateString(LOCALE, { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function formatTime(value, withSeconds = false) {
  const date = parseDate(value)
  if (!date) return '—'
  return date.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', second: withSeconds ? '2-digit' : undefined, hour12: false })
}

/** "hace 3 min", "hace 2 h"... */
export function timeAgo(value) {
  const date = parseDate(value)
  if (!date) return 'sin datos'
  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (seconds < 10) return 'ahora'
  if (seconds < 60) return `hace ${seconds} s`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `hace ${minutes} min`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `hace ${hours} h`
  return `hace ${Math.round(hours / 24)} días`
}

export function formatNumber(value, decimals = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return Number(value).toLocaleString(LOCALE, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

/** Valor con unidad: formatUnit(42.3, 'ms') -> "42 ms". */
export function formatUnit(value, unit, decimals = 0) {
  if (value === null || value === undefined) return '—'
  return `${formatNumber(value, decimals)} ${unit}`
}

export function formatPercent(value, decimals = 0) {
  if (value === null || value === undefined) return '—'
  return `${formatNumber(value, decimals)} %`
}

/** Horas en texto: 41.2 -> "41 h 12 min". */
export function formatHours(hours) {
  if (hours === null || hours === undefined) return '—'
  const total = Math.round(hours * 60)
  const h = Math.floor(total / 60)
  const m = total % 60
  if (h === 0) return `${m} min`
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

/** Fecha para inputs datetime-local ("2026-09-24T14:30"). */
export function toInputDateTime(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** Fecha para la API ("2026-09-24T14:30:00"). */
export function toApiDateTime(inputValue) {
  if (!inputValue) return undefined
  return inputValue.length === 16 ? `${inputValue}:00` : inputValue
}

export function toInputDate(date) {
  return toInputDateTime(date).slice(0, 10)
}

/** Etiqueta corta de hora para ejes de graficos. */
export function axisTime(value) {
  const date = parseDate(value)
  if (!date) return ''
  return date.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false })
}

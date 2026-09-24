import { Cpu } from 'lucide-react'
import {
  ALERT_STATUS, BATTERY_LEVEL, BATTERY_TREND, COMMAND_STATUS, CONNECTION, DEVICE_STATUS, GENERAL_STATE,
  INCIDENT_STATUS, ROLE, SEVERITY, SITE_STATUS,
} from '../../utils/labels.js'

const MAPS = {
  severity: SEVERITY,
  alertStatus: ALERT_STATUS,
  incidentStatus: INCIDENT_STATUS,
  device: DEVICE_STATUS,
  site: SITE_STATUS,
  general: GENERAL_STATE,
  connection: CONNECTION,
  battery: BATTERY_LEVEL,
  trend: BATTERY_TREND,
  command: COMMAND_STATUS,
  role: ROLE,
}

/**
 * Etiqueta de estado con icono + texto + color (nunca solo color).
 * <StatusBadge kind="severity" value="CRITICA" />
 */
export function StatusBadge({ kind, value, title }) {
  if (value === null || value === undefined) return <span className="muted">—</span>
  const entry = MAPS[kind]?.[value] || { label: value, tone: 'neutral' }
  const Icon = entry.icon
  return (
    <span className={`badge tone-${entry.tone}`} title={title}>
      {Icon && <Icon size={12} strokeWidth={2.5} aria-hidden="true" />}
      {entry.label}
    </span>
  )
}

/** Marca de dato simulado (seccion 57: no presentar valores como hardware real). */
export function SimulatedBadge({ label = 'SIMULADO' }) {
  return (
    <span className="badge tone-sim" title="Valor generado por el simulador con fines demostrativos">
      <Cpu size={12} strokeWidth={2.5} aria-hidden="true" />
      {label}
    </span>
  )
}

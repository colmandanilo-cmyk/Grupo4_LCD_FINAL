import { GENERAL_STATE } from '../../utils/labels.js'

/** Indicador grande ESTADO GENERAL del centro de control (seccion 17). */
export default function GeneralStateIndicator({ state, detail }) {
  const entry = GENERAL_STATE[state] || GENERAL_STATE.NORMAL
  const Icon = entry.icon
  return (
    <div className={`general-state state-${state || 'NORMAL'}`} role="status">
      <div className="gs-icon"><Icon size={24} aria-hidden="true" /></div>
      <div>
        <div className="gs-caption">Estado general</div>
        <div className="gs-label">{entry.label}</div>
        {detail && <div className="gs-detail">{detail}</div>}
      </div>
    </div>
  )
}

/** Texto que explica el estado a partir de las alertas activas por severidad. */
export function stateDetail(bySeverity) {
  if (!bySeverity) return null
  const parts = []
  if (bySeverity.CRITICA) parts.push(`${bySeverity.CRITICA} crítica${bySeverity.CRITICA > 1 ? 's' : ''}`)
  if (bySeverity.ALTA) parts.push(`${bySeverity.ALTA} alta${bySeverity.ALTA > 1 ? 's' : ''}`)
  if (bySeverity.MEDIA) parts.push(`${bySeverity.MEDIA} media${bySeverity.MEDIA > 1 ? 's' : ''}`)
  return parts.length ? `Alertas activas: ${parts.join(', ')}` : 'Sin alertas activas'
}

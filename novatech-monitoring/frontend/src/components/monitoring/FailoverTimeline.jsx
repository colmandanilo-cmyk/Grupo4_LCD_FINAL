import { EVENT_TYPE, SEVERITY } from '../../utils/labels.js'
import { formatDateTime } from '../../utils/format.js'
import { EmptyState } from '../common/Feedback.jsx'

const TONE_BG = {
  critical: ['var(--critical-soft)', 'var(--critical)'],
  serious: ['var(--serious-soft)', 'var(--serious)'],
  warn: ['var(--warn-soft)', 'var(--warn)'],
  ok: ['var(--ok-soft)', 'var(--ok)'],
  info: ['var(--info-soft)', 'var(--brand-dark)'],
  neutral: ['var(--neutral-soft)', 'var(--neutral)'],
}

/**
 * Linea de tiempo de contingencias (seccion 26):
 * "CONEXION STARLINK PERDIDA" -> "ACTIVANDO RESPALDO 4G" -> "CONEXION RESTABLECIDA MEDIANTE 4G".
 */
export default function FailoverTimeline({ events, showSite = false }) {
  if (!events?.length) {
    return <EmptyState title="Sin contingencias registradas" message="Cuando Starlink falle, aquí se verá el paso a 4G de respaldo." />
  }
  return (
    <ul className="timeline">
      {events.map((e) => {
        const type = EVENT_TYPE[e.eventType]
        const Icon = type?.icon
        const tone = e.eventType.includes('RESTORED') ? 'ok' : SEVERITY[e.severity]?.tone || 'neutral'
        const [bg, fg] = TONE_BG[tone] || TONE_BG.neutral
        const lines = e.description.split('. ')
        return (
          <li key={e.id}>
            <span className="tl-icon" style={{ background: bg, color: fg }}>{Icon && <Icon size={15} />}</span>
            <div>
              <div className="tl-time">{formatDateTime(e.timestamp)}{showSite && ` · ${e.siteCode}`} · {type?.label || e.eventType}</div>
              {lines.map((line) => <div key={line} className="tl-text">{line}</div>)}
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/** Barra de progreso con valor en texto. tone: ok | warn | serious | critical | neutral. */
export default function ProgressBar({ value, max = 100, tone = 'info', label, showValue = true }) {
  const safe = value === null || value === undefined ? 0 : Math.max(0, Math.min(max, value))
  return (
    <div className="progress" title={label}>
      <div className="progress-track" role="progressbar" aria-valuenow={Math.round(safe)} aria-valuemin={0} aria-valuemax={max} aria-label={label}>
        <div className={`progress-fill tone-${tone}`} style={{ width: `${(safe / max) * 100}%` }} />
      </div>
      {showValue && <span className="progress-value">{value === null || value === undefined ? '—' : `${Math.round(value)} %`}</span>}
    </div>
  )
}

/** Tono de la barra de bateria segun los umbrales configurados. */
export function batteryTone(percent, low = 35, critical = 20) {
  if (percent === null || percent === undefined) return 'neutral'
  if (percent <= critical) return 'critical'
  if (percent <= low) return 'warn'
  return 'ok'
}

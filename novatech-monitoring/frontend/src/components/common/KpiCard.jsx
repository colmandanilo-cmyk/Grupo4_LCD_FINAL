/** Tarjeta de indicador (KPI) del dashboard. */
export default function KpiCard({ icon: Icon, label, value, suffix, sub, tone = 'info', onClick }) {
  return (
    <div
      className={`kpi${onClick ? ' clickable' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
    >
      {Icon && <div className={`kpi-icon tone-${tone}`}><Icon size={20} aria-hidden="true" /></div>}
      <div>
        <div className="kpi-label">{label}</div>
        <div className="kpi-value">{value}{suffix && <small> {suffix}</small>}</div>
        {sub && <div className="kpi-sub">{sub}</div>}
      </div>
    </div>
  )
}

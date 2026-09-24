import { BatteryCharging, Bell, Cctv, ClipboardList, Satellite, Sun } from 'lucide-react'
import { eventsApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { can } from '../../utils/permissions.js'
import { CONNECTION, EVENT_TYPE } from '../../utils/labels.js'
import { formatDateTime, formatNumber } from '../../utils/format.js'
import KpiCard from '../../components/common/KpiCard.jsx'
import { StatusBadge } from '../../components/common/Badges.jsx'
import { EmptyState } from '../../components/common/Feedback.jsx'
import { batteryTone } from '../../components/common/ProgressBar.jsx'
import DeviceInventory from '../../components/sites/DeviceInventory.jsx'

/** Pestana "Vista general": indicadores de la obra, ultimos eventos e inventario. */
export default function OverviewTab({ detail, onChanged }) {
  const { user, settings } = useAuth()
  const s = detail.site
  const live = detail.live
  const events = usePolling(() => eventsApi.list({ siteId: s.id, size: 8 }), [s.id])
  const connection = CONNECTION[s.activeConnection]

  return (
    <div className="stack">
      <div className="kpi-grid kpi-grid-6" style={{ marginBottom: 0 }}>
        <KpiCard icon={Cctv} label="Cámaras en línea" value={`${s.camerasOnline} / ${s.cameraCount}`} tone={s.camerasOnline === s.cameraCount ? 'ok' : 'serious'} />
        <KpiCard icon={BatteryCharging} label="Batería" value={formatNumber(live?.batteryPercent, 0)} suffix="%"
          tone={batteryTone(live?.batteryPercent, settings.batteryLowThreshold, settings.batteryCriticalThreshold)}
          sub={live?.batteryTrend ? live.batteryTrend.toLowerCase() : null} />
        <KpiCard icon={Sun} label="Generación solar" value={formatNumber(live?.solarGeneration, 0)} suffix="W"
          tone={live?.solarStatus === 'FALLA' ? 'critical' : live?.lowGeneration ? 'warn' : 'info'}
          sub={live?.solarStatus === 'FALLA' ? 'Falla del panel' : live?.lowGeneration ? 'Generación baja' : `Hoy: ${formatNumber(live?.solarEnergyToday, 2)} kWh`} />
        <KpiCard icon={Satellite} label="Conectividad" value={connection?.label || '—'}
          tone={s.activeConnection === 'STARLINK' ? 'ok' : s.activeConnection === 'CELLULAR_4G' ? 'warn' : 'critical'}
          sub={live?.starlinkLatency ? `Latencia ${formatNumber(live.starlinkLatency)} ms` : null} />
        <KpiCard icon={Bell} label="Alertas activas" value={s.activeAlerts} tone={s.activeAlerts ? 'critical' : 'ok'} />
        {can(user, 'incidents') && (
          <KpiCard icon={ClipboardList} label="Incidencias abiertas" value={detail.openIncidents} tone={detail.openIncidents ? 'warn' : 'ok'} />
        )}
      </div>
      <div className="grid grid-main-side">
        <DeviceInventory siteId={s.id} devices={detail.devices} onChanged={onChanged} />
        <div className="card">
          <div className="card-header"><h3>Últimos eventos</h3></div>
          {!events.data?.items?.length ? <EmptyState title="Sin eventos" /> : (
            <ul className="timeline" style={{ padding: '4px 18px' }}>
              {events.data.items.map((e) => {
                const Icon = EVENT_TYPE[e.eventType]?.icon
                return (
                  <li key={e.id}>
                    <span className="tl-icon" style={{ background: 'var(--bg-subtle)', color: 'var(--text-secondary)' }}>{Icon && <Icon size={14} />}</span>
                    <div style={{ flex: 1 }}>
                      <div className="tl-time">{formatDateTime(e.timestamp)} · {e.deviceCode || 'Obra'}</div>
                      <div className="tl-text">{e.description}</div>
                    </div>
                    <StatusBadge kind="severity" value={e.severity} />
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

import { useNavigate } from 'react-router-dom'
import {
  Activity, BatteryCharging, Bell, Building2, Cctv, ClipboardList, LayoutDashboard, Satellite,
} from 'lucide-react'
import { dashboardApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import { useAuth } from '../context/AuthContext.jsx'
import { can } from '../utils/permissions.js'
import { formatDateTime, formatNumber, timeAgo } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import KpiCard from '../components/common/KpiCard.jsx'
import { DataState, EmptyState } from '../components/common/Feedback.jsx'
import { StatusBadge } from '../components/common/Badges.jsx'
import ProgressBar, { batteryTone } from '../components/common/ProgressBar.jsx'
import {
  AlertsTimelineChart, BatteryBySiteChart, CameraStatusChart, ConnectivityChart,
} from '../components/charts/DashboardCharts.jsx'

/** DASHBOARD GENERAL (seccion 14). */
export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const polling = usePolling(() => dashboardApi.summary())

  return (
    <>
      <PageHeader icon={LayoutDashboard} title="DASHBOARD GENERAL"
        subtitle={polling.data ? `Actualizado ${formatDateTime(polling.data.generatedAt)}` : 'Resumen de todas las obras monitoreadas'} />
      <DataState {...polling} onRetry={polling.reload}>
        {(d) => {
          const k = d.kpis
          const availabilityTone = k.availabilityPercent >= 95 ? 'ok' : k.availabilityPercent >= 85 ? 'warn' : 'critical'
          return (
            <>
              <div className="kpi-grid kpi-grid-7">
                <KpiCard icon={Building2} label="Obras monitoreadas" value={k.sitesTotal} sub="Estaciones de vigilancia" onClick={() => navigate('/obras')} />
                <KpiCard icon={Cctv} label="Cámaras operativas" value={`${k.camerasOnline} / ${k.camerasTotal}`}
                  tone={k.camerasOnline === k.camerasTotal ? 'ok' : 'serious'} sub={`${k.camerasTotal - k.camerasOnline} fuera de servicio`} onClick={() => navigate('/camaras')} />
                <KpiCard icon={Activity} label="Disponibilidad" value={formatNumber(k.availabilityPercent, 1)} suffix="%" tone={availabilityTone} sub="Dispositivos operativos" />
                <KpiCard icon={Bell} label="Alertas activas" value={k.activeAlerts} tone={k.activeAlerts ? 'critical' : 'ok'}
                  sub={k.activeAlerts ? 'Requieren atención' : 'Sin alertas pendientes'} onClick={() => navigate('/alertas')} />
                <KpiCard icon={ClipboardList} label="Incidencias críticas" value={k.criticalIncidents} tone={k.criticalIncidents ? 'critical' : 'ok'}
                  sub="Abiertas o en proceso" onClick={can(user, 'incidents') ? () => navigate('/incidencias') : undefined} />
                <KpiCard icon={BatteryCharging} label="Batería promedio" value={formatNumber(k.averageBattery, 0)} suffix="%"
                  tone={batteryTone(k.averageBattery, d.thresholds.batteryLow, d.thresholds.batteryCritical)} onClick={() => navigate('/energia')} />
                <KpiCard icon={Satellite} label="Estado de conectividad" value={`${k.sitesOnStarlink} · ${k.sitesOnCellular} · ${k.sitesWithoutConnection}`}
                  tone={k.sitesWithoutConnection ? 'critical' : k.sitesOnCellular ? 'warn' : 'ok'} sub="Starlink · 4G · sin conexión" onClick={() => navigate('/conectividad')} />
              </div>

              <div className="grid grid-2">
                <div className="card">
                  <div className="card-header"><h2>Estado de cámaras</h2></div>
                  <div className="card-body"><CameraStatusChart counts={d.cameraStatus} /></div>
                </div>
                <div className="card">
                  <div className="card-header"><h2>Alertas últimas 24 horas</h2><span className="card-note">Por hora y severidad</span></div>
                  <div className="card-body"><AlertsTimelineChart buckets={d.alerts24h} /></div>
                </div>
                <div className="card">
                  <div className="card-header"><h2>Batería por obra</h2><span className="card-note">Valores simulados</span></div>
                  <div className="card-body"><BatteryBySiteChart data={d.batteryBySite} low={d.thresholds.batteryLow} critical={d.thresholds.batteryCritical} /></div>
                </div>
                <div className="card">
                  <div className="card-header"><h2>Conectividad</h2><span className="card-note">Obras por conexión activa</span></div>
                  <div className="card-body"><ConnectivityChart counts={d.connectivity} /></div>
                </div>
              </div>

              <div className="grid grid-main-side mt">
                <div className="card">
                  <div className="card-header"><h2>Obras</h2></div>
                  <div className="table-wrap">
                    <table className="table">
                      <thead><tr><th>Obra</th><th>Estado general</th><th>Batería</th><th>Conexión</th><th className="num">Cámaras</th><th className="num">Alertas</th></tr></thead>
                      <tbody>
                        {d.sites.map((s) => (
                          <tr key={s.id} className="clickable" onClick={() => navigate(`/obras/${s.id}`)}>
                            <td><div className="cell-main nowrap">{s.code}</div><div className="cell-sub">{s.name}</div></td>
                            <td><StatusBadge kind="general" value={s.generalState} />{s.dataStale && <div className="cell-sub">Sin datos recientes</div>}</td>
                            <td><ProgressBar value={s.batteryPercent} tone={batteryTone(s.batteryPercent, d.thresholds.batteryLow, d.thresholds.batteryCritical)} label="Batería" /></td>
                            <td><StatusBadge kind="connection" value={s.activeConnection} /></td>
                            <td className="num">{s.camerasOnline}/{s.cameraCount}</td>
                            <td className="num">{s.activeAlerts}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div className="card">
                  <div className="card-header"><h2>Últimas alertas</h2><button type="button" className="btn btn-sm" onClick={() => navigate('/alertas')}>Ver todas</button></div>
                  {d.latestAlerts.length === 0 ? <EmptyState title="Sin alertas" /> : (
                    <ul className="timeline" style={{ padding: '4px 18px' }}>
                      {d.latestAlerts.map((a) => (
                        <li key={a.id}>
                          <div style={{ flex: 1 }}>
                            <div className="row" style={{ justifyContent: 'space-between' }}>
                              <StatusBadge kind="severity" value={a.severity} />
                              <StatusBadge kind="alertStatus" value={a.status} />
                            </div>
                            <div className="tl-text" style={{ marginTop: 4 }}>{a.title}</div>
                            <div className="tl-time">{a.siteCode} · {formatDateTime(a.createdAt)} · {timeAgo(a.createdAt)}</div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </>
          )
        }}
      </DataState>
    </>
  )
}

import { Radio, Satellite } from 'lucide-react'
import { connectivityApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { DataState } from '../common/Feedback.jsx'
import { StatusBadge } from '../common/Badges.jsx'
import ProgressBar from '../common/ProgressBar.jsx'
import SimulatedNotice from '../common/SimulatedNotice.jsx'
import TimeSeriesChart from '../charts/TimeSeriesChart.jsx'
import { COLORS } from '../charts/chartTheme.js'
import { CONNECTION } from '../../utils/labels.js'
import { formatDateTime, formatNumber, timeAgo } from '../../utils/format.js'
import FailoverTimeline from './FailoverTimeline.jsx'

/** Banner grande con la conexion activa (seccion 25). */
export function ActiveConnectionBanner({ value }) {
  const entry = CONNECTION[value] || CONNECTION.NONE
  const Icon = entry.icon
  const stateClass = value === 'STARLINK' ? 'NORMAL' : value === 'CELLULAR_4G' ? 'ADVERTENCIA' : 'CRITICO'
  return (
    <div className={`general-state state-${stateClass}`} role="status">
      <div className="gs-icon"><Icon size={24} /></div>
      <div>
        <div className="gs-caption">Conectividad</div>
        <div className="gs-label">{entry.long}</div>
        <div className="gs-detail">
          {value === 'STARLINK' && 'Conexión principal en funcionamiento. El 4G queda en espera como respaldo.'}
          {value === 'CELLULAR_4G' && 'Starlink no está disponible. El sistema activó automáticamente el respaldo 4G.'}
          {value === 'NONE' && 'Starlink y 4G fuera de servicio. La estación no puede comunicarse.'}
          {!value && 'Esperando datos de la estación.'}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, unit, decimals = 0 }) {
  return (
    <div className="metric-tile">
      <div className="label">{label}</div>
      <div className="value">{value === null || value === undefined ? '—' : formatNumber(value, decimals)} {value !== null && value !== undefined && unit && <small>{unit}</small>}</div>
    </div>
  )
}

/** MODULO DE CONECTIVIDAD de una obra: Starlink, 4G, latencia y contingencias. */
export default function ConnectivityPanel({ siteId }) {
  const current = usePolling(() => connectivityApi.site(siteId), [siteId])
  const history = usePolling(() => connectivityApi.history(siteId, 24), [siteId], { interval: 30000 })
  const timeline = usePolling(() => connectivityApi.timeline(siteId, 15), [siteId])

  return (
    <DataState {...current} onRetry={current.reload}>
      {(c) => (
        <div className="stack">
          <SimulatedNotice />
          <ActiveConnectionBanner value={c.activeConnection} />
          <div className="grid grid-2">
            <div className="card">
              <div className="card-header"><h3><Satellite size={17} /> STARLINK {c.starlinkCode}</h3><StatusBadge kind="device" value={c.starlinkStatus} /></div>
              <div className="card-body stack" style={{ gap: 12 }}>
                <div className="metric-tiles">
                  <Metric label="Latencia simulada" value={c.starlinkLatency} unit="ms" />
                  <Metric label="Descarga simulada" value={c.starlinkDownload} unit="Mbps" />
                  <Metric label="Subida simulada" value={c.starlinkUpload} unit="Mbps" />
                  <Metric label="Pérdida de paquetes" value={c.starlinkPacketLoss} unit="%" decimals={2} />
                </div>
                <span className="card-note">Última comunicación: {formatDateTime(c.starlinkLastSeen)} ({timeAgo(c.starlinkLastSeen)})</span>
              </div>
            </div>
            <div className="card">
              <div className="card-header"><h3><Radio size={17} /> 4G {c.cellularCode}</h3>
                <span className="row">
                  <StatusBadge kind="device" value={c.cellularStatus} />
                  {c.cellularStatus === 'ONLINE' && (
                    <span className={`badge tone-${c.activeConnection === 'CELLULAR_4G' ? 'warn' : 'neutral'}`}>
                      {c.activeConnection === 'CELLULAR_4G' ? 'EN USO' : 'EN ESPERA'}
                    </span>
                  )}
                </span>
              </div>
              <div className="card-body stack" style={{ gap: 12 }}>
                <div>
                  <div className="row" style={{ justifyContent: 'space-between' }}><span>Intensidad de señal</span></div>
                  <ProgressBar value={c.cellularSignal} tone={c.cellularSignal === null ? 'neutral' : c.cellularSignal < 40 ? 'warn' : 'ok'} label="Intensidad 4G" />
                </div>
                <div className="metric-tiles">
                  <Metric label="Latencia simulada" value={c.cellularLatency} unit="ms" />
                  <Metric label="Velocidad bajada" value={c.cellularDownload} unit="Mbps" />
                  <Metric label="Velocidad subida" value={c.cellularUpload} unit="Mbps" />
                </div>
                <span className="card-note">Última comunicación: {formatDateTime(c.cellularLastSeen)} ({timeAgo(c.cellularLastSeen)})</span>
              </div>
            </div>
          </div>
          <div className="grid grid-2">
            <div className="card">
              <div className="card-header"><h3>Latencia (24 horas)</h3></div>
              <div className="card-body">
                <TimeSeriesChart points={history.data} unit="ms" series={[
                  { key: 'starlinkLatency', name: 'Starlink', color: COLORS.series1 },
                  { key: 'cellularLatency', name: '4G', color: COLORS.series2 },
                ]} />
              </div>
            </div>
            <div className="card">
              <div className="card-header"><h3>Contingencias recientes</h3></div>
              <div className="card-body" style={{ maxHeight: 330, overflowY: 'auto' }}>
                <FailoverTimeline events={timeline.data} />
              </div>
            </div>
          </div>
        </div>
      )}
    </DataState>
  )
}

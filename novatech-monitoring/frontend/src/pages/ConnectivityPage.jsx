import { useState } from 'react'
import { Radio, Satellite, WifiOff } from 'lucide-react'
import { connectivityApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import { formatNumber, timeAgo } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import KpiCard from '../components/common/KpiCard.jsx'
import { DataState } from '../components/common/Feedback.jsx'
import { StatusBadge } from '../components/common/Badges.jsx'
import ConnectivityPanel from '../components/monitoring/ConnectivityPanel.jsx'
import FailoverTimeline from '../components/monitoring/FailoverTimeline.jsx'

/** Conectividad de todas las obras: Starlink, 4G y contingencias (secciones 25 y 26). */
export default function ConnectivityPage() {
  const polling = usePolling(() => connectivityApi.overview())
  const [siteId, setSiteId] = useState(null)
  const selected = siteId ?? polling.data?.sites?.[0]?.siteId

  return (
    <>
      <PageHeader icon={Satellite} title="Conectividad" subtitle="Starlink como conexión principal y 4G como respaldo (valores simulados)" />
      <DataState {...polling} onRetry={polling.reload}>
        {(data) => (
          <div className="stack">
            <div className="kpi-grid" style={{ marginBottom: 0 }}>
              <KpiCard icon={Satellite} label="Obras con Starlink" value={data.counts.starlink} tone="ok" />
              <KpiCard icon={Radio} label="Obras con 4G de respaldo" value={data.counts.cellular} tone={data.counts.cellular ? 'warn' : 'ok'} />
              <KpiCard icon={WifiOff} label="Obras sin conexión" value={data.counts.none} tone={data.counts.none ? 'critical' : 'ok'} />
            </div>
            <div className="grid grid-main-side">
              <div className="card">
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Obra</th><th>Conexión activa</th><th>Starlink</th><th className="num">Latencia</th><th>4G</th><th className="num">Señal 4G</th><th>Actualizado</th></tr></thead>
                    <tbody>
                      {data.sites.map((c) => (
                        <tr key={c.siteId} className="clickable" onClick={() => setSiteId(c.siteId)}
                          style={c.siteId === selected ? { boxShadow: 'inset 3px 0 0 var(--brand)' } : undefined}>
                          <td><div className="cell-main nowrap">{c.siteCode}</div><div className="cell-sub">{c.siteName}</div></td>
                          <td><StatusBadge kind="connection" value={c.activeConnection} /></td>
                          <td><StatusBadge kind="device" value={c.starlinkStatus} /></td>
                          <td className="num">{c.starlinkLatency ? `${formatNumber(c.starlinkLatency)} ms` : '—'}</td>
                          <td><StatusBadge kind="device" value={c.cellularStatus} /></td>
                          <td className="num">{c.cellularSignal !== null ? `${c.cellularSignal} %` : '—'}</td>
                          <td className="nowrap">{timeAgo(c.updatedAt)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="card">
                <div className="card-header"><h3>Contingencias en todas las obras</h3></div>
                <div className="card-body" style={{ maxHeight: 300, overflowY: 'auto' }}>
                  <FailoverTimeline events={data.recentEvents} showSite />
                </div>
              </div>
            </div>
            {selected && (
              <>
                <h2 style={{ fontSize: 16 }}>Detalle: {data.sites.find((s) => s.siteId === selected)?.siteCode} · {data.sites.find((s) => s.siteId === selected)?.siteName}</h2>
                <ConnectivityPanel siteId={selected} />
              </>
            )}
          </div>
        )}
      </DataState>
    </>
  )
}

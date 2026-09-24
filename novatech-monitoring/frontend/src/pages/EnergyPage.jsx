import { useState } from 'react'
import { SunDim } from 'lucide-react'
import { energyApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import { useAuth } from '../context/AuthContext.jsx'
import { formatHours, formatNumber } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import { DataState } from '../components/common/Feedback.jsx'
import { StatusBadge } from '../components/common/Badges.jsx'
import ProgressBar, { batteryTone } from '../components/common/ProgressBar.jsx'
import EnergyPanel from '../components/monitoring/EnergyPanel.jsx'

/** Energia de todas las obras y detalle de la obra elegida (seccion 22). */
export default function EnergyPage() {
  const { settings } = useAuth()
  const polling = usePolling(() => energyApi.overview())
  const [siteId, setSiteId] = useState(null)
  const selected = siteId ?? polling.data?.[0]?.siteId

  return (
    <>
      <PageHeader icon={SunDim} title="Energía" subtitle="Panel solar, batería y consumo de cada estación (valores simulados)" />
      <DataState {...polling} onRetry={polling.reload}>
        {(sites) => (
          <div className="stack">
            <div className="card">
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>Obra</th><th>Batería</th><th>Nivel</th><th>Estado</th><th className="num">Generación</th><th className="num">Consumo</th><th className="num">Autonomía</th><th>Panel</th></tr>
                  </thead>
                  <tbody>
                    {sites.map((e) => (
                      <tr key={e.siteId} className="clickable" onClick={() => setSiteId(e.siteId)}
                        style={e.siteId === selected ? { boxShadow: 'inset 3px 0 0 var(--brand)' } : undefined}>
                        <td><div className="cell-main nowrap">{e.siteCode}</div><div className="cell-sub">{e.siteName}</div></td>
                        <td><ProgressBar value={e.batteryPercent} tone={batteryTone(e.batteryPercent, settings.batteryLowThreshold, settings.batteryCriticalThreshold)} label="Batería" /></td>
                        <td><StatusBadge kind="battery" value={e.batteryLevel} /></td>
                        <td><StatusBadge kind="trend" value={e.batteryTrend} /></td>
                        <td className="num">{formatNumber(e.solarGeneration)} W</td>
                        <td className="num">{formatNumber(e.consumption)} W</td>
                        <td className="num">{formatHours(e.estimatedAutonomy)}</td>
                        <td>{e.solarStatus === 'FALLA' ? <StatusBadge kind="device" value="FALLA" /> : e.lowGeneration ? <span className="badge tone-warn">NUBLADO</span> : <StatusBadge kind="device" value={e.solarStatus} />}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            {selected && (
              <>
                <h2 style={{ fontSize: 16 }}>Detalle: {sites.find((s) => s.siteId === selected)?.siteCode} · {sites.find((s) => s.siteId === selected)?.siteName}</h2>
                <EnergyPanel siteId={selected} />
              </>
            )}
          </div>
        )}
      </DataState>
    </>
  )
}

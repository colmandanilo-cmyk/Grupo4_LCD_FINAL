import { BatteryCharging, Gauge, Sun, Zap } from 'lucide-react'
import { energyApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { DataState } from '../common/Feedback.jsx'
import { StatusBadge } from '../common/Badges.jsx'
import ProgressBar, { batteryTone } from '../common/ProgressBar.jsx'
import SimulatedNotice from '../common/SimulatedNotice.jsx'
import { BatteryHistoryChart, SolarConsumptionChart } from '../charts/EnergyCharts.jsx'
import { formatHours, formatNumber, formatUnit, parseDate, timeAgo } from '../../utils/format.js'

/** Estado del panel solar en texto. */
function solarState(e) {
  if (e.solarStatus === 'FALLA') return { text: 'FALLA DEL PANEL', tone: 'critical' }
  if (e.lowGeneration) return { text: 'GENERACIÓN BAJA (NUBLADO)', tone: 'warn' }
  const hour = parseDate(e.deviceTime)?.getHours()
  if (!e.solarGeneration && hour !== undefined && (hour < 6 || hour >= 18)) return { text: 'SIN SOL (NOCHE)', tone: 'neutral' }
  return { text: 'OPERATIVO', tone: 'ok' }
}

/** MODULO DE ENERGIA de una obra (seccion 22): panel solar, bateria, consumo y graficos. */
export default function EnergyPanel({ siteId }) {
  const { settings } = useAuth()
  const current = usePolling(() => energyApi.site(siteId), [siteId])
  const history = usePolling(() => energyApi.history(siteId, 24), [siteId], { interval: 30000 })
  const low = settings.batteryLowThreshold
  const critical = settings.batteryCriticalThreshold

  return (
    <DataState {...current} onRetry={current.reload}>
      {(e) => {
        const solar = solarState(e)
        const consumptionParts = [
          { label: 'Cámaras', value: e.consumptionCameras },
          { label: 'Conectividad', value: e.consumptionConnectivity },
          { label: 'Sistema de control', value: e.consumptionControl },
        ]
        return (
          <div className="stack">
            <SimulatedNotice />
            {e.dataStale && (
              <div className="inline-alert tone-warn">Sin datos recientes: la última lectura fue {timeAgo(e.updatedAt)}.</div>
            )}
            <div className="grid grid-3">
              <div className="card">
                <div className="card-header"><h3><Sun size={17} /> Panel solar {e.solarPanelCode}</h3>
                  <span className={`badge tone-${solar.tone}`}>{solar.text}</span></div>
                <div className="card-body metric-tiles">
                  <div className="metric-tile"><div className="label">Potencia simulada</div><div className="value">{formatNumber(e.solarRatedPower)} <small>W</small></div></div>
                  <div className="metric-tile"><div className="label">Generación actual</div><div className="value">{formatNumber(e.solarGeneration)} <small>W</small></div></div>
                  <div className="metric-tile"><div className="label">Producción del día</div><div className="value">{formatNumber(e.solarEnergyToday, 2)} <small>kWh</small></div></div>
                </div>
              </div>
              <div className="card">
                <div className="card-header"><h3><BatteryCharging size={17} /> Batería {e.batteryCode}</h3>
                  <span className="row"><StatusBadge kind="battery" value={e.batteryLevel} /><StatusBadge kind="trend" value={e.batteryTrend} /></span></div>
                <div className="card-body stack" style={{ gap: 12 }}>
                  <ProgressBar value={e.batteryPercent} tone={batteryTone(e.batteryPercent, low, critical)} label="Nivel de batería" />
                  <div className="metric-tiles">
                    <div className="metric-tile"><div className="label">Voltaje simulado</div><div className="value">{formatNumber(e.batteryVoltage, 1)} <small>V</small></div></div>
                    <div className="metric-tile"><div className="label">Consumo</div><div className="value">{formatNumber(e.consumption)} <small>W</small></div></div>
                    <div className="metric-tile"><div className="label">Autonomía estimada</div><div className="value" style={{ fontSize: 16 }}>{formatHours(e.estimatedAutonomy)}</div></div>
                  </div>
                </div>
              </div>
              <div className="card">
                <div className="card-header"><h3><Zap size={17} /> Consumo</h3><span className="secondary tabular">{formatUnit(e.consumption, 'W')}</span></div>
                <div className="card-body stack" style={{ gap: 12 }}>
                  {consumptionParts.map((part) => (
                    <div key={part.label}>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <span>{part.label}</span><strong className="tabular">{formatUnit(part.value, 'W')}</strong>
                      </div>
                      <ProgressBar value={e.consumption ? (part.value / e.consumption) * 100 : 0} tone="neutral" showValue={false} label={part.label} />
                    </div>
                  ))}
                  <span className="card-note"><Gauge size={12} /> Consumo aproximado simulado de la estación.</span>
                </div>
              </div>
            </div>
            <div className="grid grid-2">
              <div className="card">
                <div className="card-header"><h3>NIVEL DE BATERÍA</h3><span className="card-note">Últimas 24 horas</span></div>
                <div className="card-body">
                  <BatteryHistoryChart points={history.data} low={low} critical={critical} />
                </div>
              </div>
              <div className="card">
                <div className="card-header"><h3>GENERACIÓN SOLAR VS CONSUMO</h3><span className="card-note">Últimas 24 horas</span></div>
                <div className="card-body">
                  <SolarConsumptionChart points={history.data} />
                </div>
              </div>
            </div>
          </div>
        )
      }}
    </DataState>
  )
}

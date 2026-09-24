import { useEffect, useMemo, useState } from 'react'
import { telemetryApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { METRIC } from '../../utils/labels.js'
import { formatDateTime, formatNumber } from '../../utils/format.js'
import { DataState, EmptyState } from '../../components/common/Feedback.jsx'
import SimulatedNotice from '../../components/common/SimulatedNotice.jsx'
import TimeSeriesChart from '../../components/charts/TimeSeriesChart.jsx'

/** Pestana "Telemetria" (seccion 36): grafico de una metrica y ultimos registros guardados. */
export default function TelemetryTab({ siteId }) {
  const [metrics, setMetrics] = useState([])
  const [selected, setSelected] = useState('')
  const [hours, setHours] = useState(24)

  useEffect(() => {
    telemetryApi.metrics(siteId).then((list) => {
      setMetrics(list)
      if (list.length) setSelected((current) => current || `${list[0].deviceId}|${list[0].metric}`)
    }).catch(() => setMetrics([]))
  }, [siteId])

  const [deviceId, metric] = selected ? selected.split('|') : [null, null]
  const series = usePolling(() => (deviceId ? telemetryApi.series(deviceId, metric, hours) : Promise.resolve(null)),
    [deviceId, metric, hours], { interval: 30000 })
  const latest = usePolling(() => telemetryApi.latest(siteId, 60), [siteId])
  const current = useMemo(() => metrics.find((m) => `${m.deviceId}|${m.metric}` === selected), [metrics, selected])

  return (
    <div className="stack">
      <SimulatedNotice />
      <div className="card">
        <div className="card-header">
          <h3>Serie de telemetría</h3>
          <div className="row">
            <select className="select" style={{ width: 'auto' }} value={selected} onChange={(e) => setSelected(e.target.value)} aria-label="Métrica">
              {metrics.map((m) => (
                <option key={`${m.deviceId}|${m.metric}`} value={`${m.deviceId}|${m.metric}`}>
                  {m.deviceCode} ({m.deviceName}) · {METRIC[m.metric] || m.metric}
                </option>
              ))}
            </select>
            <select className="select" style={{ width: 'auto' }} value={hours} onChange={(e) => setHours(Number(e.target.value))} aria-label="Período">
              <option value={6}>Últimas 6 h</option><option value={24}>Últimas 24 h</option><option value={72}>Últimos 3 días</option>
            </select>
          </div>
        </div>
        <div className="card-body">
          {!metrics.length ? <EmptyState title="Sin telemetría" message="Esta obra todavía no registró mediciones." /> : (
            <TimeSeriesChart points={series.data?.points} unit={series.data?.unit === 'estado' ? '' : series.data?.unit}
              step={current?.metric === 'online'} domain={current?.metric === 'online' ? [0, 1] : series.data?.unit === '%' ? [0, 100] : undefined}
              series={[{ key: 'value', name: METRIC[current?.metric] || current?.metric }]} />
          )}
        </div>
      </div>
      <div className="card">
        <div className="card-header"><h3>Últimos registros guardados</h3><span className="card-note">Se guarda un registro según la frecuencia de telemetría configurada</span></div>
        <DataState {...latest} onRetry={latest.reload}>
          {(rows) => rows.length === 0 ? <EmptyState title="Sin registros" /> : (
            <div className="table-wrap" style={{ maxHeight: 420 }}>
              <table className="table">
                <thead><tr><th>Fecha y hora</th><th>Dispositivo</th><th>Métrica</th><th className="num">Valor</th><th>Unidad</th></tr></thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={`${r.timestamp}-${r.deviceCode}-${r.metric}-${i}`}>
                      <td className="nowrap tabular">{formatDateTime(r.timestamp)}</td>
                      <td>{r.deviceCode}<div className="cell-sub">{r.deviceName}</div></td>
                      <td>{METRIC[r.metric] || r.metric}</td>
                      <td className="num">{r.unit === 'estado' ? (r.value === 1 ? 'En línea' : 'Fuera de línea') : formatNumber(r.value, r.unit === 'V' ? 2 : 1)}</td>
                      <td>{r.unit === 'estado' ? '—' : r.unit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </div>
    </div>
  )
}

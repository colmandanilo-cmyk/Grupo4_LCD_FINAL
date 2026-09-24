import { useState } from 'react'
import { History } from 'lucide-react'
import { eventsApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { EVENT_TYPE, SEVERITY } from '../../utils/labels.js'
import { formatDateTime } from '../../utils/format.js'
import { StatusBadge } from '../common/Badges.jsx'
import { DataState, EmptyState } from '../common/Feedback.jsx'
import Pagination from '../common/Pagination.jsx'

/** Historial de eventos (seccion 27) con filtros por tipo y severidad. */
export default function EventsTable({ siteId, pageSize = 20 }) {
  const [type, setType] = useState('')
  const [severity, setSeverity] = useState('')
  const [page, setPage] = useState(0)
  const polling = usePolling(
    () => eventsApi.list({ siteId, type: type || undefined, severity: severity || undefined, page, size: pageSize }),
    [siteId, type, severity, page, pageSize],
  )

  return (
    <>
      <div className="filters">
        <select className="select" value={type} onChange={(e) => { setType(e.target.value); setPage(0) }} aria-label="Filtrar por tipo">
          <option value="">Todos los tipos</option>
          {Object.entries(EVENT_TYPE).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className="select" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(0) }} aria-label="Filtrar por severidad">
          <option value="">Todas las severidades</option>
          {Object.entries(SEVERITY).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      <div className="card">
        <DataState {...polling} onRetry={polling.reload}>
          {(result) => result.items.length === 0 ? (
            <EmptyState icon={History} title="Sin eventos" message="No hay eventos con estos filtros." />
          ) : (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>Fecha y hora</th>{!siteId && <th>Obra</th>}<th>Dispositivo</th><th>Tipo</th><th>Descripción</th><th>Severidad</th></tr>
                  </thead>
                  <tbody>
                    {result.items.map((e) => {
                      const Icon = EVENT_TYPE[e.eventType]?.icon
                      return (
                        <tr key={e.id}>
                          <td className="nowrap tabular">{formatDateTime(e.timestamp)}</td>
                          {!siteId && <td>{e.siteCode}</td>}
                          <td>{e.deviceCode || 'Obra'}<div className="cell-sub">{e.deviceName}</div></td>
                          <td className="nowrap">{Icon && <Icon size={14} style={{ verticalAlign: -2, marginRight: 6 }} />}{EVENT_TYPE[e.eventType]?.label || e.eventType}</td>
                          <td>{e.description}</td>
                          <td><StatusBadge kind="severity" value={e.severity} /></td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination page={result.page} size={result.size} total={result.total} onChange={setPage} />
            </>
          )}
        </DataState>
      </div>
    </>
  )
}

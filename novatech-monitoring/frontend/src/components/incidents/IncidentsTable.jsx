import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ClipboardList, Plus } from 'lucide-react'
import { incidentsApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { INCIDENT_STATUS, SEVERITY } from '../../utils/labels.js'
import { formatDateTime } from '../../utils/format.js'
import { StatusBadge } from '../common/Badges.jsx'
import { DataState, EmptyState } from '../common/Feedback.jsx'
import IncidentDetailModal from './IncidentDetailModal.jsx'
import IncidentFormModal from './IncidentFormModal.jsx'

/** Tabla de incidencias (seccion 31) con filtros, alta manual y detalle. */
export default function IncidentsTable({ siteId }) {
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [selected, setSelected] = useState(null)
  const [creating, setCreating] = useState(false)
  const polling = usePolling(
    () => incidentsApi.list({ siteId, status: status || undefined, priority: priority || undefined }),
    [siteId, status, priority],
  )

  return (
    <>
      <div className="filters">
        <select className="select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filtrar por estado">
          <option value="">Todos los estados</option>
          {Object.entries(INCIDENT_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className="select" value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Filtrar por prioridad">
          <option value="">Todas las prioridades</option>
          {['CRITICA', 'ALTA', 'MEDIA', 'BAJA'].map((k) => <option key={k} value={k}>{SEVERITY[k].label}</option>)}
        </select>
        <div style={{ flex: 1 }} />
        <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}><Plus size={15} /> Nueva incidencia</button>
      </div>
      <div className="card">
        <DataState {...polling} onRetry={polling.reload}>
          {(items) => items.length === 0 ? (
            <EmptyState icon={ClipboardList} title="No hay incidencias" message="No hay incidencias con estos filtros." />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Código</th>
                    {!siteId && <th>Obra</th>}
                    <th>Título</th>
                    <th>Prioridad</th>
                    <th>Estado</th>
                    <th>Responsable</th>
                    <th>Fechas</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i) => (
                    <tr key={i.id} className="clickable" onClick={() => setSelected(i.id)}>
                      <td className="cell-main nowrap">{i.code}</td>
                      {!siteId && <td><Link className="nowrap" to={`/obras/${i.siteId}?tab=incidencias`} onClick={(e) => e.stopPropagation()}>{i.siteCode}</Link></td>}
                      <td style={{ maxWidth: 340 }}><div className="cell-main">{i.title}</div>{i.alertId && <div className="cell-sub">Desde la alerta #{i.alertId}</div>}</td>
                      <td><StatusBadge kind="severity" value={i.priority} /></td>
                      <td><StatusBadge kind="incidentStatus" value={i.status} /></td>
                      <td>{i.assignedToName || '—'}</td>
                      <td className="nowrap">
                        <div>Apertura: {formatDateTime(i.createdAt)}</div>
                        {i.resolvedAt && <div className="cell-sub">Resolución: {formatDateTime(i.resolvedAt)}</div>}
                        {i.closedAt && <div className="cell-sub">Cierre: {formatDateTime(i.closedAt)}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </div>
      {selected && <IncidentDetailModal incidentId={selected} onClose={() => setSelected(null)} onChanged={polling.reload} />}
      {creating && <IncidentFormModal siteId={siteId} onClose={() => setCreating(false)} onSaved={polling.reload} />}
    </>
  )
}

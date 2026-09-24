import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, ClipboardPlus, CheckCheck } from 'lucide-react'
import { alertsApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useToast } from '../../context/ToastContext.jsx'
import { can } from '../../utils/permissions.js'
import { ALERT_STATUS, SEVERITY } from '../../utils/labels.js'
import { formatDateTime, timeAgo } from '../../utils/format.js'
import { StatusBadge } from '../common/Badges.jsx'
import { DataState, EmptyState } from '../common/Feedback.jsx'
import Pagination from '../common/Pagination.jsx'
import ResolveAlertModal from './ResolveAlertModal.jsx'
import IncidentFormModal from '../incidents/IncidentFormModal.jsx'

/**
 * Tabla de alertas (seccion 30) con filtros, paginacion y acciones:
 * Reconocer (todos), Crear incidencia y Resolver (administrador y supervisor).
 */
export default function AlertsTable({ siteId, defaultStatus = 'ACTIVAS', pageSize = 15 }) {
  const { user } = useAuth()
  const toast = useToast()
  const [status, setStatus] = useState(defaultStatus)
  const [severity, setSeverity] = useState('')
  const [page, setPage] = useState(0)
  const [resolving, setResolving] = useState(null)
  const [creatingFrom, setCreatingFrom] = useState(null)
  const [busy, setBusy] = useState(null)

  const polling = usePolling(
    () => alertsApi.list({ siteId, status: status || undefined, severity: severity || undefined, page, size: pageSize }),
    [siteId, status, severity, page, pageSize],
  )

  const acknowledge = async (alert) => {
    setBusy(alert.id)
    try {
      await alertsApi.acknowledge(alert.id)
      toast.success(`Reconociste la alerta "${alert.title}".`, 'Alerta reconocida')
      polling.reload()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setBusy(null)
    }
  }

  const changeFilter = (setter) => (e) => {
    setter(e.target.value)
    setPage(0)
  }

  return (
    <>
      <div className="filters">
        <select className="select" value={status} onChange={changeFilter(setStatus)} aria-label="Filtrar por estado">
          <option value="ACTIVAS">Activas (sin resolver)</option>
          <option value="">Todas</option>
          {Object.entries(ALERT_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className="select" value={severity} onChange={changeFilter(setSeverity)} aria-label="Filtrar por severidad">
          <option value="">Todas las severidades</option>
          {['CRITICA', 'ALTA', 'MEDIA', 'BAJA'].map((k) => <option key={k} value={k}>{SEVERITY[k].label}</option>)}
        </select>
      </div>
      <div className="card">
        <DataState {...polling} onRetry={polling.reload}>
          {(result) => result.items.length === 0 ? (
            <EmptyState icon={CheckCircle2} title="No hay alertas" message={status === 'ACTIVAS' ? 'No hay alertas activas con estos filtros.' : 'No hay alertas con estos filtros.'} />
          ) : (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      {!siteId && <th>Obra</th>}
                      <th>Dispositivo</th>
                      <th>Alerta</th>
                      <th>Severidad</th>
                      <th>Estado</th>
                      <th>Responsable</th>
                      <th className="num">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.items.map((a) => (
                      <tr key={a.id}>
                        <td className="nowrap"><div>{formatDateTime(a.createdAt)}</div><div className="cell-sub">{timeAgo(a.createdAt)}</div></td>
                        {!siteId && <td><Link className="nowrap" to={`/obras/${a.siteId}?tab=alertas`}>{a.siteCode}</Link><div className="cell-sub">{a.siteName}</div></td>}
                        <td>{a.deviceCode || '—'}<div className="cell-sub">{a.deviceName}</div></td>
                        <td style={{ minWidth: 240, maxWidth: 380 }}>
                          <div className="cell-main">{a.title}</div>
                          <div className="cell-sub">{a.description}</div>
                          {a.resolutionNote && <div className="cell-sub">Resolución: {a.resolutionNote}</div>}
                          {a.incidentCode && <div className="cell-sub">Incidencia {a.incidentCode}</div>}
                        </td>
                        <td><StatusBadge kind="severity" value={a.severity} /></td>
                        <td><StatusBadge kind="alertStatus" value={a.status} /></td>
                        <td>
                          {a.responsibleName || (a.status === 'RESUELTA' && !a.resolvedByName ? 'Sistema' : '—')}
                          {a.resolvedAt && <div className="cell-sub">Resuelta {formatDateTime(a.resolvedAt)}{a.resolvedByName ? ` por ${a.resolvedByName}` : ''}</div>}
                          {!a.resolvedAt && a.acknowledgedAt && <div className="cell-sub">Reconocida {formatDateTime(a.acknowledgedAt)}{a.acknowledgedByName ? ` por ${a.acknowledgedByName}` : ''}</div>}
                        </td>
                        <td>
                          <div className="actions actions-stack">
                            {a.status === 'NUEVA' && can(user, 'acknowledgeAlert') && (
                              <button type="button" className="btn btn-sm" disabled={busy === a.id} onClick={() => acknowledge(a)}>
                                <CheckCircle2 size={14} /> Reconocer
                              </button>
                            )}
                            {a.status !== 'RESUELTA' && !a.incidentId && can(user, 'incidents') && (
                              <button type="button" className="btn btn-sm" onClick={() => setCreatingFrom(a)}>
                                <ClipboardPlus size={14} /> Crear incidencia
                              </button>
                            )}
                            {a.status !== 'RESUELTA' && can(user, 'resolveAlert') && (
                              <button type="button" className="btn btn-sm btn-success" onClick={() => setResolving(a)}>
                                <CheckCheck size={14} /> Resolver
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={result.page} size={result.size} total={result.total} onChange={setPage} />
            </>
          )}
        </DataState>
      </div>
      {resolving && <ResolveAlertModal alert={resolving} onClose={() => setResolving(null)} onDone={polling.reload} />}
      {creatingFrom && (
        <IncidentFormModal alert={creatingFrom} onClose={() => setCreatingFrom(null)} onSaved={polling.reload} />
      )}
    </>
  )
}

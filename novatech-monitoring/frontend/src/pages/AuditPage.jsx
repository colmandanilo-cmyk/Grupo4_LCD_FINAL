import { useEffect, useState } from 'react'
import { ScrollText } from 'lucide-react'
import { auditApi, usersApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import { formatDateTime, toApiDateTime } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import { DataState, EmptyState } from '../components/common/Feedback.jsx'
import Pagination from '../components/common/Pagination.jsx'

/** REGISTRO DE AUDITORIA (seccion 44). Solo administrador. */
export default function AuditPage() {
  const [users, setUsers] = useState([])
  const [actions, setActions] = useState([])
  const [filters, setFilters] = useState({ userId: '', action: '', from: '', to: '' })
  const [page, setPage] = useState(0)

  useEffect(() => {
    usersApi.list().then(setUsers).catch(() => setUsers([]))
    auditApi.actions().then(setActions).catch(() => setActions([]))
  }, [])

  const polling = usePolling(() => auditApi.list({
    userId: filters.userId || undefined, action: filters.action || undefined,
    from: toApiDateTime(filters.from), to: toApiDateTime(filters.to), page, size: 25,
  }), [filters, page])

  const set = (field) => (e) => {
    setFilters((f) => ({ ...f, [field]: e.target.value }))
    setPage(0)
  }

  return (
    <>
      <PageHeader icon={ScrollText} title="REGISTRO DE AUDITORÍA" subtitle="Acciones importantes realizadas en la plataforma" />
      <div className="filters">
        <select className="select" value={filters.userId} onChange={set('userId')} aria-label="Usuario">
          <option value="">Todos los usuarios</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select>
        <select className="select" value={filters.action} onChange={set('action')} aria-label="Acción">
          <option value="">Todas las acciones</option>
          {actions.map((a) => <option key={a} value={a}>{a.replaceAll('_', ' ')}</option>)}
        </select>
        <label className="row">Desde <input type="datetime-local" className="input" value={filters.from} onChange={set('from')} /></label>
        <label className="row">Hasta <input type="datetime-local" className="input" value={filters.to} onChange={set('to')} /></label>
      </div>
      <div className="card">
        <DataState {...polling} onRetry={polling.reload}>
          {(result) => result.items.length === 0 ? <EmptyState icon={ScrollText} title="Sin registros" message="No hay acciones con estos filtros." /> : (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Fecha y hora</th><th>Usuario</th><th>Acción</th><th>Entidad</th><th>Detalle</th></tr></thead>
                  <tbody>
                    {result.items.map((a) => (
                      <tr key={a.id}>
                        <td className="nowrap tabular">{formatDateTime(a.timestamp)}</td>
                        <td>{a.userName || 'Sistema'}<div className="cell-sub">{a.userEmail}</div></td>
                        <td><span className="badge tone-neutral">{a.action.replaceAll('_', ' ')}</span></td>
                        <td className="nowrap">{a.entity}{a.entityId ? ` #${a.entityId}` : ''}</td>
                        <td>{a.details}</td>
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
    </>
  )
}

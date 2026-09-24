import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Pencil, Plus, Search } from 'lucide-react'
import { sitesApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import { useAuth } from '../context/AuthContext.jsx'
import { can } from '../utils/permissions.js'
import { formatDate } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import { DataState, EmptyState } from '../components/common/Feedback.jsx'
import { StatusBadge } from '../components/common/Badges.jsx'
import ProgressBar, { batteryTone } from '../components/common/ProgressBar.jsx'
import SiteFormModal from '../components/sites/SiteFormModal.jsx'

const FILTERS = [
  { value: '', label: 'Todas' },
  { value: 'ACTIVA', label: 'Activa' },
  { value: 'MANTENIMIENTO', label: 'Mantenimiento' },
  { value: 'SIN_CONEXION', label: 'Sin conexión' },
]

/** OBRAS MONITOREADAS (seccion 15). */
export default function SitesPage() {
  const { user, settings } = useAuth()
  const navigate = useNavigate()
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [form, setForm] = useState(null)
  const polling = usePolling(() => sitesApi.list({ status: status || undefined }), [status])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!polling.data || !q) return polling.data
    return polling.data.filter((s) => [s.name, s.client, s.location, s.code].some((v) => v?.toLowerCase().includes(q)))
  }, [polling.data, query])

  const nextCode = useMemo(() => {
    const max = Math.max(0, ...(polling.data || []).map((s) => parseInt(s.code.slice(5), 10) || 0))
    return `OBRA-${String(max + 1).padStart(3, '0')}`
  }, [polling.data])

  return (
    <>
      <PageHeader icon={Building2} title="OBRAS MONITOREADAS" subtitle="Estaciones de vigilancia instaladas en cada obra"
        actions={can(user, 'manageSites') && (
          <button type="button" className="btn btn-primary" onClick={() => setForm({})}><Plus size={16} /> Nueva obra</button>
        )} />
      <div className="filters">
        <div className="btn-group" role="group" aria-label="Filtrar por estado">
          {FILTERS.map((f) => (
            <button key={f.value} type="button" className={`btn${status === f.value ? ' active' : ''}`} onClick={() => setStatus(f.value)}>{f.label}</button>
          ))}
        </div>
        <div className="search-box">
          <Search size={15} />
          <input className="input" placeholder="Buscar por nombre, cliente o ubicación" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Buscar obra" />
        </div>
      </div>
      <div className="card">
        <DataState {...polling} data={visible} onRetry={polling.reload}>
          {(sites) => sites.length === 0 ? (
            <EmptyState icon={Building2} title="No se encontraron obras" message="Pruebe con otro filtro o búsqueda." />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Código</th><th>Nombre</th><th>Cliente</th><th>Ubicación</th><th>Estado</th><th>Estado general</th>
                    <th className="num">Cámaras</th><th>Batería</th><th>Conexión activa</th><th className="num">Alertas</th>
                    {can(user, 'manageSites') && <th className="num">Acciones</th>}
                  </tr>
                </thead>
                <tbody>
                  {sites.map((s) => (
                    <tr key={s.id} className="clickable" onClick={() => navigate(`/obras/${s.id}`)}>
                      <td className="cell-main nowrap">{s.code}</td>
                      <td><div className="cell-main">{s.name}</div><div className="cell-sub">Instalada el {formatDate(s.installationDate)}</div></td>
                      <td>{s.client}</td>
                      <td>{s.location}</td>
                      <td><StatusBadge kind="site" value={s.status} /></td>
                      <td><StatusBadge kind="general" value={s.generalState} />{s.dataStale && <div className="cell-sub">Sin datos recientes</div>}</td>
                      <td className="num">{s.camerasOnline}/{s.cameraCount}</td>
                      <td><ProgressBar value={s.batteryPercent} tone={batteryTone(s.batteryPercent, settings.batteryLowThreshold, settings.batteryCriticalThreshold)} label="Batería" /></td>
                      <td><StatusBadge kind="connection" value={s.activeConnection} /></td>
                      <td className="num">{s.activeAlerts > 0 ? <strong style={{ color: 'var(--critical)' }}>{s.activeAlerts}</strong> : 0}</td>
                      {can(user, 'manageSites') && (
                        <td><div className="actions">
                          <button type="button" className="btn btn-sm" onClick={(e) => { e.stopPropagation(); setForm(s) }}><Pencil size={14} /> Editar</button>
                        </div></td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </div>
      {form && (
        <SiteFormModal site={form.id ? form : null} suggestedCode={nextCode} onClose={() => setForm(null)}
          onSaved={(saved) => { polling.reload(); if (!form.id && saved?.site?.id) navigate(`/obras/${saved.site.id}`) }} />
      )}
    </>
  )
}

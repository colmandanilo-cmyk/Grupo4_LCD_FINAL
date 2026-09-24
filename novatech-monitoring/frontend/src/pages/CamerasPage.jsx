import { useMemo, useState } from 'react'
import { Cctv, Grid2x2, Grid3x3, LayoutGrid } from 'lucide-react'
import { camerasApi, sitesApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import PageHeader from '../components/common/PageHeader.jsx'
import { DataState } from '../components/common/Feedback.jsx'
import CameraGrid from '../components/cameras/CameraGrid.jsx'
import CameraDetailModal from '../components/cameras/CameraDetailModal.jsx'

const LAYOUTS = [
  { columns: 2, label: '2×2', icon: Grid2x2 },
  { columns: 3, label: '3×3', icon: Grid3x3 },
  { columns: 4, label: '4×4', icon: LayoutGrid },
]

/** Vista tipo CCTV de todas las camaras (secciones 20 y 21). */
export default function CamerasPage() {
  const [siteId, setSiteId] = useState('')
  const [status, setStatus] = useState('')
  const [columns, setColumns] = useState(3)
  const [selectedId, setSelectedId] = useState(null)
  const polling = usePolling(() => camerasApi.list(siteId || undefined), [siteId])
  const sites = usePolling(() => sitesApi.list(), [], { interval: 60000 })

  const visible = useMemo(() => polling.data?.filter((c) => !status || c.status === status) ?? null, [polling.data, status])
  const selected = polling.data?.find((c) => c.deviceId === selectedId)
  const online = polling.data?.filter((c) => c.status === 'ONLINE').length ?? 0

  return (
    <>
      <PageHeader icon={Cctv} title="Cámaras" subtitle={polling.data ? `${online} de ${polling.data.length} cámaras en línea · vista simulada, sin video real` : 'Vista CCTV'}
        actions={
          <div className="btn-group" role="group" aria-label="Distribución">
            {LAYOUTS.map((l) => (
              <button key={l.columns} type="button" className={`btn${columns === l.columns ? ' active' : ''}`} onClick={() => setColumns(l.columns)}>
                <l.icon size={15} /> {l.label}
              </button>
            ))}
          </div>
        } />
      <div className="filters">
        <select className="select" value={siteId} onChange={(e) => setSiteId(e.target.value)} aria-label="Obra">
          <option value="">Todas las obras</option>
          {sites.data?.map((s) => <option key={s.id} value={s.id}>{s.code} · {s.name}</option>)}
        </select>
        <select className="select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Estado">
          <option value="">Todos los estados</option>
          <option value="ONLINE">ONLINE</option>
          <option value="OFFLINE">OFFLINE</option>
          <option value="MANTENIMIENTO">MANTENIMIENTO</option>
        </select>
      </div>
      <DataState {...polling} data={visible} onRetry={polling.reload}>
        {(cameras) => <CameraGrid cameras={cameras} columns={columns} showSite={!siteId} onSelect={(c) => setSelectedId(c.deviceId)} />}
      </DataState>
      {selected && <CameraDetailModal camera={selected} onClose={() => setSelectedId(null)} />}
    </>
  )
}

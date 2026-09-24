import { useState } from 'react'
import { camerasApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { formatDateTime, timeAgo } from '../../utils/format.js'
import { DataState } from '../../components/common/Feedback.jsx'
import { StatusBadge } from '../../components/common/Badges.jsx'
import CameraGrid from '../../components/cameras/CameraGrid.jsx'
import CameraDetailModal from '../../components/cameras/CameraDetailModal.jsx'

/** Pestana "Camaras": vista CCTV de la obra y tabla con los datos de cada camara. */
export default function CamerasTab({ siteId }) {
  const polling = usePolling(() => camerasApi.list(siteId), [siteId])
  const [selectedId, setSelectedId] = useState(null)
  const selected = polling.data?.find((c) => c.deviceId === selectedId)

  return (
    <DataState {...polling} onRetry={polling.reload}>
      {(cameras) => (
        <div className="stack">
          <CameraGrid cameras={cameras} columns={cameras.length > 2 ? 2 : cameras.length} onSelect={(c) => setSelectedId(c.deviceId)} />
          <div className="card">
            <div className="card-header"><h3>Detalle de cámaras</h3></div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>ID</th><th>Nombre / ubicación</th><th>Estado</th><th>Resolución</th><th className="num">FPS</th><th className="num">Señal</th><th>Última comunicación</th><th>Detección</th></tr>
                </thead>
                <tbody>
                  {cameras.map((c) => (
                    <tr key={c.deviceId} className="clickable" onClick={() => setSelectedId(c.deviceId)}>
                      <td className="cell-main nowrap">{c.code}</td>
                      <td>{c.name}<div className="cell-sub">{c.position}</div></td>
                      <td><StatusBadge kind="device" value={c.status} /></td>
                      <td>{c.resolution}</td>
                      <td className="num">{c.fps}</td>
                      <td className="num">{c.signal} %</td>
                      <td className="nowrap">{formatDateTime(c.lastSeen)}<div className="cell-sub">{timeAgo(c.lastSeen)}</div></td>
                      <td>{c.motionDetection ? (c.motionActive ? <span className="badge tone-warn">MOVIMIENTO AHORA</span> : 'Activada') : 'Desactivada'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {selected && <CameraDetailModal camera={selected} onClose={() => setSelectedId(null)} />}
        </div>
      )}
    </DataState>
  )
}

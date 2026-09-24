import { Link } from 'react-router-dom'
import Modal from '../common/Modal.jsx'
import { SimulatedBadge, StatusBadge } from '../common/Badges.jsx'
import CameraTile from './CameraTile.jsx'
import { useNow } from './CameraGrid.jsx'
import { EVENT_TYPE } from '../../utils/labels.js'
import { formatDateTime, timeAgo } from '../../utils/format.js'

/** Vista ampliada de una camara con todos sus datos (seccion 20). */
export default function CameraDetailModal({ camera, onClose }) {
  const now = useNow()
  if (!camera) return null
  return (
    <Modal open title={`${camera.code} · ${camera.name}`} onClose={onClose} size="lg"
      footer={<Link className="btn" to={`/obras/${camera.siteId}?tab=camaras`} onClick={onClose}>Ir al centro de control de {camera.siteCode}</Link>}>
      <div className="stack">
        <CameraTile camera={camera} nowMs={now} />
        <dl className="detail-list">
          <dt>Obra</dt><dd>{camera.siteCode} · {camera.siteName}</dd>
          <dt>Ubicación</dt><dd>{camera.position}</dd>
          <dt>Estado</dt><dd><StatusBadge kind="device" value={camera.status} /> {camera.simulated && <SimulatedBadge />}</dd>
          <dt>Resolución</dt><dd>{camera.resolution}</dd>
          <dt>FPS</dt><dd>{camera.fps}</dd>
          <dt>Señal</dt><dd>{camera.signal} %</dd>
          <dt>Detección de movimiento</dt><dd>{camera.motionDetection ? 'Activada' : 'Desactivada'}</dd>
          <dt>Grabando</dt><dd>{camera.recording ? 'Sí' : 'No'}</dd>
          <dt>Última comunicación</dt><dd>{formatDateTime(camera.lastSeen)} ({timeAgo(camera.lastSeen)})</dd>
          <dt>Último movimiento</dt><dd>{camera.lastMotionAt ? formatDateTime(camera.lastMotionAt) : 'Sin registros'}</dd>
          <dt>Último evento</dt>
          <dd>{camera.lastEventType
            ? `${EVENT_TYPE[camera.lastEventType]?.label || camera.lastEventType} · ${formatDateTime(camera.lastEventAt)}`
            : 'Sin eventos'}</dd>
        </dl>
      </div>
    </Modal>
  )
}

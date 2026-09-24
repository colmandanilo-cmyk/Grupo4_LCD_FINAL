import { Footprints, Siren, Wrench, WifiOff } from 'lucide-react'
import acceso from '../../assets/cameras/acceso.svg'
import perimetro from '../../assets/cameras/perimetro.svg'
import materiales from '../../assets/cameras/materiales.svg'
import vehicular from '../../assets/cameras/vehicular.svg'
import grua from '../../assets/cameras/grua.svg'
import maquinaria from '../../assets/cameras/maquinaria.svg'
import { EVENT_TYPE } from '../../utils/labels.js'
import { formatDate, formatTime, parseDate, timeAgo } from '../../utils/format.js'

/** Imagen de fondo de cada camara: escenas ilustradas, no hay video real (seccion 21). */
export const SCENES = { acceso, perimetro, materiales, vehicular, grua, maquinaria }

/**
 * Hora que muestra la camara: la del equipo (reloj virtual del simulador),
 * avanzada localmente entre actualizaciones para que el reloj no "salte".
 */
export function cameraClock(camera, nowMs) {
  const device = parseDate(camera.deviceTime)
  if (!device) return null
  const received = parseDate(camera.deviceTimeReceivedAt)
  let elapsed = received ? (nowMs - received.getTime()) / 1000 : 0
  elapsed = Math.max(0, Math.min(elapsed, 60))
  const factor = camera.running ? camera.speed || 1 : 0
  return new Date(device.getTime() + elapsed * factor * 1000)
}

/** Cuando dos camaras comparten escena, la de numero par se muestra espejada. */
function isFlipped(code) {
  const number = parseInt(String(code).replace(/\D/g, ''), 10)
  return Number.isFinite(number) && number % 2 === 0
}

export default function CameraTile({ camera, nowMs, onClick, showSite = false }) {
  const clock = cameraClock(camera, nowMs) || new Date(nowMs)
  const hour = clock.getHours()
  const night = hour < 6 || hour >= 18
  const online = camera.status === 'ONLINE'
  const classes = ['cctv-tile']
  if (online && night) classes.push('ir')
  if (online && camera.motionActive) classes.push('motion')
  if (camera.intrusionActive) classes.push('intrusion')
  const lastEvent = camera.lastEventType ? EVENT_TYPE[camera.lastEventType]?.label || camera.lastEventType : null

  return (
    <div className={classes.join(' ')} onClick={onClick} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.()}
      aria-label={`Cámara ${camera.code} ${camera.name}, estado ${camera.status}`}>
      {camera.status === 'OFFLINE' && <div className="cctv-noise" />}
      {camera.status === 'MANTENIMIENTO' && <div className="cctv-maintenance" />}
      {online && (
        <img className={`cctv-scene${isFlipped(camera.code) ? ' flip' : ''}`} src={SCENES[camera.scene] || acceso} alt="" draggable="false" />
      )}

      <div className="cctv-osd top-left">
        <div className="cam-name">{camera.code} · {camera.name}</div>
        {showSite && <div>{camera.siteCode}</div>}
        {online && night && <div>IR</div>}
      </div>
      <div className="cctv-osd top-right">
        {online && camera.recording && <span className="cctv-rec">REC</span>}
        <div><span className="cctv-status">{camera.status}</span></div>
      </div>
      <div className="cctv-osd bottom-left">
        <div>{formatDate(clock)} {formatTime(clock, true)}</div>
        {online && <div>{camera.fps} FPS · señal {camera.signal} %</div>}
      </div>
      <div className="cctv-osd bottom-right">
        {lastEvent && <div>Últ. evento: {lastEvent}</div>}
        {camera.lastEventAt && <div>{timeAgo(camera.lastEventAt)}</div>}
      </div>

      {camera.status === 'OFFLINE' && (
        <div className="cctv-center"><WifiOff size={26} />SIN SEÑAL<small>Última comunicación: {timeAgo(camera.lastSeen)}</small></div>
      )}
      {camera.status === 'MANTENIMIENTO' && (
        <div className="cctv-center"><Wrench size={26} />EN MANTENIMIENTO<small>Cámara detenida por el administrador</small></div>
      )}
      {online && camera.motionActive && (
        <div className="cctv-banner motion"><Footprints size={14} />MOVIMIENTO DETECTADO</div>
      )}
      {camera.intrusionActive && (
        <div className="cctv-banner intrusion"><Siren size={14} />ALERTA DE INTRUSIÓN</div>
      )}
    </div>
  )
}

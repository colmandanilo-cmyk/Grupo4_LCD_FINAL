import { useEffect, useState } from 'react'
import CameraTile from './CameraTile.jsx'
import { EmptyState } from '../common/Feedback.jsx'

/** Reloj local que avanza cada segundo (para la hora en pantalla de las camaras). */
export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

/** Cuadricula CCTV con 2, 3 o 4 columnas. */
export default function CameraGrid({ cameras, columns = 3, onSelect, showSite = false }) {
  const now = useNow()
  if (!cameras?.length) return <EmptyState title="Sin cámaras" message="No hay cámaras para los filtros elegidos." />
  return (
    <div className="cctv-grid" style={{ '--cctv-cols': columns }}>
      {cameras.map((camera) => (
        <CameraTile key={camera.deviceId} camera={camera} nowMs={now} onClick={() => onSelect?.(camera)} showSite={showSite} />
      ))}
    </div>
  )
}

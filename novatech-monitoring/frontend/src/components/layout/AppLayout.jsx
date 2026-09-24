import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { dashboardApi } from '../../services/api.js'
import { usePolling } from '../../hooks/usePolling.js'
import { useToast } from '../../context/ToastContext.jsx'
import { SEVERITY } from '../../utils/labels.js'
import ErrorBoundary from '../common/ErrorBoundary.jsx'
import Header from './Header.jsx'
import Sidebar from './Sidebar.jsx'

/**
 * Estructura de las pantallas con sesion: menu lateral, cabecera y contenido.
 * Consulta el estado general cada pocos segundos y avisa cuando llega una alerta nueva.
 */
export default function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { data: status } = usePolling(() => dashboardApi.status())
  const toast = useToast()
  const lastAlertId = useRef(null)
  const location = useLocation()

  useEffect(() => {
    const latest = status?.latestAlert
    if (!latest) return
    if (lastAlertId.current !== null && latest.id > lastAlertId.current) {
      const tone = latest.severity === 'CRITICA' ? 'critical' : 'warn'
      toast.show(`${latest.siteCode} · ${latest.title}`, tone, `Nueva alerta ${SEVERITY[latest.severity]?.label || ''}`, 8000)
    }
    lastAlertId.current = Math.max(lastAlertId.current ?? 0, latest.id)
  }, [status, toast])

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} activeAlerts={status?.activeAlerts} />
      <div className="app-main">
        <Header status={status} onToggleMenu={() => setMenuOpen((v) => !v)} />
        <main className="app-content">
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}

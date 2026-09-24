import { useEffect, useState } from 'react'
import { LogOut, Menu } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { ROLE } from '../../utils/labels.js'
import { formatTime, timeAgo } from '../../utils/format.js'
import { SimulatedBadge, StatusBadge } from '../common/Badges.jsx'

/** Cabecera: estado general, fuente de datos, fecha, hora, usuario, rol y cerrar sesion. */
export default function Header({ status, onToggleMenu }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const source = status?.dataSource
  const counts = status ? [
    status.sitesCritical ? `${status.sitesCritical} en estado crítico` : null,
    status.sitesWarning ? `${status.sitesWarning} con advertencia` : null,
  ].filter(Boolean).join(', ') : ''
  const initials = (user?.name || '?').split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()

  return (
    <header className="app-header">
      <button type="button" className="btn btn-ghost btn-icon header-menu-button" onClick={onToggleMenu} aria-label="Abrir menú">
        <Menu size={20} />
      </button>
      <div className="header-status" title={counts || 'Todas las obras en operación normal'}>
        <span className="muted nowrap">Estado general</span>
        {status ? <StatusBadge kind="general" value={status.generalState} /> : <span className="muted">…</span>}
      </div>
      {source && (
        <span className={`data-source${source.online ? '' : ' offline'}`}
          title={source.lastContact ? `Último contacto: ${timeAgo(source.lastContact)}` : 'Sin contacto'}>
          <span className="dot" aria-hidden="true" />
          <span className="label-long">Fuente de datos:</span> {source.online ? 'en línea' : 'desconectada'}
        </span>
      )}
      {source?.mode === 'SIMULADO' && <SimulatedBadge label="DATOS SIMULADOS" />}
      <div className="header-spacer" />
      <div className="header-clock">
        <strong>{formatTime(now, true)}</strong>
        <span>{now.toLocaleDateString('es-PE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</span>
      </div>
      <div className="header-user">
        <div className="avatar" aria-hidden="true">{initials}</div>
        <div className="who">
          <strong>{user?.name}</strong>
          <span>{ROLE[user?.role]?.label}</span>
        </div>
        <button type="button" className="btn btn-sm" onClick={handleLogout} title="Cerrar sesión">
          <LogOut size={15} /> Salir
        </button>
      </div>
    </header>
  )
}

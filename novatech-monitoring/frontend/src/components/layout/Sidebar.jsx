import { NavLink } from 'react-router-dom'
import logo from '../../assets/logo-novatech.svg'
import { useAuth } from '../../context/AuthContext.jsx'
import { menuFor } from '../../utils/permissions.js'

/** Menu lateral: solo muestra las opciones permitidas para el rol (seccion 12). */
export default function Sidebar({ open, onNavigate, activeAlerts }) {
  const { user } = useAuth()
  const items = menuFor(user?.role)
  return (
    <aside className={`sidebar${open ? ' open' : ''}`} aria-label="Menú principal">
      <div className="sidebar-brand">
        <img src={logo} alt="" />
        <div>
          <strong>NOVA TECH</strong>
          <span>Centro de Monitoreo de Seguridad</span>
        </div>
      </div>
      <nav>
        {items.map((item) => item.section ? (
          <div key={item.section} className="sidebar-section">{item.section}</div>
        ) : (
          <NavLink key={item.to} to={item.to} className="sidebar-link" onClick={onNavigate}>
            <item.icon size={18} aria-hidden="true" />
            <span>{item.label}</span>
            {item.badge === 'alerts' && activeAlerts > 0 && (
              <span className="badge-count" aria-label={`${activeAlerts} alertas activas`}>{activeAlerts}</span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">Monitoreo y vigilancia para obras · v1.0</div>
    </aside>
  )
}

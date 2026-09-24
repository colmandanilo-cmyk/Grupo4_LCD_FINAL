/**
 * Que ve y que puede hacer cada rol (seccion 10). La proteccion real esta en el
 * backend (@PreAuthorize): aqui solo se ocultan menus y botones que no corresponden.
 */
import {
  Bell, Building2, Cctv, ClipboardList, FileChartColumn, FlaskConical, LayoutDashboard, Satellite, ScrollText,
  Settings, SunDim, Users,
} from 'lucide-react'

const ALL = ['ADMINISTRADOR', 'SUPERVISOR', 'OPERADOR']
const SUPERVISION = ['ADMINISTRADOR', 'SUPERVISOR']
const ADMIN = ['ADMINISTRADOR']

export const MENU = [
  { section: 'Monitoreo' },
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ALL },
  { to: '/obras', label: 'Obras', icon: Building2, roles: ALL },
  { to: '/camaras', label: 'Cámaras', icon: Cctv, roles: ALL },
  { to: '/energia', label: 'Energía', icon: SunDim, roles: ALL },
  { to: '/conectividad', label: 'Conectividad', icon: Satellite, roles: ALL },
  { section: 'Gestión' },
  { to: '/alertas', label: 'Alertas', icon: Bell, roles: ALL, badge: 'alerts' },
  { to: '/incidencias', label: 'Incidencias', icon: ClipboardList, roles: SUPERVISION },
  { to: '/reportes', label: 'Reportes', icon: FileChartColumn, roles: SUPERVISION },
  { section: 'Administración' },
  { to: '/simulador', label: 'Simulador', icon: FlaskConical, roles: ADMIN },
  { to: '/usuarios', label: 'Usuarios', icon: Users, roles: ADMIN },
  { to: '/configuracion', label: 'Configuración', icon: Settings, roles: ADMIN },
  { to: '/auditoria', label: 'Auditoría', icon: ScrollText, roles: ADMIN },
]

/** Menu visible para un rol (sin titulos de seccion vacios). */
export function menuFor(role) {
  const items = []
  let pendingSection = null
  for (const item of MENU) {
    if (item.section) {
      pendingSection = item
    } else if (item.roles.includes(role)) {
      if (pendingSection) {
        items.push(pendingSection)
        pendingSection = null
      }
      items.push(item)
    }
  }
  return items
}

export const ROLES_FOR = {
  view: ALL,
  acknowledgeAlert: ALL,
  resolveAlert: SUPERVISION,
  incidents: SUPERVISION,
  reports: SUPERVISION,
  manageSites: ADMIN,
  manageDevices: ADMIN,
  simulator: ADMIN,
  users: ADMIN,
  settings: ADMIN,
  audit: ADMIN,
}

/** can(user, 'resolveAlert') */
export function can(user, action) {
  return Boolean(user && ROLES_FOR[action]?.includes(user.role))
}

import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout.jsx'
import ProtectedRoute from './components/common/ProtectedRoute.jsx'
import { ROLES_FOR } from './utils/permissions.js'
import LoginPage from './pages/LoginPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import SitesPage from './pages/SitesPage.jsx'
import SiteControlCenterPage from './pages/SiteControlCenterPage.jsx'
import CamerasPage from './pages/CamerasPage.jsx'
import EnergyPage from './pages/EnergyPage.jsx'
import ConnectivityPage from './pages/ConnectivityPage.jsx'
import AlertsPage from './pages/AlertsPage.jsx'
import IncidentsPage from './pages/IncidentsPage.jsx'
import ReportsPage from './pages/ReportsPage.jsx'
import SimulationLabPage from './pages/SimulationLabPage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import AuditPage from './pages/AuditPage.jsx'
import ForbiddenPage from './pages/ForbiddenPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'

/** Rutas de la aplicacion. Cada ruta protegida declara los roles que la pueden ver. */
export default function App() {
  const only = (roles, element) => <ProtectedRoute roles={roles}>{element}</ProtectedRoute>
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/obras" element={<SitesPage />} />
        <Route path="/obras/:id" element={<SiteControlCenterPage />} />
        <Route path="/camaras" element={<CamerasPage />} />
        <Route path="/energia" element={<EnergyPage />} />
        <Route path="/conectividad" element={<ConnectivityPage />} />
        <Route path="/alertas" element={<AlertsPage />} />
        <Route path="/incidencias" element={only(ROLES_FOR.incidents, <IncidentsPage />)} />
        <Route path="/reportes" element={only(ROLES_FOR.reports, <ReportsPage />)} />
        <Route path="/simulador" element={only(ROLES_FOR.simulator, <SimulationLabPage />)} />
        <Route path="/usuarios" element={only(ROLES_FOR.users, <UsersPage />)} />
        <Route path="/configuracion" element={only(ROLES_FOR.settings, <SettingsPage />)} />
        <Route path="/auditoria" element={only(ROLES_FOR.audit, <AuditPage />)} />
        <Route path="/acceso-denegado" element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

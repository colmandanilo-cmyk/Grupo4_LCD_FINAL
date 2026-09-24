import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { LoadingState } from './Feedback.jsx'

/**
 * Ruta protegida: sin sesion lleva al login; con un rol no permitido lleva a
 * "Acceso no autorizado". La proteccion definitiva la hace el backend.
 */
export default function ProtectedRoute({ roles, children }) {
  const { user, checking } = useAuth()
  const location = useLocation()
  if (checking) return <LoadingState message="Verificando sesión..." />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to="/acceso-denegado" replace />
  return children
}

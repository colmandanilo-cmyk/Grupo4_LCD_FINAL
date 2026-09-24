import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { ErrorState, LoadingState } from './Feedback.jsx'

/**
 * Ruta protegida: sin sesion lleva al login; con un rol no permitido lleva a
 * "Acceso no autorizado". La proteccion definitiva la hace el backend.
 */
export default function ProtectedRoute({ roles, children }) {
  const { user, checking, connectionError, retryCheck } = useAuth()
  const location = useLocation()
  if (!user && connectionError) {
    return (
      <div className="page-center">
        <ErrorState title="No se pudo conectar con el servidor" error={connectionError} onRetry={retryCheck} />
        <p className="muted">La sesión se mantiene. Se vuelve a intentar automáticamente cada 5 segundos.</p>
      </div>
    )
  }
  if (checking && !user) return <LoadingState message="Verificando sesión..." />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to="/acceso-denegado" replace />
  return children
}

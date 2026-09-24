import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'

/** Estados de carga, error y vacio: la pantalla nunca queda en blanco (seccion 47). */
export function LoadingState({ message = 'Cargando información...' }) {
  return (
    <div className="feedback" role="status">
      <div className="spinner" aria-hidden="true" />
      <span>{message}</span>
    </div>
  )
}

export function ErrorState({ error, onRetry, title = 'No se pudo cargar la información' }) {
  return (
    <div className="feedback error" role="alert">
      <AlertTriangle size={30} aria-hidden="true" />
      <h3>{title}</h3>
      <span>{error?.message || 'Ocurrió un error inesperado.'}</span>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          <RefreshCw size={14} /> Reintentar
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title = 'Sin datos', message, icon: Icon = Inbox }) {
  return (
    <div className="feedback">
      <Icon size={30} aria-hidden="true" />
      <h3>{title}</h3>
      {message && <span>{message}</span>}
    </div>
  )
}

/**
 * Envoltorio para datos que se actualizan periodicamente: muestra carga la
 * primera vez, error si no hay datos, y un aviso si falla una actualizacion
 * pero ya hay datos anteriores.
 */
export function DataState({ loading, error, data, onRetry, children }) {
  if (loading && !data) return <LoadingState />
  if (error && !data) return <ErrorState error={error} onRetry={onRetry} />
  return (
    <>
      {error && (
        <div className="inline-alert tone-warn no-print">
          <AlertTriangle size={16} />
          <span>No se pudo actualizar: {error.message} Se muestran los últimos datos recibidos.</span>
        </div>
      )}
      {data && children(data)}
    </>
  )
}

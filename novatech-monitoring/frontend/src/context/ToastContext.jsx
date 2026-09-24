import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

/** Avisos breves en la esquina inferior derecha (exito, error, alerta nueva). */
const ToastContext = createContext(null)

const ICONS = { ok: CheckCircle2, critical: AlertTriangle, warn: AlertTriangle, info: Info }
let nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), [])

  const show = useCallback((message, tone = 'info', title = null, duration = 5000) => {
    const id = nextId++
    setToasts((list) => [...list.slice(-3), { id, message, tone, title }])
    setTimeout(() => dismiss(id), duration)
  }, [dismiss])

  const value = useMemo(() => ({
    show,
    success: (message, title) => show(message, 'ok', title),
    error: (message, title = 'No se pudo completar la acción') => show(message, 'critical', title, 7000),
  }), [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.tone] || Info
          return (
            <div key={toast.id} className={`toast tone-${toast.tone}`}>
              <Icon size={18} />
              <div>
                {toast.title && <strong>{toast.title}</strong>}
                {toast.message}
              </div>
              <button type="button" onClick={() => dismiss(toast.id)} aria-label="Cerrar aviso"><X size={15} /></button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}

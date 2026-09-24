import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

/**
 * Consulta periodica (polling, seccion 35): ejecuta "fetcher" al montar y luego
 * cada N segundos (Configuracion > frecuencia de actualizacion).
 *
 * - No superpone pedidos: espera la respuesta antes de programar el siguiente.
 * - Si falla, conserva los ultimos datos y expone el error.
 * - Si cambian las dependencias (por ejemplo, otra obra), vuelve a empezar.
 *
 * Devuelve { data, error, loading, reload }.
 */
export function usePolling(fetcher, deps = [], { interval, enabled = true } = {}) {
  const { settings } = useAuth()
  const period = interval ?? settings.refreshSeconds * 1000
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [tick, setTick] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const depsKey = JSON.stringify(deps)
  const lastKey = useRef(depsKey)

  useEffect(() => {
    if (!enabled) return undefined
    let cancelled = false
    let timer = null
    if (lastKey.current !== depsKey) {
      lastKey.current = depsKey
      setState({ data: null, error: null, loading: true })
    }
    const run = async () => {
      try {
        const data = await fetcherRef.current()
        if (!cancelled) setState({ data, error: null, loading: false })
      } catch (error) {
        if (!cancelled) setState((prev) => ({ data: prev.data, error, loading: false }))
      }
      if (!cancelled && period > 0) timer = setTimeout(run, period)
    }
    run()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [depsKey, period, enabled, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}

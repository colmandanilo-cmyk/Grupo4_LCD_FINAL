import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authApi, session, setUnauthorizedHandler } from '../services/api.js'

/**
 * Sesion del usuario: quien es, su rol y los parametros de la interfaz
 * (frecuencia de actualizacion y umbrales de bateria).
 */
const AuthContext = createContext(null)

const DEFAULT_SETTINGS = { refreshSeconds: 5, batteryLowThreshold: 35, batteryCriticalThreshold: 20 }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [checking, setChecking] = useState(Boolean(session.getToken()))
  const [expired, setExpired] = useState(false)

  const clearSession = useCallback(() => {
    session.clear()
    setUser(null)
  }, [])

  // Si el backend responde 401 en cualquier pantalla, la sesion vencio.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (session.getToken()) setExpired(true)
      clearSession()
    })
    return () => setUnauthorizedHandler(null)
  }, [clearSession])

  // Al recargar la pagina se valida el token guardado.
  useEffect(() => {
    if (!session.getToken()) return
    authApi.me()
      .then((data) => {
        setUser(data.user)
        setSettings(data.settings)
      })
      .catch(() => clearSession())
      .finally(() => setChecking(false))
  }, [clearSession])

  const login = useCallback(async (email, password) => {
    const data = await authApi.login(email, password)
    session.setToken(data.token)
    setUser(data.user)
    setSettings(data.settings)
    setExpired(false)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      /* aunque falle el registro de auditoria, la sesion se cierra */
    }
    setExpired(false)
    clearSession()
  }, [clearSession])

  const refreshSettings = useCallback(async () => {
    const data = await authApi.me()
    setSettings(data.settings)
  }, [])

  const value = useMemo(() => ({
    user, settings, checking, expired, login, logout, refreshSettings,
  }), [user, settings, checking, expired, login, logout, refreshSettings])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}

/**
 * Unico punto de salida a la red del frontend.
 *
 * Todas las llamadas van a rutas relativas /api/...; el servidor de Vite las
 * reenvia al backend Java (ver vite.config.js). React nunca habla con Python.
 */

const TOKEN_KEY = 'novatech.token'

/** Error de la API con codigo HTTP y, si corresponde, errores por campo. */
export class ApiError extends Error {
  constructor(status, message, fieldErrors = null) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

// ---------------- Token de sesion (se borra al cerrar la pestana) ----------------

export const session = {
  getToken: () => {
    try {
      return sessionStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  setToken: (token) => {
    try {
      sessionStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* el navegador no permite almacenamiento: la sesion dura hasta recargar */
    }
  },
  clear: () => {
    try {
      sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      /* sin almacenamiento */
    }
  },
}

let unauthorizedHandler = null

/** AuthContext registra aqui que hacer cuando el backend responde 401 (sesion vencida). */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler
}

function toQuery(params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return ''
  return '?' + new URLSearchParams(entries).toString()
}

async function request(method, path, { body, params, raw = false } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = session.getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch('/api' + path + toQuery(params), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor. Verifique que el backend esté en ejecución.')
  }

  if (!response.ok) {
    let data = null
    try {
      data = await response.json()
    } catch {
      /* respuesta sin JSON (por ejemplo, el proxy no encontro al backend) */
    }
    if (response.status === 401 && !path.startsWith('/auth/login') && unauthorizedHandler) {
      unauthorizedHandler()
    }
    const message = data?.message
      || (response.status >= 500 ? 'El servidor no está disponible o tuvo un error. Intente nuevamente.'
        : `Error ${response.status}`)
    throw new ApiError(response.status, message, data?.fieldErrors || null)
  }

  if (raw) return response
  if (response.status === 204) return null
  const text = await response.text()
  return text ? JSON.parse(text) : null
}

const get = (path, params) => request('GET', path, { params })
const post = (path, body) => request('POST', path, { body: body ?? {} })
const put = (path, body) => request('PUT', path, { body: body ?? {} })

// ---------------- Funciones por recurso ----------------

export const authApi = {
  login: (email, password) => post('/auth/login', { email, password }),
  me: () => get('/auth/me'),
  logout: () => post('/auth/logout'),
}

export const dashboardApi = {
  summary: () => get('/dashboard/summary'),
  status: () => get('/dashboard/status'),
}

export const sitesApi = {
  list: (params) => get('/sites', params),
  get: (id) => get(`/sites/${id}`),
  create: (data) => post('/sites', data),
  update: (id, data) => put(`/sites/${id}`, data),
}

export const devicesApi = {
  list: (siteId) => get('/devices', { siteId }),
  createCamera: (data) => post('/devices', data),
  update: (id, data) => put(`/devices/${id}`, data),
}

export const camerasApi = {
  list: (siteId) => get('/cameras', { siteId }),
}

export const energyApi = {
  overview: () => get('/energy'),
  site: (siteId) => get(`/energy/sites/${siteId}`),
  history: (siteId, hours = 24) => get(`/energy/sites/${siteId}/history`, { hours }),
}

export const connectivityApi = {
  overview: () => get('/connectivity'),
  site: (siteId) => get(`/connectivity/sites/${siteId}`),
  history: (siteId, hours = 24) => get(`/connectivity/sites/${siteId}/history`, { hours }),
  timeline: (siteId, limit = 20) => get(`/connectivity/sites/${siteId}/timeline`, { limit }),
}

export const telemetryApi = {
  metrics: (siteId) => get('/telemetry/metrics', { siteId }),
  series: (deviceId, metric, hours = 24) => get('/telemetry', { deviceId, metric, hours }),
  latest: (siteId, limit = 60) => get('/telemetry/latest', { siteId, limit }),
}

export const eventsApi = {
  list: (params) => get('/events', params),
}

export const alertsApi = {
  list: (params) => get('/alerts', params),
  get: (id) => get(`/alerts/${id}`),
  acknowledge: (id) => put(`/alerts/${id}/acknowledge`),
  resolve: (id, note) => put(`/alerts/${id}/resolve`, { note }),
}

export const incidentsApi = {
  list: (params) => get('/incidents', params),
  get: (id) => get(`/incidents/${id}`),
  create: (data) => post('/incidents', data),
  update: (id, data) => put(`/incidents/${id}`, data),
  changeStatus: (id, status, observation) => put(`/incidents/${id}/status`, { status, observation }),
}

export const usersApi = {
  list: () => get('/users'),
  assignable: () => get('/users/assignable'),
  create: (data) => post('/users', data),
  update: (id, data) => put(`/users/${id}`, data),
}

export const reportsApi = {
  get: (type, params) => get(`/reports/${type}`, params),
  /** Descarga el CSV (se pide con el token y se guarda como archivo). */
  downloadCsv: async (type, params) => {
    const response = await request('GET', `/reports/${type}/csv`, { params, raw: true })
    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="([^"]+)"/)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = match ? match[1] : `reporte-${type}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },
}

export const simulationApi = {
  status: () => get('/simulation/status'),
  start: () => post('/simulation/start'),
  pause: () => post('/simulation/pause'),
  reset: () => post('/simulation/reset'),
  speed: (speed) => post('/simulation/speed', { speed }),
  scenario: (path, siteId, deviceId) => post(`/simulation/${path}`, { siteId, deviceId: deviceId || null }),
}

export const configApi = {
  list: () => get('/config'),
  update: (values) => put('/config', { values }),
}

export const auditApi = {
  list: (params) => get('/audit', params),
  actions: () => get('/audit/actions'),
}

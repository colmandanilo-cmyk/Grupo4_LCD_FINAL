import { useEffect, useState } from 'react'
import { Save, Settings } from 'lucide-react'
import { configApi } from '../services/api.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { formatDateTime } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import { ErrorState, LoadingState } from '../components/common/Feedback.jsx'

/** Definicion de cada parametro de la pantalla (seccion 43). */
const FIELDS = [
  { key: 'battery.low_threshold', label: 'Límite de batería baja', unit: '%', type: 'number', min: 5, max: 90 },
  { key: 'battery.critical_threshold', label: 'Límite de batería crítica', unit: '%', type: 'number', min: 1, max: 89 },
  { key: 'ui.refresh_seconds', label: 'Frecuencia de actualización de pantallas', unit: 'segundos', type: 'number', min: 2, max: 60 },
  { key: 'telemetry.interval_seconds', label: 'Frecuencia de registro de telemetría', unit: 'segundos', type: 'number', min: 10, max: 600 },
  { key: 'simulation.enabled', label: 'Simulación automática activada', type: 'boolean' },
  { key: 'simulation.default_speed', label: 'Velocidad predeterminada de la simulación', type: 'select', options: ['1', '5', '20'] },
]

/** CONFIGURACION (solo administrador). */
export default function SettingsPage() {
  const { refreshSettings } = useAuth()
  const toast = useToast()
  const [entries, setEntries] = useState(null)
  const [values, setValues] = useState({})
  const [error, setError] = useState(null)
  const [saveError, setSaveError] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setError(null)
    configApi.list().then((list) => {
      setEntries(list)
      setValues(Object.fromEntries(list.map((e) => [e.key, e.value])))
    }).catch(setError)
  }
  useEffect(load, [])

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      const changed = Object.fromEntries(Object.entries(values).filter(([k, v]) => entries.find((x) => x.key === k)?.value !== v))
      if (Object.keys(changed).length === 0) {
        toast.show('No hay cambios para guardar.', 'info')
        return
      }
      const list = await configApi.update(changed)
      setEntries(list)
      await refreshSettings()
      toast.success('La configuración se guardó y ya está en uso.', 'Configuración actualizada')
    } catch (err) {
      setSaveError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (error) return <ErrorState error={error} onRetry={load} />
  if (!entries) return <LoadingState />
  const byKey = Object.fromEntries(entries.map((e) => [e.key, e]))

  return (
    <>
      <PageHeader icon={Settings} title="Configuración" subtitle="Parámetros del sistema. Cada cambio queda registrado en auditoría." />
      <form className="card" onSubmit={save} style={{ maxWidth: 860 }}>
        <div className="card-body stack">
          {saveError && <div className="form-error">{saveError}</div>}
          {FIELDS.map((f) => (
            <div key={f.key} className="field" style={{ borderBottom: '1px solid var(--border)', paddingBottom: 14 }}>
              <label htmlFor={f.key}>{f.label}</label>
              <div className="row">
                {f.type === 'number' && (
                  <input id={f.key} type="number" className="input" style={{ width: 140 }} min={f.min} max={f.max}
                    value={values[f.key] ?? ''} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} />
                )}
                {f.type === 'select' && (
                  <select id={f.key} className="select" style={{ width: 140 }} value={values[f.key] ?? '1'}
                    onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}>
                    {f.options.map((o) => <option key={o} value={o}>x{o}</option>)}
                  </select>
                )}
                {f.type === 'boolean' && (
                  <label className="checkbox">
                    <input id={f.key} type="checkbox" checked={values[f.key] === 'true'}
                      onChange={(e) => setValues({ ...values, [f.key]: e.target.checked ? 'true' : 'false' })} />
                    {values[f.key] === 'true' ? 'Activada' : 'Desactivada'}
                  </label>
                )}
                {f.unit && <span className="secondary">{f.unit}{f.min !== undefined && ` (entre ${f.min} y ${f.max})`}</span>}
              </div>
              <span className="hint">{byKey[f.key]?.description}
                {byKey[f.key]?.updatedAt && ` · Último cambio: ${formatDateTime(byKey[f.key].updatedAt)}${byKey[f.key].updatedByName ? ` por ${byKey[f.key].updatedByName}` : ''}`}</span>
            </div>
          ))}
          <div className="row" style={{ justifyContent: 'flex-end' }}>
            <button type="submit" className="btn btn-primary" disabled={saving}><Save size={15} /> Guardar configuración</button>
          </div>
        </div>
      </form>
    </>
  )
}

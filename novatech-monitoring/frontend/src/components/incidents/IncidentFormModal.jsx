import { useEffect, useState } from 'react'
import { ClipboardPlus } from 'lucide-react'
import Modal from '../common/Modal.jsx'
import { incidentsApi, sitesApi, usersApi } from '../../services/api.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useToast } from '../../context/ToastContext.jsx'
import { SEVERITY } from '../../utils/labels.js'

/**
 * Crear incidencia: desde una alerta (queda vinculada y la alerta pasa a EN ATENCION)
 * o manual, eligiendo la obra.
 */
export default function IncidentFormModal({ alert, siteId, onClose, onSaved }) {
  const { user } = useAuth()
  const toast = useToast()
  const [users, setUsers] = useState([])
  const [sites, setSites] = useState([])
  const [form, setForm] = useState({
    siteId: alert?.siteId || siteId || '',
    title: alert ? alert.title : '',
    description: alert ? `${alert.description}${alert.deviceCode ? ` (dispositivo ${alert.deviceCode})` : ''}` : '',
    priority: alert ? (alert.severity === 'INFO' ? 'BAJA' : alert.severity) : 'MEDIA',
    assignedToId: user?.id || '',
  })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    usersApi.assignable().then(setUsers).catch(() => setUsers([]))
    if (!alert && !siteId) sitesApi.list().then(setSites).catch(() => setSites([]))
  }, [alert, siteId])

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    const found = {}
    if (!form.siteId) found.siteId = 'Seleccione la obra'
    if (!form.title.trim()) found.title = 'El título es obligatorio'
    if (!form.description.trim()) found.description = 'La descripción es obligatoria'
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    setError(null)
    try {
      const incident = await incidentsApi.create({
        siteId: Number(form.siteId),
        alertId: alert?.id || null,
        title: form.title.trim(),
        description: form.description.trim(),
        priority: form.priority,
        assignedToId: form.assignedToId ? Number(form.assignedToId) : null,
      })
      toast.success(`Se creó la incidencia ${incident.code}.`, 'Incidencia creada')
      onSaved?.(incident)
      onClose()
    } catch (err) {
      setError(err.message)
      setErrors(err.fieldErrors || {})
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open title={alert ? 'Crear incidencia desde la alerta' : 'Nueva incidencia'} onClose={onClose} size="lg"
      footer={<>
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button type="submit" form="incident-form" className="btn btn-primary" disabled={saving}><ClipboardPlus size={15} /> Crear incidencia</button>
      </>}>
      {error && <div className="form-error">{error}</div>}
      <form id="incident-form" className="form-grid" onSubmit={submit} noValidate>
        {alert ? (
          <div className="field full"><label>Alerta de origen</label><div>#{alert.id} · {alert.siteCode} · {alert.title}</div></div>
        ) : !siteId && (
          <div className="field full">
            <label htmlFor="inc-site">Obra</label>
            <select id="inc-site" className={`select${errors.siteId ? ' invalid' : ''}`} value={form.siteId} onChange={set('siteId')}>
              <option value="">Seleccione...</option>
              {sites.map((s) => <option key={s.id} value={s.id}>{s.code} · {s.name}</option>)}
            </select>
            {errors.siteId && <span className="error-text">{errors.siteId}</span>}
          </div>
        )}
        <div className="field full">
          <label htmlFor="inc-title">Título</label>
          <input id="inc-title" className={`input${errors.title ? ' invalid' : ''}`} maxLength={150} value={form.title} onChange={set('title')} />
          {errors.title && <span className="error-text">{errors.title}</span>}
        </div>
        <div className="field full">
          <label htmlFor="inc-desc">Descripción</label>
          <textarea id="inc-desc" className={`textarea${errors.description ? ' invalid' : ''}`} maxLength={1000} value={form.description} onChange={set('description')} />
          {errors.description && <span className="error-text">{errors.description}</span>}
        </div>
        <div className="field">
          <label htmlFor="inc-priority">Prioridad</label>
          <select id="inc-priority" className="select" value={form.priority} onChange={set('priority')}>
            {['CRITICA', 'ALTA', 'MEDIA', 'BAJA'].map((k) => <option key={k} value={k}>{SEVERITY[k].label}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="inc-assigned">Responsable</label>
          <select id="inc-assigned" className="select" value={form.assignedToId} onChange={set('assignedToId')}>
            {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select>
        </div>
      </form>
    </Modal>
  )
}

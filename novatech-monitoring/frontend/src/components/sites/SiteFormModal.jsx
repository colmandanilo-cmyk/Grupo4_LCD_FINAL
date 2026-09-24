import { useState } from 'react'
import { Save } from 'lucide-react'
import Modal from '../common/Modal.jsx'
import { sitesApi } from '../../services/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { toInputDate } from '../../utils/format.js'

/**
 * Alta o edicion de una obra (solo administrador).
 * Al crearla se instala su estacion estandar con 2 a 4 camaras.
 */
export default function SiteFormModal({ site, suggestedCode, onClose, onSaved }) {
  const editing = Boolean(site)
  const toast = useToast()
  const [form, setForm] = useState({
    code: site?.code || suggestedCode || '',
    name: site?.name || '',
    client: site?.client || '',
    location: site?.location || '',
    status: site?.status === 'MANTENIMIENTO' ? 'MANTENIMIENTO' : 'ACTIVA',
    installationDate: site?.installationDate || toInputDate(new Date()),
    cameraCount: 2,
  })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    const found = {}
    if (!/^OBRA-\d{3}$/.test(form.code)) found.code = 'Formato OBRA-000'
    for (const f of ['name', 'client', 'location']) if (!form[f].trim()) found[f] = 'Campo obligatorio'
    if (!form.installationDate) found.installationDate = 'Campo obligatorio'
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    setError(null)
    const payload = { ...form, name: form.name.trim(), client: form.client.trim(), location: form.location.trim(), cameraCount: Number(form.cameraCount) }
    try {
      const saved = editing ? await sitesApi.update(site.id, payload) : await sitesApi.create(payload)
      toast.success(editing ? `Se guardaron los cambios de ${form.code}.` : `Se creó ${form.code} con su estación de vigilancia.`,
        editing ? 'Obra actualizada' : 'Obra creada')
      onSaved?.(saved)
      onClose()
    } catch (err) {
      setError(err.message)
      setErrors(err.fieldErrors || {})
    } finally {
      setSaving(false)
    }
  }

  const field = (id, label, input, hint) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {input}
      {errors[id] ? <span className="error-text">{errors[id]}</span> : hint && <span className="hint">{hint}</span>}
    </div>
  )

  return (
    <Modal open title={editing ? `Editar obra ${site.code}` : 'Nueva obra'} onClose={onClose} size="lg"
      footer={<>
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button type="submit" form="site-form" className="btn btn-primary" disabled={saving}><Save size={15} /> Guardar</button>
      </>}>
      {error && <div className="form-error">{error}</div>}
      <form id="site-form" className="form-grid" onSubmit={submit} noValidate>
        {field('code', 'Código', <input id="code" className={`input${errors.code ? ' invalid' : ''}`} value={form.code} onChange={set('code')} disabled={editing} maxLength={8} />,
          editing ? 'El código no se puede cambiar' : 'Ejemplo: OBRA-005')}
        {field('name', 'Nombre', <input id="name" className={`input${errors.name ? ' invalid' : ''}`} value={form.name} onChange={set('name')} maxLength={120} />)}
        {field('client', 'Cliente', <input id="client" className={`input${errors.client ? ' invalid' : ''}`} value={form.client} onChange={set('client')} maxLength={120} />)}
        {field('location', 'Ubicación', <input id="location" className={`input${errors.location ? ' invalid' : ''}`} value={form.location} onChange={set('location')} maxLength={120} />)}
        {field('status', 'Estado',
          <select id="status" className="select" value={form.status} onChange={set('status')}>
            <option value="ACTIVA">ACTIVA</option>
            <option value="MANTENIMIENTO">MANTENIMIENTO</option>
          </select>, 'SIN CONEXIÓN lo asigna el sistema automáticamente')}
        {field('installationDate', 'Fecha de instalación',
          <input id="installationDate" type="date" className={`input${errors.installationDate ? ' invalid' : ''}`} value={form.installationDate} onChange={set('installationDate')} />)}
        {!editing && field('cameraCount', 'Cámaras de la estación',
          <select id="cameraCount" className="select" value={form.cameraCount} onChange={set('cameraCount')}>
            <option value={2}>2 cámaras</option><option value={3}>3 cámaras</option><option value={4}>4 cámaras</option>
          </select>, 'Se crean también panel solar, batería, Starlink y módem 4G (simulados)')}
      </form>
    </Modal>
  )
}

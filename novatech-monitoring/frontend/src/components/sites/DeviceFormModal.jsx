import { useState } from 'react'
import { Save } from 'lucide-react'
import Modal from '../common/Modal.jsx'
import { devicesApi } from '../../services/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { DEVICE_TYPE, SCENE_OPTIONS } from '../../utils/labels.js'

/** Agregar una camara a una obra o editar un dispositivo (solo administrador). */
export default function DeviceFormModal({ device, siteId, onClose, onSaved }) {
  const editing = Boolean(device)
  const isCamera = !editing || device.type === 'CAMERA'
  const toast = useToast()
  const [form, setForm] = useState({
    name: device?.name || '',
    position: device?.position || '',
    resolution: device?.resolution || '1920x1080',
    scene: device?.scene || 'acceso',
  })
  const [error, setError] = useState(null)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    const found = {}
    if (!form.name.trim()) found.name = 'El nombre es obligatorio'
    if (isCamera && !form.position.trim()) found.position = 'La ubicación es obligatoria'
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    setError(null)
    try {
      const saved = editing
        ? await devicesApi.update(device.id, isCamera ? { ...form, name: form.name.trim() } : { name: form.name.trim() })
        : await devicesApi.createCamera({ siteId, ...form, name: form.name.trim() })
      toast.success(editing ? `Se guardó ${saved.code}.` : `Se agregó la cámara ${saved.code}.`)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(err.message)
      setErrors(err.fieldErrors || {})
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open title={editing ? `Editar ${DEVICE_TYPE[device.type]?.label.toLowerCase()} ${device.code}` : 'Agregar cámara'} onClose={onClose}
      footer={<>
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button type="submit" form="device-form" className="btn btn-primary" disabled={saving}><Save size={15} /> Guardar</button>
      </>}>
      {error && <div className="form-error">{error}</div>}
      <form id="device-form" className="form-grid" onSubmit={submit} noValidate>
        <div className="field full">
          <label htmlFor="dev-name">Nombre</label>
          <input id="dev-name" className={`input${errors.name ? ' invalid' : ''}`} value={form.name} onChange={set('name')} maxLength={80} />
          {errors.name && <span className="error-text">{errors.name}</span>}
        </div>
        {isCamera && (
          <>
            <div className="field full">
              <label htmlFor="dev-position">Ubicación</label>
              <input id="dev-position" className={`input${errors.position ? ' invalid' : ''}`} value={form.position} onChange={set('position')} maxLength={120} placeholder="Ejemplo: Cerco perimétrico, lado oeste" />
              {errors.position && <span className="error-text">{errors.position}</span>}
            </div>
            <div className="field">
              <label htmlFor="dev-resolution">Resolución</label>
              <select id="dev-resolution" className="select" value={form.resolution} onChange={set('resolution')}>
                <option value="1280x720">1280x720</option><option value="1920x1080">1920x1080</option><option value="2560x1440">2560x1440</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="dev-scene">Imagen de la vista CCTV</label>
              <select id="dev-scene" className="select" value={form.scene} onChange={set('scene')}>
                {SCENE_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
          </>
        )}
      </form>
    </Modal>
  )
}

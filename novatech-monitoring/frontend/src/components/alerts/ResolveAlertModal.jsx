import { useState } from 'react'
import { CheckCheck } from 'lucide-react'
import Modal from '../common/Modal.jsx'
import { alertsApi } from '../../services/api.js'
import { useToast } from '../../context/ToastContext.jsx'

/** Resolver una alerta con una nota opcional (administrador o supervisor). */
export default function ResolveAlertModal({ alert, onClose, onDone }) {
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const toast = useToast()

  const submit = async () => {
    setSaving(true)
    setError(null)
    try {
      await alertsApi.resolve(alert.id, note.trim() || null)
      toast.success(`La alerta "${alert.title}" quedó resuelta.`, 'Alerta resuelta')
      onDone?.()
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open title="Resolver alerta" onClose={onClose}
      footer={<>
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button type="button" className="btn btn-success" onClick={submit} disabled={saving}><CheckCheck size={15} /> Resolver</button>
      </>}>
      {error && <div className="form-error">{error}</div>}
      <p style={{ marginTop: 0 }}><strong>{alert.title}</strong><br /><span className="secondary">{alert.description}</span></p>
      <div className="field">
        <label htmlFor="resolve-note">Nota de resolución (opcional)</label>
        <textarea id="resolve-note" className="textarea" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)}
          placeholder="Ejemplo: se verificó en sitio con el vigilante; sin hallazgos." />
      </div>
    </Modal>
  )
}

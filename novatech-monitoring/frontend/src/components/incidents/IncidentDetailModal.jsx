import { useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import Modal from '../common/Modal.jsx'
import { StatusBadge } from '../common/Badges.jsx'
import { LoadingState, ErrorState } from '../common/Feedback.jsx'
import { incidentsApi, usersApi } from '../../services/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { INCIDENT_STATUS, SEVERITY } from '../../utils/labels.js'
import { formatDateTime } from '../../utils/format.js'

/** Transiciones permitidas (las mismas que valida el backend en MonitoringRules). */
const TRANSITIONS = {
  ABIERTA: ['EN_PROCESO', 'RESUELTA'],
  EN_PROCESO: ['RESUELTA'],
  RESUELTA: ['EN_PROCESO', 'CERRADA'],
  CERRADA: [],
}

const ACTION_LABEL = {
  EN_PROCESO: 'Pasar a EN PROCESO',
  RESUELTA: 'Marcar como RESUELTA',
  CERRADA: 'Cerrar incidencia',
}

/** Detalle de una incidencia: datos, responsable, observaciones y cambio de estado. */
export default function IncidentDetailModal({ incidentId, onClose, onChanged }) {
  const toast = useToast()
  const [incident, setIncident] = useState(null)
  const [users, setUsers] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [edit, setEdit] = useState(null)
  const [observation, setObservation] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoadError(null)
    incidentsApi.get(incidentId)
      .then((data) => {
        setIncident(data)
        setEdit({ priority: data.priority, assignedToId: data.assignedToId || '' })
      })
      .catch(setLoadError)
  }

  useEffect(load, [incidentId]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    usersApi.assignable().then(setUsers).catch(() => setUsers([]))
  }, [])

  const run = async (action, successMessage) => {
    setSaving(true)
    try {
      const updated = await action()
      setIncident(updated)
      setEdit({ priority: updated.priority, assignedToId: updated.assignedToId || '' })
      setObservation('')
      toast.success(successMessage)
      onChanged?.()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const saveData = () => run(() => incidentsApi.update(incidentId, {
    priority: edit.priority,
    assignedToId: edit.assignedToId ? Number(edit.assignedToId) : null,
  }), 'Datos de la incidencia guardados.')

  const changeStatus = (status) => run(() => incidentsApi.changeStatus(incidentId, status, observation.trim() || null),
    `La incidencia pasó a ${INCIDENT_STATUS[status].label}.`)

  const closed = incident?.status === 'CERRADA'

  return (
    <Modal open title={incident ? `Incidencia ${incident.code}` : 'Incidencia'} onClose={onClose} size="lg"
      footer={incident && !closed && (
        <>
          {TRANSITIONS[incident.status].map((status) => (
            <button key={status} type="button" disabled={saving}
              className={`btn ${status === 'RESUELTA' ? 'btn-success' : status === 'CERRADA' ? 'btn-primary' : ''}`}
              onClick={() => changeStatus(status)}>
              {ACTION_LABEL[status]}
            </button>
          ))}
        </>
      )}>
      {loadError && <ErrorState error={loadError} onRetry={load} />}
      {!incident && !loadError && <LoadingState />}
      {incident && (
        <div className="stack">
          <div className="row">
            <StatusBadge kind="incidentStatus" value={incident.status} />
            <StatusBadge kind="severity" value={incident.priority} title="Prioridad" />
            <span className="secondary">{incident.siteCode} · {incident.siteName}</span>
          </div>
          <div>
            <h3 style={{ fontSize: 16 }}>{incident.title}</h3>
            <p className="secondary" style={{ margin: '4px 0 0' }}>{incident.description}</p>
          </div>
          <dl className="detail-list">
            <dt>Alerta relacionada</dt><dd>{incident.alertId ? `#${incident.alertId} · ${incident.alertTitle}` : 'Incidencia manual'}</dd>
            <dt>Creada por</dt><dd>{incident.createdByName || '—'}</dd>
            <dt>Fecha de apertura</dt><dd>{formatDateTime(incident.createdAt)}</dd>
            <dt>Fecha de resolución</dt><dd>{formatDateTime(incident.resolvedAt)}</dd>
            <dt>Fecha de cierre</dt><dd>{formatDateTime(incident.closedAt)}</dd>
          </dl>
          {!closed && edit && (
            <div className="form-grid">
              <div className="field">
                <label htmlFor="det-priority">Prioridad</label>
                <select id="det-priority" className="select" value={edit.priority} onChange={(e) => setEdit({ ...edit, priority: e.target.value })}>
                  {['CRITICA', 'ALTA', 'MEDIA', 'BAJA'].map((k) => <option key={k} value={k}>{SEVERITY[k].label}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="det-assigned">Responsable</label>
                <select id="det-assigned" className="select" value={edit.assignedToId} onChange={(e) => setEdit({ ...edit, assignedToId: e.target.value })}>
                  <option value="">Sin asignar</option>
                  {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
              </div>
              <div className="full row" style={{ justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-sm" onClick={saveData} disabled={saving}><Save size={14} /> Guardar cambios</button>
              </div>
            </div>
          )}
          {closed && <dl className="detail-list"><dt>Responsable</dt><dd>{incident.assignedToName || '—'}</dd></dl>}
          <div className="field">
            <label>Observaciones</label>
            <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'inherit', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 6, padding: 10, minHeight: 50 }}>
              {incident.observations || 'Sin observaciones.'}
            </pre>
          </div>
          {!closed && (
            <div className="field">
              <label htmlFor="det-observation">Observación para el próximo cambio de estado (opcional)</label>
              <textarea id="det-observation" className="textarea" maxLength={500} value={observation} onChange={(e) => setObservation(e.target.value)}
                placeholder="Qué se hizo o qué se verificó" />
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

import { useState } from 'react'
import { Pencil, Plus, Save, Users } from 'lucide-react'
import { usersApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { ROLE } from '../utils/labels.js'
import { formatDateTime } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import Modal from '../components/common/Modal.jsx'
import { DataState } from '../components/common/Feedback.jsx'
import { StatusBadge } from '../components/common/Badges.jsx'

/** Alta y edicion de un usuario. La contrasena es obligatoria solo al crear. */
function UserFormModal({ editUser, onClose, onSaved }) {
  const editing = Boolean(editUser)
  const toast = useToast()
  const [form, setForm] = useState({
    name: editUser?.name || '', email: editUser?.email || '', role: editUser?.role || 'OPERADOR',
    active: editUser ? editUser.active : true, password: '',
  })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    const found = {}
    if (!form.name.trim()) found.name = 'El nombre es obligatorio'
    if (!/^\S+@\S+\.\S+$/.test(form.email)) found.email = 'Ingrese un correo válido'
    if (!editing && !form.password) found.password = 'La contraseña es obligatoria'
    if (form.password && (form.password.length < 8 || !/[A-Za-z]/.test(form.password) || !/\d/.test(form.password))) {
      found.password = 'Mínimo 8 caracteres, con letras y números'
    }
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    setError(null)
    try {
      const payload = { name: form.name.trim(), email: form.email.trim(), role: form.role }
      if (editing) {
        await usersApi.update(editUser.id, { ...payload, active: form.active, password: form.password || null })
      } else {
        await usersApi.create({ ...payload, password: form.password })
      }
      toast.success(editing ? `Se guardaron los cambios de ${payload.email}.` : `Se creó el usuario ${payload.email}.`)
      onSaved()
      onClose()
    } catch (err) {
      setError(err.message)
      setErrors(err.fieldErrors || {})
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open title={editing ? `Editar usuario` : 'Nuevo usuario'} onClose={onClose}
      footer={<>
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button type="submit" form="user-form" className="btn btn-primary" disabled={saving}><Save size={15} /> Guardar</button>
      </>}>
      {error && <div className="form-error">{error}</div>}
      <form id="user-form" className="form-grid" onSubmit={submit} noValidate>
        <div className="field full">
          <label htmlFor="u-name">Nombre</label>
          <input id="u-name" className={`input${errors.name ? ' invalid' : ''}`} value={form.name} onChange={set('name')} maxLength={100} />
          {errors.name && <span className="error-text">{errors.name}</span>}
        </div>
        <div className="field full">
          <label htmlFor="u-email">Correo</label>
          <input id="u-email" type="email" className={`input${errors.email ? ' invalid' : ''}`} value={form.email} onChange={set('email')} />
          {errors.email && <span className="error-text">{errors.email}</span>}
        </div>
        <div className="field">
          <label htmlFor="u-role">Rol</label>
          <select id="u-role" className="select" value={form.role} onChange={set('role')}>
            {Object.entries(ROLE).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="u-password">{editing ? 'Nueva contraseña (opcional)' : 'Contraseña'}</label>
          <input id="u-password" type="password" autoComplete="new-password" className={`input${errors.password ? ' invalid' : ''}`} value={form.password} onChange={set('password')} />
          {errors.password ? <span className="error-text">{errors.password}</span> : <span className="hint">Mínimo 8 caracteres, con letras y números</span>}
        </div>
        {editing && (
          <label className="checkbox full"><input type="checkbox" checked={form.active} onChange={set('active')} /> Usuario activo (puede iniciar sesión)</label>
        )}
      </form>
    </Modal>
  )
}

/** Administracion de usuarios (solo administrador). Los usuarios no se borran: se desactivan. */
export default function UsersPage() {
  const { user } = useAuth()
  const polling = usePolling(() => usersApi.list(), [], { interval: 0 })
  const [form, setForm] = useState(null)

  return (
    <>
      <PageHeader icon={Users} title="Usuarios" subtitle="Cuentas de acceso a la plataforma y su rol"
        actions={<button type="button" className="btn btn-primary" onClick={() => setForm({})}><Plus size={16} /> Nuevo usuario</button>} />
      <div className="card">
        <DataState {...polling} onRetry={polling.reload}>
          {(users) => (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Estado</th><th>Último ingreso</th><th>Creado</th><th className="num">Acciones</th></tr></thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td className="cell-main">{u.name}{u.id === user.id && <span className="muted"> (usted)</span>}</td>
                      <td>{u.email}</td>
                      <td><StatusBadge kind="role" value={u.role} /></td>
                      <td>{u.active ? <span className="badge tone-ok">ACTIVO</span> : <span className="badge tone-neutral">DESACTIVADO</span>}</td>
                      <td className="nowrap">{formatDateTime(u.lastLoginAt)}</td>
                      <td className="nowrap">{formatDateTime(u.createdAt)}</td>
                      <td><div className="actions"><button type="button" className="btn btn-sm" onClick={() => setForm(u)}><Pencil size={14} /> Editar</button></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </div>
      {form && <UserFormModal editUser={form.id ? form : null} onClose={() => setForm(null)} onSaved={polling.reload} />}
    </>
  )
}

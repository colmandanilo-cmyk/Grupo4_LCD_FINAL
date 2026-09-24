import { useState } from 'react'
import { Pencil, Plus, Wrench, RotateCcw } from 'lucide-react'
import { devicesApi } from '../../services/api.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useToast } from '../../context/ToastContext.jsx'
import { can } from '../../utils/permissions.js'
import { DEVICE_TYPE } from '../../utils/labels.js'
import { formatDateTime, timeAgo } from '../../utils/format.js'
import { SimulatedBadge, StatusBadge } from '../common/Badges.jsx'
import DeviceFormModal from './DeviceFormModal.jsx'

const MAX_CAMERAS = 4

/** Inventario de dispositivos de una obra, con administracion para el administrador. */
export default function DeviceInventory({ siteId, devices, onChanged }) {
  const { user } = useAuth()
  const toast = useToast()
  const admin = can(user, 'manageDevices')
  const [editing, setEditing] = useState(null)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(null)
  const cameras = devices.filter((d) => d.type === 'CAMERA').length

  const toggleMaintenance = async (device) => {
    const target = device.status === 'MANTENIMIENTO' ? 'ONLINE' : 'MANTENIMIENTO'
    setBusy(device.id)
    try {
      await devicesApi.update(device.id, { status: target })
      toast.success(target === 'MANTENIMIENTO' ? `${device.code} quedó en mantenimiento.` : `${device.code} volvió a operar.`)
      onChanged?.()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3>Dispositivos instalados</h3>
        <span className="row">
          {devices.some((d) => d.simulated) && <SimulatedBadge />}
          {admin && (
            <button type="button" className="btn btn-sm" disabled={cameras >= MAX_CAMERAS} onClick={() => setAdding(true)}
              title={cameras >= MAX_CAMERAS ? 'La obra ya tiene 4 cámaras' : 'Agregar cámara'}>
              <Plus size={14} /> Agregar cámara
            </button>
          )}
        </span>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>Código</th><th>Tipo</th><th>Nombre / ubicación</th><th>Estado</th><th>Última comunicación</th>{admin && <th className="num">Acciones</th>}</tr>
          </thead>
          <tbody>
            {devices.map((d) => {
              const Icon = DEVICE_TYPE[d.type]?.icon
              return (
                <tr key={d.id}>
                  <td className="cell-main nowrap">{d.code}</td>
                  <td className="nowrap">{Icon && <Icon size={14} style={{ verticalAlign: -2, marginRight: 6 }} />}{DEVICE_TYPE[d.type]?.label}</td>
                  <td>{d.name}{d.position && <div className="cell-sub">{d.position}{d.resolution ? ` · ${d.resolution}` : ''}</div>}</td>
                  <td><StatusBadge kind="device" value={d.status} /></td>
                  <td className="nowrap">{formatDateTime(d.lastSeen)}<div className="cell-sub">{timeAgo(d.lastSeen)}</div></td>
                  {admin && (
                    <td>
                      <div className="actions">
                        <button type="button" className="btn btn-sm btn-icon" title="Editar" onClick={() => setEditing(d)}><Pencil size={14} /></button>
                        {d.type === 'CAMERA' && (
                          <button type="button" className="btn btn-sm" disabled={busy === d.id} onClick={() => toggleMaintenance(d)}>
                            {d.status === 'MANTENIMIENTO' ? <><RotateCcw size={14} /> Quitar mantenimiento</> : <><Wrench size={14} /> Mantenimiento</>}
                          </button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {editing && <DeviceFormModal device={editing} onClose={() => setEditing(null)} onSaved={onChanged} />}
      {adding && <DeviceFormModal siteId={siteId} onClose={() => setAdding(false)} onSaved={onChanged} />}
    </div>
  )
}

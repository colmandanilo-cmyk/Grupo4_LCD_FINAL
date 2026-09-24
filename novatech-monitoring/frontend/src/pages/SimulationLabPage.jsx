import { useEffect, useState } from 'react'
import {
  BatteryLow, BatteryWarning, Camera, CameraOff, CheckCircle2, Cloud, Cpu, FlaskConical, Footprints, Pause,
  Play, PlugZap, Radio, RotateCcw, Satellite, Siren, WifiOff, Zap,
} from 'lucide-react'
import { camerasApi, eventsApi, simulationApi, sitesApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import { useToast } from '../context/ToastContext.jsx'
import { EVENT_TYPE } from '../utils/labels.js'
import { formatDateTime, formatNumber, formatTime, timeAgo } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import Modal from '../components/common/Modal.jsx'
import { DataState, EmptyState } from '../components/common/Feedback.jsx'
import { StatusBadge } from '../components/common/Badges.jsx'
import GeneralStateIndicator, { stateDetail } from '../components/common/GeneralStateIndicator.jsx'

/** Escenarios del laboratorio (seccion 32). "camera" = se puede elegir la camara. */
const GROUPS = [
  { title: 'Operación', items: [
    { path: 'restore-normal', label: 'OPERACIÓN NORMAL', desc: 'Restaurar todos los sistemas', icon: CheckCircle2, tone: 'ok' },
  ] },
  { title: 'Seguridad', items: [
    { path: 'motion', label: 'DETECTAR MOVIMIENTO', desc: 'Generar movimiento', icon: Footprints, tone: 'warn', camera: true },
    { path: 'intrusion', label: 'SIMULAR INTRUSIÓN', desc: 'Generar evento y alerta', icon: Siren, tone: 'critical', camera: true },
  ] },
  { title: 'Cámaras', items: [
    { path: 'camera-failure', label: 'DESCONECTAR CÁMARA', desc: 'Colocar cámara offline', icon: CameraOff, tone: 'critical', camera: true },
    { path: 'camera-restore', label: 'RECUPERAR CÁMARA', desc: 'Restaurarla (o todas las caídas)', icon: Camera, tone: 'ok', camera: true },
  ] },
  { title: 'Conectividad', items: [
    { path: 'starlink-failure', label: 'FALLA STARLINK', desc: 'Starlink offline; el sistema cambia a 4G', icon: WifiOff, tone: 'warn' },
    { path: 'starlink-restore', label: 'RESTAURAR STARLINK', desc: 'Recuperar la conexión principal', icon: Satellite, tone: 'ok' },
    { path: 'network-failure', label: 'FALLA STARLINK + 4G', desc: 'Obra sin conectividad, alerta crítica', icon: Radio, tone: 'critical' },
  ] },
  { title: 'Energía', items: [
    { path: 'low-battery', label: 'BATERÍA BAJA', desc: 'Llevar la batería a ~30 %', icon: BatteryLow, tone: 'warn' },
    { path: 'critical-battery', label: 'BATERÍA CRÍTICA', desc: 'Llevar la batería a ~15 %', icon: BatteryWarning, tone: 'critical' },
    { path: 'cloudy-day', label: 'DÍA NUBLADO', desc: 'Reducir la generación solar', icon: Cloud, tone: 'neutral' },
    { path: 'solar-failure', label: 'FALLA PANEL SOLAR', desc: 'Generación = 0', icon: PlugZap, tone: 'critical' },
    { path: 'restore-energy', label: 'RESTAURAR ENERGÍA', desc: 'Normalizar el sistema', icon: Zap, tone: 'ok' },
  ] },
]

const TONE = {
  ok: ['var(--ok-soft)', 'var(--ok)'],
  warn: ['var(--warn-soft)', 'var(--warn)'],
  critical: ['var(--critical-soft)', 'var(--critical)'],
  neutral: ['var(--neutral-soft)', 'var(--neutral)'],
}

/** LABORATORIO DE SIMULACION (secciones 32 a 34). Solo administrador. */
export default function SimulationLabPage() {
  const toast = useToast()
  const status = usePolling(() => simulationApi.status(), [], { interval: 3000 })
  const [siteId, setSiteId] = useState(null)
  const [cameraId, setCameraId] = useState('')
  const [busy, setBusy] = useState(null)
  const [confirmReset, setConfirmReset] = useState(false)

  useEffect(() => {
    if (!siteId && status.data?.sites?.length) setSiteId(status.data.sites[0].siteId)
  }, [status.data, siteId])

  const site = usePolling(() => (siteId ? sitesApi.get(siteId) : Promise.resolve(null)), [siteId], { interval: 3000 })
  const cameras = usePolling(() => (siteId ? camerasApi.list(siteId) : Promise.resolve([])), [siteId], { interval: 5000 })
  const events = usePolling(() => (siteId ? eventsApi.list({ siteId, size: 8 }) : Promise.resolve(null)), [siteId], { interval: 3000 })

  const run = async (key, action, message) => {
    setBusy(key)
    try {
      const result = await action()
      if (result?.message) {
        toast.show(result.message, result.simulatorOnline === false ? 'warn' : 'ok', message)
      } else {
        toast.success(message)
      }
      status.reload()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setBusy(null)
    }
  }

  const runScenario = (item) => run(item.path,
    () => simulationApi.scenario(item.path, siteId, item.camera && cameraId ? Number(cameraId) : null),
    `${item.label} enviado al simulador`)

  const sim = status.data
  const speed = sim?.sites?.[0]?.speed ?? 1
  const running = sim?.sites?.some((s) => s.enabled)
  const selectedSim = sim?.sites?.find((s) => s.siteId === siteId)
  const detail = site.data
  const live = detail?.live

  return (
    <>
      <PageHeader icon={FlaskConical} title="LABORATORIO DE SIMULACIÓN"
        subtitle="Genere situaciones en las obras. Java registra la orden, el simulador Python la ejecuta y el sistema reacciona como con equipos reales." />
      <DataState {...status} onRetry={status.reload}>
        {() => (
          <>
            {!sim.simulatorOnline && (
              <div className="inline-alert tone-critical">
                <Cpu size={16} />
                <span>El simulador Python no está conectado{sim.lastContact ? ` (último contacto ${timeAgo(sim.lastContact)})` : ''}.
                  Inícielo con <strong>start_app.bat</strong> o, desde la carpeta simulator, con <strong>python main.py</strong>. Las órdenes que nadie recoja en 2 minutos expiran.</span>
              </div>
            )}
            <div className="lab-grid">
              <div className="stack">
                <div className="card">
                  <div className="card-header"><h2>Escenarios</h2></div>
                  <div className="card-body">
                    <div className="form-grid" style={{ marginBottom: 16 }}>
                      <div className="field">
                        <label htmlFor="lab-site">OBRA A SIMULAR</label>
                        <select id="lab-site" className="select" value={siteId ?? ''} onChange={(e) => { setSiteId(Number(e.target.value)); setCameraId('') }}>
                          {sim.sites.map((s) => <option key={s.siteId} value={s.siteId}>{s.code} · {s.name}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor="lab-camera">Cámara (escenarios de cámara)</label>
                        <select id="lab-camera" className="select" value={cameraId} onChange={(e) => setCameraId(e.target.value)}>
                          <option value="">Automática (el simulador elige)</option>
                          {(cameras.data || []).filter((c) => c.status !== 'MANTENIMIENTO').map((c) => (
                            <option key={c.deviceId} value={c.deviceId}>{c.code} · {c.name} ({c.status})</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    {GROUPS.map((group) => (
                      <div key={group.title} className="scenario-group">
                        <h3>{group.title}</h3>
                        <div className="scenario-buttons">
                          {group.items.map((item) => {
                            const [bg, fg] = TONE[item.tone]
                            return (
                              <button key={item.path} type="button" className="scenario-btn" disabled={!siteId || busy === item.path}
                                onClick={() => runScenario(item)}>
                                <span className="sb-icon" style={{ background: bg, color: fg }}><item.icon size={17} /></span>
                                <span><strong>{item.label}</strong><span>{item.desc}</span></span>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="card">
                  <div className="card-header"><h2>Bitácora de órdenes</h2><span className="card-note">PENDIENTE → ENVIADO → EJECUTADO</span></div>
                  {sim.commands.length === 0 ? <EmptyState title="Sin órdenes" message="Las órdenes que envíe aparecerán aquí." /> : (
                    <div className="table-wrap" style={{ maxHeight: 360 }}>
                      <table className="table">
                        <thead><tr><th>Hora</th><th>Orden</th><th>Estado</th><th>Resultado</th></tr></thead>
                        <tbody>
                          {sim.commands.map((c) => (
                            <tr key={c.id}>
                              <td className="nowrap tabular">{formatTime(c.createdAt, true)}</td>
                              <td>
                                <div className="cell-main nowrap">{c.commandLabel}</div>
                                <div className="cell-sub">{[c.siteCode || 'Todas las obras', c.deviceCode, c.createdByName].filter(Boolean).join(' · ')}</div>
                              </td>
                              <td><StatusBadge kind="command" value={c.status} /></td>
                              <td className="secondary">{c.result || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>

              <div className="stack">
                <div className="card">
                  <div className="card-header"><h2>Control de simulación</h2>
                    <span className={`data-source${sim.simulatorOnline ? '' : ' offline'}`}><span className="dot" />Simulador {sim.simulatorOnline ? 'conectado' : 'desconectado'}</span>
                  </div>
                  <div className="card-body stack" style={{ gap: 12 }}>
                    <div className="speed-controls">
                      {running ? (
                        <button type="button" className="btn" disabled={busy === 'pause'} onClick={() => run('pause', simulationApi.pause, 'Simulación pausada')}><Pause size={15} /> Pausar</button>
                      ) : (
                        <button type="button" className="btn btn-primary" disabled={busy === 'start'} onClick={() => run('start', simulationApi.start, 'Simulación reanudada')}><Play size={15} /> Reanudar</button>
                      )}
                      <div className="btn-group" role="group" aria-label="Velocidad">
                        {[1, 5, 20].map((v) => (
                          <button key={v} type="button" className={`btn${speed === v ? ' active' : ''}`} disabled={busy === `speed${v}`}
                            onClick={() => run(`speed${v}`, () => simulationApi.speed(v), `Velocidad x${v}`)}>x{v}</button>
                        ))}
                      </div>
                      <button type="button" className="btn" onClick={() => setConfirmReset(true)}><RotateCcw size={15} /> Reiniciar</button>
                    </div>
                    <dl className="detail-list">
                      <dt>Estado</dt><dd>{running ? 'Simulación automática en marcha' : 'En pausa (valores congelados)'}</dd>
                      <dt>Velocidad</dt><dd>x{speed} {speed === 20 && '(un día simulado dura 72 minutos)'}</dd>
                      <dt>Hora virtual de la obra</dt><dd>{selectedSim?.deviceTime ? formatDateTime(selectedSim.deviceTime) : '—'}</dd>
                      <dt>Último escenario</dt><dd>{selectedSim?.scenario || '—'}</dd>
                      <dt>Configuración</dt><dd>Automática {sim.autoEnabled ? 'activada' : 'desactivada'} · velocidad predeterminada x{sim.defaultSpeed}</dd>
                    </dl>
                  </div>
                </div>
                {detail && (
                  <>
                    <GeneralStateIndicator state={detail.site.generalState} detail={stateDetail(detail.activeAlertsBySeverity)} />
                    <div className="card">
                      <div className="card-header"><h3>Estado de {detail.site.code}</h3></div>
                      <div className="card-body metric-tiles">
                        <div className="metric-tile"><div className="label">Batería</div><div className="value">{formatNumber(live?.batteryPercent, 1)} <small>%</small></div></div>
                        <div className="metric-tile"><div className="label">Generación</div><div className="value">{formatNumber(live?.solarGeneration)} <small>W</small></div></div>
                        <div className="metric-tile"><div className="label">Consumo</div><div className="value">{formatNumber(live?.consumption)} <small>W</small></div></div>
                        <div className="metric-tile"><div className="label">Cámaras</div><div className="value">{detail.site.camerasOnline}/{detail.site.cameraCount}</div></div>
                        <div className="metric-tile" style={{ gridColumn: '1 / -1' }}><div className="label">Conexión activa</div><div style={{ marginTop: 4 }}><StatusBadge kind="connection" value={detail.site.activeConnection} /></div></div>
                      </div>
                    </div>
                  </>
                )}
                <div className="card">
                  <div className="card-header"><h3>Eventos recientes de la obra</h3></div>
                  {!events.data?.items?.length ? <EmptyState title="Sin eventos" /> : (
                    <ul className="timeline" style={{ padding: '4px 18px' }}>
                      {events.data.items.map((e) => {
                        const Icon = EVENT_TYPE[e.eventType]?.icon
                        return (
                          <li key={e.id}>
                            <span className="tl-icon" style={{ background: 'var(--bg-subtle)' }}>{Icon && <Icon size={14} />}</span>
                            <div style={{ flex: 1 }}>
                              <div className="tl-time">{formatTime(e.timestamp, true)} · {e.deviceCode || 'Obra'}</div>
                              <div className="tl-text">{e.description}</div>
                            </div>
                            <StatusBadge kind="severity" value={e.severity} />
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </DataState>
      <Modal open={confirmReset} title="Reiniciar simulación" onClose={() => setConfirmReset(false)}
        footer={<>
          <button type="button" className="btn" onClick={() => setConfirmReset(false)}>Cancelar</button>
          <button type="button" className="btn btn-primary" onClick={() => { setConfirmReset(false); run('reset', simulationApi.reset, 'Simulación reiniciada') }}>
            <RotateCcw size={15} /> Reiniciar
          </button>
        </>}>
        Todas las obras vuelven a operación normal, la batería al nivel inicial y el reloj virtual a la hora real,
        con la velocidad y el modo definidos en Configuración. El historial y las alertas no se borran.
      </Modal>
    </>
  )
}

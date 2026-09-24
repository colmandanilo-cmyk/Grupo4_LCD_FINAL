import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  Activity, ArrowLeft, Bell, Calendar, Cctv, ClipboardList, History, LayoutGrid, MapPin, Satellite, SunDim, User,
} from 'lucide-react'
import { sitesApi } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'
import { useAuth } from '../context/AuthContext.jsx'
import { can } from '../utils/permissions.js'
import { formatDate, timeAgo } from '../utils/format.js'
import Tabs from '../components/common/Tabs.jsx'
import { DataState } from '../components/common/Feedback.jsx'
import { SimulatedBadge, StatusBadge } from '../components/common/Badges.jsx'
import GeneralStateIndicator, { stateDetail } from '../components/common/GeneralStateIndicator.jsx'
import OverviewTab from './site-tabs/OverviewTab.jsx'
import CamerasTab from './site-tabs/CamerasTab.jsx'
import EnergyTab from './site-tabs/EnergyTab.jsx'
import CommunicationsTab from './site-tabs/CommunicationsTab.jsx'
import EventsTab from './site-tabs/EventsTab.jsx'
import AlertsTab from './site-tabs/AlertsTab.jsx'
import IncidentsTab from './site-tabs/IncidentsTab.jsx'
import TelemetryTab from './site-tabs/TelemetryTab.jsx'
import NotFoundPage from './NotFoundPage.jsx'

/** CENTRO DE CONTROL – [NOMBRE DE OBRA] (secciones 17 y 19). */
export default function SiteControlCenterPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const polling = usePolling(() => sitesApi.get(id), [id])

  if (polling.error?.status === 404 || (polling.error?.status === 400 && !polling.data)) return <NotFoundPage />

  const activeAlerts = polling.data?.site.activeAlerts || 0
  const tabs = [
    { id: 'general', label: 'Vista general', icon: LayoutGrid },
    { id: 'camaras', label: 'Cámaras', icon: Cctv },
    { id: 'energia', label: 'Energía', icon: SunDim },
    { id: 'comunicaciones', label: 'Comunicaciones', icon: Satellite },
    { id: 'eventos', label: 'Eventos', icon: History },
    { id: 'alertas', label: 'Alertas', icon: Bell, count: activeAlerts },
    ...(can(user, 'incidents') ? [{ id: 'incidencias', label: 'Incidencias', icon: ClipboardList }] : []),
    { id: 'telemetria', label: 'Telemetría', icon: Activity },
  ]
  const requested = params.get('tab')
  const active = tabs.some((t) => t.id === requested) ? requested : 'general'

  return (
    <>
      <Link to="/obras" className="row muted" style={{ marginBottom: 10, fontSize: 13 }}><ArrowLeft size={14} /> Obras monitoreadas</Link>
      <DataState {...polling} onRetry={polling.reload}>
        {(detail) => {
          const s = detail.site
          return (
            <>
              <div className="site-hero">
                <div className="card card-body">
                  <div className="row">
                    <h1 style={{ fontSize: 21 }}>CENTRO DE CONTROL – {s.name.toUpperCase()}</h1>
                  </div>
                  <div className="site-meta">
                    <span><strong>{s.code}</strong></span>
                    <span><User size={14} /> {s.client}</span>
                    <span><MapPin size={14} /> {s.location}</span>
                    <span><Calendar size={14} /> Instalada el {formatDate(s.installationDate)}</span>
                    <StatusBadge kind="site" value={s.status} />
                    <StatusBadge kind="connection" value={s.activeConnection} />
                    {detail.simulated && <SimulatedBadge label="ESTACIÓN SIMULADA" />}
                  </div>
                  <div className="site-meta">
                    <span>Última telemetría: {s.lastUpdate ? timeAgo(s.lastUpdate) : 'sin datos'}</span>
                    {s.dataStale && <span className="badge tone-warn">SIN DATOS RECIENTES</span>}
                  </div>
                </div>
                <GeneralStateIndicator state={s.generalState} detail={stateDetail(detail.activeAlertsBySeverity)} />
              </div>
              <Tabs tabs={tabs} active={active} onChange={(tab) => setParams({ tab }, { replace: true })} />
              {active === 'general' && <OverviewTab detail={detail} onChanged={polling.reload} />}
              {active === 'camaras' && <CamerasTab siteId={s.id} />}
              {active === 'energia' && <EnergyTab siteId={s.id} />}
              {active === 'comunicaciones' && <CommunicationsTab siteId={s.id} />}
              {active === 'eventos' && <EventsTab siteId={s.id} />}
              {active === 'alertas' && <AlertsTab siteId={s.id} />}
              {active === 'incidencias' && <IncidentsTab siteId={s.id} />}
              {active === 'telemetria' && <TelemetryTab siteId={s.id} />}
            </>
          )
        }}
      </DataState>
    </>
  )
}

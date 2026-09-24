import { ClipboardList } from 'lucide-react'
import PageHeader from '../components/common/PageHeader.jsx'
import IncidentsTable from '../components/incidents/IncidentsTable.jsx'

/** Incidencias de todas las obras (seccion 31). Haga clic en una fila para ver el detalle. */
export default function IncidentsPage() {
  return (
    <>
      <PageHeader icon={ClipboardList} title="Incidencias" subtitle="Seguimiento de problemas: ABIERTA → EN PROCESO → RESUELTA → CERRADA" />
      <IncidentsTable />
    </>
  )
}

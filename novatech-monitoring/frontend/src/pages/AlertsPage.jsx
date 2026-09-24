import { Bell } from 'lucide-react'
import PageHeader from '../components/common/PageHeader.jsx'
import AlertsTable from '../components/alerts/AlertsTable.jsx'

/** Alertas de todas las obras (secciones 29 y 30). */
export default function AlertsPage() {
  return (
    <>
      <PageHeader icon={Bell} title="Alertas"
        subtitle="Las alertas de condición se resuelven solas cuando la situación se normaliza; las de intrusión las resuelve una persona." />
      <AlertsTable pageSize={20} />
    </>
  )
}

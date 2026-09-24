import AlertsTable from '../../components/alerts/AlertsTable.jsx'

/** Pestana "Alertas": alertas de la obra con sus acciones (seccion 30). */
export default function AlertsTab({ siteId }) {
  return <AlertsTable siteId={siteId} defaultStatus="ACTIVAS" />
}

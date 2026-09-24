import EnergyPanel from '../../components/monitoring/EnergyPanel.jsx'

/** Pestana "Energia": panel solar, bateria, consumo y graficos (seccion 22). */
export default function EnergyTab({ siteId }) {
  return <EnergyPanel siteId={siteId} />
}

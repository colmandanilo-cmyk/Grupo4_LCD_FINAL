import ConnectivityPanel from '../../components/monitoring/ConnectivityPanel.jsx'

/** Pestana "Comunicaciones": Starlink, 4G y contingencias (secciones 25 y 26). */
export default function CommunicationsTab({ siteId }) {
  return <ConnectivityPanel siteId={siteId} />
}

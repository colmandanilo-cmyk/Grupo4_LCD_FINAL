import { Link } from 'react-router-dom'
import { MapPin } from 'lucide-react'

/** Pagina no encontrada (404). */
export default function NotFoundPage() {
  return (
    <div className="error-page">
      <MapPin size={48} color="var(--brand)" />
      <div className="code">404</div>
      <h1>Página no encontrada</h1>
      <p>La dirección que ingresó no existe en la plataforma.</p>
      <Link className="btn btn-primary" to="/dashboard">Volver al dashboard</Link>
    </div>
  )
}

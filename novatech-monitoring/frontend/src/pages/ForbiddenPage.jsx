import { Link } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'

/** Acceso no autorizado (403). */
export default function ForbiddenPage() {
  return (
    <div className="error-page">
      <ShieldAlert size={48} color="var(--critical)" />
      <div className="code">403</div>
      <h1>Acceso no autorizado</h1>
      <p>Su rol no tiene permiso para ver esta pantalla. Si necesita acceso, contacte al administrador.</p>
      <Link className="btn btn-primary" to="/dashboard">Volver al dashboard</Link>
    </div>
  )
}

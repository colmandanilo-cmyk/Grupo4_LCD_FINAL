import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { BatteryCharging, Cctv, LogIn, Satellite, ShieldCheck } from 'lucide-react'
import logo from '../assets/logo-novatech.svg'
import { useAuth } from '../context/AuthContext.jsx'

const DEMO_ACCOUNTS = [
  { role: 'Administrador', email: 'admin@novatech.local', password: 'Admin123*' },
  { role: 'Supervisor', email: 'supervisor@novatech.local', password: 'Supervisor123*' },
  { role: 'Operador', email: 'operador@novatech.local', password: 'Operador123*' },
]

/** Inicio de sesion (seccion 11). */
export default function LoginPage() {
  const { user, login, expired } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  if (user) return <Navigate to={location.state?.from || '/dashboard'} replace />

  const submit = async (e) => {
    e.preventDefault()
    if (!email.trim() || !password) {
      setError('Ingrese su correo y su contraseña.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate(location.state?.from || '/dashboard', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <section className="login-brand">
        <div>
          <div className="logo">
            <img src={logo} alt="" />
            <strong>NOVA TECH</strong>
          </div>
          <h1>Centro de Monitoreo de Seguridad</h1>
          <p>Vigilancia remota de obras de construcción: cámaras, energía solar, batería y conectividad Starlink con respaldo 4G en una sola plataforma.</p>
          <div className="login-features">
            <div><Cctv size={20} /> Cámaras en tiempo real con alertas de movimiento e intrusión</div>
            <div><BatteryCharging size={20} /> Estado de panel solar y batería de cada estación</div>
            <div><Satellite size={20} /> Contingencia automática de Starlink a 4G</div>
            <div><ShieldCheck size={20} /> Alertas, incidencias, reportes y auditoría</div>
          </div>
        </div>
        <small style={{ color: 'var(--text-on-dark-muted)' }}>Proyecto académico · Los equipos de las obras son simulados.</small>
      </section>
      <section className="login-panel">
        <div className="card login-card">
          <h2>Iniciar sesión</h2>
          <p className="subtitle">Ingrese con su cuenta de la plataforma.</p>
          {expired && !error && <div className="inline-alert tone-warn">Su sesión expiró. Vuelva a iniciar sesión.</div>}
          {error && <div className="form-error" role="alert">{error}</div>}
          <form onSubmit={submit} noValidate>
            <div className="field">
              <label htmlFor="email">Correo</label>
              <input id="email" type="email" className="input" autoComplete="username" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="usuario@novatech.local" autoFocus />
            </div>
            <div className="field">
              <label htmlFor="password">Contraseña</label>
              <input id="password" type="password" className="input" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} />
            </div>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <LogIn size={16} /> {loading ? 'VERIFICANDO...' : 'INICIAR SESIÓN'}
            </button>
          </form>
          <details className="demo-accounts">
            <summary>Cuentas de demostración</summary>
            {DEMO_ACCOUNTS.map((a) => (
              <button key={a.email} type="button" onClick={() => { setEmail(a.email); setPassword(a.password); setError(null) }}>
                <span><strong>{a.role}</strong> · {a.email}</span>
                <span className="muted">{a.password}</span>
              </button>
            ))}
          </details>
        </div>
      </section>
    </div>
  )
}

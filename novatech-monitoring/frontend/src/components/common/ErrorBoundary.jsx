import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

/** Si un componente falla al dibujarse, muestra un mensaje en vez de dejar la pantalla en blanco. */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Error en la interfaz:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error-page">
          <AlertTriangle size={48} color="var(--critical)" />
          <h1>Ocurrió un error inesperado en la pantalla</h1>
          <p>Puede recargar la página. Si el problema continúa, verifique que el backend esté en ejecución.</p>
          <p className="muted">{String(this.state.error?.message || this.state.error)}</p>
          <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
            <RefreshCw size={16} /> Recargar
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

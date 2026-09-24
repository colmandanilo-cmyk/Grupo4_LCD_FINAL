import { Cpu } from 'lucide-react'

/** Aviso de valores simulados (secciones 22 y 57). */
export default function SimulatedNotice({ children }) {
  return (
    <div className="inline-alert tone-sim">
      <Cpu size={16} aria-hidden="true" />
      <span>
        {children || 'Valores simulados con fines demostrativos. No corresponden a características técnicas de productos comerciales.'}
      </span>
    </div>
  )
}

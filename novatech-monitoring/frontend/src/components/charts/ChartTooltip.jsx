import { formatDateTime } from '../../utils/format.js'

/**
 * Tooltip comun de los graficos: titulo (fecha u hora) y una fila por serie
 * con su color, nombre y valor con unidad.
 */
export default function ChartTooltip({ active, payload, label, unit = '', labelIsDate = true, formatter }) {
  if (!active || !payload || payload.length === 0) return null
  const title = labelIsDate ? formatDateTime(label) : label
  return (
    <div className="chart-tooltip">
      <div className="tt-title">{title}</div>
      {payload.filter((p) => p.value !== null && p.value !== undefined).map((p) => (
        <div className="tt-row" key={p.dataKey}>
          <span className="swatch" style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 2, background: p.color || p.fill }} />
          {p.name}
          <strong>{formatter ? formatter(p.value, p) : `${Number(p.value).toLocaleString('es-PE', { maximumFractionDigits: 1 })}${unit ? ' ' + unit : ''}`}</strong>
        </div>
      ))}
    </div>
  )
}

/** Leyenda simple en HTML (siempre visible cuando hay 2 o mas series). */
export function Legend({ items }) {
  return (
    <div className="chart-legend">
      {items.map((item) => (
        <span key={item.label}>
          <span className="swatch" style={{ background: item.color }} />
          {item.label}{item.value !== undefined && <strong> {item.value}</strong>}
        </span>
      ))}
    </div>
  )
}

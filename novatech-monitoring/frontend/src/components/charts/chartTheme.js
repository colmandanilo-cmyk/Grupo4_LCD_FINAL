/**
 * Colores y estilos de los graficos (paleta validada para daltonismo).
 * Series para identidad (azul, naranja); colores de estado solo para estados,
 * siempre acompanados de leyenda o texto.
 */
export const COLORS = {
  series1: '#2a78d6',
  series2: '#eb6834',
  series3: '#1baf7a',
  ok: '#0ca30c',
  warn: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
  neutral: '#9aa3ad',
  grid: '#e1e0d9',
  axis: '#898781',
  text: '#52514e',
}

export const AXIS_PROPS = {
  stroke: COLORS.axis,
  tick: { fill: COLORS.text, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: '#c3c2b7' },
}

export const GRID_PROPS = { stroke: COLORS.grid, strokeDasharray: '0', vertical: false }

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { axisTime } from '../../utils/format.js'
import { AXIS_PROPS, COLORS, GRID_PROPS } from './chartTheme.js'
import ChartTooltip, { Legend } from './ChartTooltip.jsx'
import { EmptyState } from '../common/Feedback.jsx'

/**
 * Grafico de linea generico para series en el tiempo (latencia, telemetria).
 * series: [{ key, name, color }]. Con una sola serie no se muestra leyenda.
 */
export default function TimeSeriesChart({ points, series, unit = '', domain, step = false, height }) {
  if (!points?.length) return <EmptyState title="Sin datos para graficar" message="Aún no hay registros para este período." />
  return (
    <>
      <div className="chart-box" style={height ? { height } : undefined}>
        <ResponsiveContainer>
          <LineChart data={points} margin={{ top: 10, right: 12, left: -6, bottom: 0 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="timestamp" {...AXIS_PROPS} tickFormatter={axisTime} minTickGap={40} />
            <YAxis {...AXIS_PROPS} domain={domain || ['auto', 'auto']} unit={unit ? ` ${unit}` : ''} />
            <Tooltip content={<ChartTooltip unit={unit} />} />
            {series.map((s, i) => (
              <Line key={s.key} type={step ? 'stepAfter' : 'monotone'} dataKey={s.key} name={s.name}
                stroke={s.color || [COLORS.series1, COLORS.series2][i]} strokeWidth={2} dot={false}
                activeDot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {series.length > 1 && <Legend items={series.map((s, i) => ({ label: s.name, color: s.color || [COLORS.series1, COLORS.series2][i] }))} />}
    </>
  )
}

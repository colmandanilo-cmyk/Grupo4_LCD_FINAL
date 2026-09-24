import {
  Area, CartesianGrid, ComposedChart, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { axisTime } from '../../utils/format.js'
import { AXIS_PROPS, COLORS, GRID_PROPS } from './chartTheme.js'
import ChartTooltip, { Legend } from './ChartTooltip.jsx'
import { EmptyState } from '../common/Feedback.jsx'

/** NIVEL DE BATERIA en el tiempo, con los limites de bateria baja y critica. */
export function BatteryHistoryChart({ points, low, critical }) {
  if (!points?.length) return <EmptyState title="Sin historial de batería" message="Aún no hay registros para este período." />
  return (
    <div className="chart-box">
      <ResponsiveContainer>
        <LineChart data={points} margin={{ top: 10, right: 84, left: -14, bottom: 0 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="timestamp" {...AXIS_PROPS} tickFormatter={axisTime} minTickGap={40} />
          <YAxis {...AXIS_PROPS} domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit="%" />
          <Tooltip content={<ChartTooltip unit="%" />} />
          <ReferenceLine y={low} stroke={COLORS.warn} strokeDasharray="4 4"
            label={{ value: `Baja ${low} %`, position: 'right', fill: COLORS.text, fontSize: 11 }} />
          <ReferenceLine y={critical} stroke={COLORS.critical} strokeDasharray="4 4"
            label={{ value: `Crítica ${critical} %`, position: 'right', fill: COLORS.text, fontSize: 11 }} />
          <Line type="monotone" dataKey="batteryPercent" name="Batería" stroke={COLORS.series1} strokeWidth={2}
            dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** GENERACION SOLAR VS CONSUMO (W). */
export function SolarConsumptionChart({ points }) {
  if (!points?.length) return <EmptyState title="Sin historial de energía" message="Aún no hay registros para este período." />
  return (
    <>
      <div className="chart-box">
        <ResponsiveContainer>
          <ComposedChart data={points} margin={{ top: 10, right: 12, left: -6, bottom: 0 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="timestamp" {...AXIS_PROPS} tickFormatter={axisTime} minTickGap={40} />
            <YAxis {...AXIS_PROPS} unit=" W" />
            <Tooltip content={<ChartTooltip unit="W" />} />
            <Area type="monotone" dataKey="solarGeneration" name="Generación solar" stroke={COLORS.series2}
              fill={COLORS.series2} fillOpacity={0.14} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="consumption" name="Consumo" stroke={COLORS.series1} strokeWidth={2}
              dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <Legend items={[{ label: 'Generación solar', color: COLORS.series2 }, { label: 'Consumo', color: COLORS.series1 }]} />
    </>
  )
}

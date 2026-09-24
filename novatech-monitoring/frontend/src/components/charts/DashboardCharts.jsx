import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { AXIS_PROPS, COLORS, GRID_PROPS } from './chartTheme.js'
import ChartTooltip, { Legend } from './ChartTooltip.jsx'

/** Estado de camaras: online / offline / mantenimiento (dona con total al centro). */
export function CameraStatusChart({ counts }) {
  const data = [
    { name: 'Online', value: counts.online, color: COLORS.ok },
    { name: 'Offline', value: counts.offline, color: COLORS.critical },
    { name: 'Mantenimiento', value: counts.maintenance, color: COLORS.neutral },
  ]
  const total = counts.online + counts.offline + counts.maintenance
  return (
    <>
      <div className="chart-box" style={{ position: 'relative' }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data.filter((d) => d.value > 0)} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="88%"
              paddingAngle={data.filter((d) => d.value > 0).length > 1 ? 2 : 0} stroke="#fff"
              strokeWidth={data.filter((d) => d.value > 0).length > 1 ? 2 : 0} isAnimationActive={false}>
              {data.filter((d) => d.value > 0).map((d) => <Cell key={d.name} fill={d.color} />)}
            </Pie>
            <Tooltip content={<ChartTooltip labelIsDate={false} unit="cámaras" />} />
          </PieChart>
        </ResponsiveContainer>
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', pointerEvents: 'none' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 28, fontWeight: 800 }}>{counts.online}/{total}</div>
            <div className="muted" style={{ fontSize: 12 }}>en línea</div>
          </div>
        </div>
      </div>
      <Legend items={data.map((d) => ({ label: d.name, color: d.color, value: d.value }))} />
    </>
  )
}

/** Alertas de las ultimas 24 horas, una barra por hora apilada por severidad. */
export function AlertsTimelineChart({ buckets }) {
  const series = [
    { key: 'media', label: 'Media', color: COLORS.warn },
    { key: 'alta', label: 'Alta', color: COLORS.serious },
    { key: 'critica', label: 'Crítica', color: COLORS.critical },
  ]
  const total = buckets.reduce((sum, b) => sum + b.total, 0)
  return (
    <>
      <div className="chart-box">
        <ResponsiveContainer>
          <BarChart data={buckets} margin={{ top: 8, right: 8, left: -18, bottom: 0 }} barCategoryGap="18%">
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="hour" {...AXIS_PROPS} interval={2} />
            <YAxis {...AXIS_PROPS} allowDecimals={false} />
            <Tooltip cursor={{ fill: 'rgba(31,111,209,0.06)' }} content={<ChartTooltip labelIsDate={false} unit="alertas" />} />
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} stackId="a" fill={s.color} stroke="#fff" strokeWidth={1}
                radius={i === series.length - 1 ? [4, 4, 0, 0] : 0} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Legend items={[...series.map((s) => ({ label: s.label, color: s.color })), { label: `Total 24 h: ${total}`, color: 'transparent' }]} />
    </>
  )
}

/** Bateria por obra, con lineas en los limites de bateria baja y critica. */
export function BatteryBySiteChart({ data, low, critical }) {
  const colorFor = (p) => (p === null ? COLORS.neutral : p <= critical ? COLORS.critical : p <= low ? COLORS.warn : COLORS.series1)
  const rows = data.map((d) => ({ ...d, name: d.code, percent: d.percent === null ? 0 : d.percent }))
  return (
    <div className="chart-box">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 16, right: 84, left: -18, bottom: 0 }} barCategoryGap="30%">
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="name" {...AXIS_PROPS} />
          <YAxis {...AXIS_PROPS} domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit="%" />
          <Tooltip cursor={{ fill: 'rgba(31,111,209,0.06)' }}
            content={<ChartTooltip labelIsDate={false} unit="%" />} />
          <ReferenceLine y={low} stroke={COLORS.warn} strokeDasharray="4 4"
            label={{ value: `Baja ${low} %`, position: 'right', fill: COLORS.text, fontSize: 11 }} />
          <ReferenceLine y={critical} stroke={COLORS.critical} strokeDasharray="4 4"
            label={{ value: `Crítica ${critical} %`, position: 'right', fill: COLORS.text, fontSize: 11 }} />
          <Bar dataKey="percent" name="Batería" radius={[4, 4, 0, 0]} isAnimationActive={false}
            label={{ position: 'top', fill: COLORS.text, fontSize: 11, formatter: (v) => `${Math.round(v)} %` }}>
            {rows.map((d) => <Cell key={d.name} fill={colorFor(d.percent)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Obras conectadas por Starlink, por 4G de respaldo o sin conexion. */
export function ConnectivityChart({ counts }) {
  const data = [
    { name: 'Starlink', value: counts.starlink, color: COLORS.ok },
    { name: '4G de respaldo', value: counts.cellular, color: COLORS.warn },
    { name: 'Sin conexión', value: counts.none, color: COLORS.critical },
  ]
  return (
    <div className="chart-box">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 36, left: 12, bottom: 0 }} barCategoryGap="28%">
          <CartesianGrid {...GRID_PROPS} horizontal={false} vertical />
          <XAxis type="number" {...AXIS_PROPS} allowDecimals={false} />
          <YAxis type="category" dataKey="name" {...AXIS_PROPS} width={110} />
          <Tooltip cursor={{ fill: 'rgba(31,111,209,0.06)' }} content={<ChartTooltip labelIsDate={false} unit="obras" />} />
          <Bar dataKey="value" name="Obras" radius={[0, 4, 4, 0]} isAnimationActive={false}
            label={{ position: 'right', fill: COLORS.text, fontSize: 12 }}>
            {data.map((d) => <Cell key={d.name} fill={d.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

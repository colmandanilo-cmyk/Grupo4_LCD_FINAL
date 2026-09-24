import { useEffect, useState } from 'react'
import { Activity, Bell, ClipboardList, Download, FileChartColumn, Printer, Satellite, SunDim } from 'lucide-react'
import { reportsApi } from '../services/api.js'
import { useToast } from '../context/ToastContext.jsx'
import { formatDateTime, formatNumber, toApiDateTime, toInputDateTime } from '../utils/format.js'
import PageHeader from '../components/common/PageHeader.jsx'
import Tabs from '../components/common/Tabs.jsx'
import { EmptyState, ErrorState, LoadingState } from '../components/common/Feedback.jsx'

const TYPES = [
  { id: 'availability', label: 'Disponibilidad', icon: Activity },
  { id: 'alerts', label: 'Alertas', icon: Bell },
  { id: 'energy', label: 'Energía', icon: SunDim },
  { id: 'connectivity', label: 'Conectividad', icon: Satellite },
  { id: 'incidents', label: 'Incidencias', icon: ClipboardList },
]

const PRESETS = [
  { id: '24h', label: 'Últimas 24 h', hours: 24 },
  { id: '7d', label: 'Últimos 7 días', hours: 24 * 7 },
  { id: '30d', label: 'Últimos 30 días', hours: 24 * 30 },
  { id: 'custom', label: 'Personalizado' },
]

function formatCell(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return formatNumber(value, Number.isInteger(value) ? 0 : 1)
  return value
}

/** REPORTES (seccion 37): cinco reportes con exportacion a CSV e impresion a PDF. */
export default function ReportsPage() {
  const toast = useToast()
  const [type, setType] = useState('availability')
  const [preset, setPreset] = useState('24h')
  const [from, setFrom] = useState(toInputDateTime(new Date(Date.now() - 24 * 3600 * 1000)))
  const [to, setTo] = useState(toInputDateTime(new Date()))
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)

  const period = () => {
    if (preset === 'custom') return { from: toApiDateTime(from), to: toApiDateTime(to) }
    const hours = PRESETS.find((p) => p.id === preset).hours
    return { from: toApiDateTime(toInputDateTime(new Date(Date.now() - hours * 3600 * 1000))), to: undefined }
  }

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setReport(await reportsApi.get(type, period()))
    } catch (e) {
      setError(e)
      setReport(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [type, preset]) // eslint-disable-line react-hooks/exhaustive-deps

  const exportCsv = async () => {
    setExporting(true)
    try {
      await reportsApi.downloadCsv(type, period())
      toast.success('El archivo CSV se descargó.', 'Reporte exportado')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <PageHeader icon={FileChartColumn} title="REPORTES" subtitle="Indicadores del período elegido. Los valores de energía y conectividad son simulados."
        actions={<>
          <button type="button" className="btn" onClick={exportCsv} disabled={!report || exporting}><Download size={15} /> Exportar CSV</button>
          <button type="button" className="btn" onClick={() => window.print()} disabled={!report}><Printer size={15} /> Imprimir / Guardar PDF</button>
        </>} />
      <div className="no-print"><Tabs tabs={TYPES} active={type} onChange={setType} /></div>
      <div className="filters no-print">
        <div className="btn-group" role="group" aria-label="Período">
          {PRESETS.map((p) => (
            <button key={p.id} type="button" className={`btn${preset === p.id ? ' active' : ''}`} onClick={() => setPreset(p.id)}>{p.label}</button>
          ))}
        </div>
        {preset === 'custom' && (
          <>
            <label className="row">Desde <input type="datetime-local" className="input" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
            <label className="row">Hasta <input type="datetime-local" className="input" value={to} onChange={(e) => setTo(e.target.value)} /></label>
            <button type="button" className="btn btn-primary" onClick={load}>Generar</button>
          </>
        )}
      </div>
      {loading && !report && <LoadingState message="Generando reporte..." />}
      {error && <ErrorState error={error} onRetry={load} title="No se pudo generar el reporte" />}
      {report && (
        <div className="stack">
          <div className="print-only">
            <h1>NOVA TECH · {report.title}</h1>
          </div>
          <div className="card card-body">
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
              <h2 style={{ fontSize: 16 }}>{report.title}</h2>
              <span className="card-note">Período: {formatDateTime(report.from)} a {formatDateTime(report.to)} · generado {formatDateTime(report.generatedAt)}</span>
            </div>
            <div className="report-summary">
              {report.summary.map((item) => (
                <div key={item.label} className="metric-tile">
                  <div className="label">{item.label}</div>
                  <div className="value" style={{ fontSize: 16 }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            {report.rows.length === 0 ? <EmptyState title="Sin datos en el período" /> : (
              <div className="table-wrap">
                <table className="table">
                  <thead><tr>{report.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>
                    {report.rows.map((row, i) => (
                      <tr key={i}>
                        {row.map((cell, j) => (
                          <td key={j} className={typeof cell === 'number' ? 'num' : j === 0 ? 'cell-main' : undefined}>{formatCell(cell)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}

/** Titulo de pantalla con subtitulo y botones de accion. */
export default function PageHeader({ icon: Icon, title, subtitle, actions }) {
  return (
    <div className="page-header">
      <div>
        <h1>{Icon && <Icon size={22} aria-hidden="true" />}{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="page-actions no-print">{actions}</div>}
    </div>
  )
}

import { ChevronLeft, ChevronRight } from 'lucide-react'

/** Paginacion simple: "Mostrando 1-20 de 134". page empieza en 0. */
export default function Pagination({ page, size, total, onChange }) {
  if (!total) return null
  const pages = Math.max(1, Math.ceil(total / size))
  const from = page * size + 1
  const to = Math.min(total, (page + 1) * size)
  return (
    <div className="pagination">
      <span>Mostrando {from}-{to} de {total}</span>
      <div className="row">
        <button type="button" className="btn btn-sm" disabled={page === 0} onClick={() => onChange(page - 1)}>
          <ChevronLeft size={14} /> Anterior
        </button>
        <span className="tabular">Página {page + 1} de {pages}</span>
        <button type="button" className="btn btn-sm" disabled={page + 1 >= pages} onClick={() => onChange(page + 1)}>
          Siguiente <ChevronRight size={14} />
        </button>
      </div>
    </div>
  )
}

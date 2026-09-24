/** Pestanas. tabs: [{ id, label, icon, count }] */
export default function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(({ id, label, icon: Icon, count }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={active === id}
          className={`tab${active === id ? ' active' : ''}`}
          onClick={() => onChange(id)}
        >
          {Icon && <Icon size={15} aria-hidden="true" />}
          {label}
          {count > 0 && <span className="count">{count}</span>}
        </button>
      ))}
    </div>
  )
}

export interface TabItem {
  id: string
  label: string
}

/** Horizontally-scrolling tab bar — tabs stay on one line and scroll instead of wrapping/clustering as they grow. */
export function TabBar({ tabs, activeId, onChange }: { tabs: TabItem[]; activeId: string; onChange: (id: string) => void }) {
  return (
    <div className="knp-tabbar">
      <div className="knp-tabbar-scroll" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeId === tab.id}
            onClick={() => onChange(tab.id)}
            className={`knp-tab ${activeId === tab.id ? 'knp-tab-active' : ''}`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  )
}

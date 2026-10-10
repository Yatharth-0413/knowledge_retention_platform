import { useState } from 'react'
import { ContributionActivity } from './ContributionActivity'
import { DependencyAnalyzer } from './DependencyAnalyzer'
import { KnowledgeRecommendations } from './KnowledgeRecommendations'
import { Dropdown, DropdownItem } from './ui/Dropdown'

type InsightView = 'dependency' | 'contribution' | 'recommendations'

const VIEWS: { id: InsightView; label: string; description: string }[] = [
  {
    id: 'dependency',
    label: 'Dependency analyzer',
    description:
      "Topics where documented knowledge is concentrated around one person. This reflects team knowledge distribution, not the person.",
  },
  {
    id: 'contribution',
    label: 'Contribution activity',
    description: 'Documents uploaded and topics contributed per person. This tracks documented contribution, not performance.',
  },
  {
    id: 'recommendations',
    label: 'Knowledge recommendations',
    description:
      "Functional (business/process) vs technical knowledge, split by role, with who's still missing documented evidence on each topic.",
  },
]

export function InsightsPanel({ teamId, refreshKey }: { teamId: number; refreshKey: number }) {
  const [view, setView] = useState<InsightView>('dependency')
  const current = VIEWS.find((v) => v.id === view)!

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <h2 className="knp-section-title">{current.label}</h2>
          <p className="mt-1 text-sm text-gray-500">{current.description}</p>
        </div>
        <Dropdown
          align="right"
          trigger={({ toggle }) => (
            <button type="button" onClick={toggle} className="knp-btn-secondary shrink-0">
              {current.label}
              <span className="ml-1.5 text-gray-400">▾</span>
            </button>
          )}
        >
          {(close) => (
            <div className="w-60">
              {VIEWS.map((v) => (
                <DropdownItem
                  key={v.id}
                  active={v.id === view}
                  onClick={() => {
                    setView(v.id)
                    close()
                  }}
                >
                  {v.label}
                </DropdownItem>
              ))}
            </div>
          )}
        </Dropdown>
      </div>

      {view === 'dependency' && <DependencyAnalyzer teamId={teamId} key={`dependency-${refreshKey}`} />}
      {view === 'contribution' && <ContributionActivity teamId={teamId} key={`contributions-${refreshKey}`} />}
      {view === 'recommendations' && <KnowledgeRecommendations teamId={teamId} key={`recommendations-${refreshKey}`} />}
    </div>
  )
}

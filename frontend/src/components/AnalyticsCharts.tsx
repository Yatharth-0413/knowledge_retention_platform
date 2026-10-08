import type { ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { DocumentTypeCount, FreshnessBreakdown, KnowledgeByMemberItem, KnowledgeByTopicItem } from '../api/types'

export const BRAND = '#c8102e'
export const BRAND_LIGHT = '#e8899a'
const FRESHNESS_COLORS: Record<'New' | 'Medium' | 'Old', string> = {
  New: '#22c55e',
  Medium: '#f59e0b',
  Old: '#9ca3af',
}
const TYPE_COLORS = ['#c8102e', '#f59e0b', '#22c55e', '#3b82f6', '#8b5cf6']

export function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="knp-card p-4">
      <p className="knp-section-title mb-3">{title}</p>
      {children}
    </div>
  )
}

export function KnowledgeByMemberChart({ data }: { data: KnowledgeByMemberItem[] }) {
  if (data.length === 0) return null
  return (
    <ChartCard title="Average knowledge level by member">
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 42)}>
        <BarChart data={data} layout="vertical" margin={{ left: 12, right: 24 }}>
          <CartesianGrid horizontal={false} stroke="#f1f5f9" />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => `${value}%`} />
          <Bar dataKey="avg_score" fill={BRAND} radius={[0, 4, 4, 0]} barSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

export function KnowledgeByTopicChart({ data }: { data: KnowledgeByTopicItem[] }) {
  if (data.length === 0) return null
  const top = [...data].sort((a, b) => b.avg_score - a.avg_score).slice(0, 8)
  return (
    <ChartCard title="Average knowledge level by topic (top 8)">
      <ResponsiveContainer width="100%" height={Math.max(180, top.length * 36)}>
        <BarChart data={top} layout="vertical" margin={{ left: 12, right: 24 }}>
          <CartesianGrid horizontal={false} stroke="#f1f5f9" />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="topic_name" width={120} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => `${value}%`} />
          <Bar dataKey="avg_score" fill={BRAND_LIGHT} radius={[0, 4, 4, 0]} barSize={16} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

export function FreshnessDonutChart({ data }: { data: FreshnessBreakdown }) {
  const total = data.new + data.medium + data.old
  if (total === 0) return null
  const slices = [
    { label: 'New' as const, value: data.new },
    { label: 'Medium' as const, value: data.medium },
    { label: 'Old' as const, value: data.old },
  ].filter((s) => s.value > 0)

  return (
    <ChartCard title="Knowledge freshness">
      <div className="flex items-center gap-4">
        <ResponsiveContainer width="100%" height={160}>
          <PieChart>
            <Pie data={slices} dataKey="value" nameKey="label" innerRadius={40} outerRadius={70} paddingAngle={2}>
              {slices.map((s) => (
                <Cell key={s.label} fill={FRESHNESS_COLORS[s.label]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
        <ul className="shrink-0 space-y-1 text-xs text-gray-600">
          {slices.map((s) => (
            <li key={s.label} className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: FRESHNESS_COLORS[s.label] }} />
              {s.label}: {s.value}
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-2 text-xs text-gray-400">
        How recently each piece of documented knowledge was last updated — separate from how strong it is.
      </p>
    </ChartCard>
  )
}

export function DocumentsByTypeChart({ data }: { data: DocumentTypeCount[] }) {
  if (data.length === 0) return null
  return (
    <ChartCard title="Documents by type">
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ left: 0, right: 12 }}>
          <CartesianGrid vertical={false} stroke="#f1f5f9" />
          <XAxis dataKey="file_type" tick={{ fontSize: 12 }} tickFormatter={(v: string) => v.toUpperCase()} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={36}>
            {data.map((d, i) => (
              <Cell key={d.file_type} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BRAND, BRAND_LIGHT, ChartCard } from './AnalyticsCharts'
import type { RecommendationsSummary } from '../api/types'

export function RecommendationsCoverageChart({ summary }: { summary: RecommendationsSummary }) {
  const totalMembers = summary.functional.member_count + summary.technical.member_count
  if (totalMembers === 0) return null

  const data = [
    { category: 'Functional', member_count: summary.functional.member_count, gap_member_count: summary.functional.gap_member_count },
    { category: 'Technical', member_count: summary.technical.member_count, gap_member_count: summary.technical.gap_member_count },
  ]

  return (
    <ChartCard title="Functional vs technical knowledge coverage">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ left: 0, right: 12 }}>
          <CartesianGrid vertical={false} stroke="#f1f5f9" />
          <XAxis dataKey="category" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="member_count" name="Team members in category" fill={BRAND_LIGHT} radius={[4, 4, 0, 0]} barSize={28} />
          <Bar dataKey="gap_member_count" name="Members with at least one gap" fill={BRAND} radius={[4, 4, 0, 0]} barSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ReactFlow, {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { getTeamGraph } from '../api/graph'
import type { GraphEdge as ApiGraphEdge, GraphNode as ApiGraphNode, GraphNodeType, TeamGraph } from '../api/types'

const COLUMN_X: Record<GraphNodeType, number> = { person: 40, topic: 380, document: 720 }
const ROW_HEIGHT = 76

const TYPE_STYLES: Record<GraphNodeType, { border: string; bg: string; text: string }> = {
  person: { border: 'border-red-400', bg: 'bg-red-50', text: 'text-red-900' },
  topic: { border: 'border-amber-400', bg: 'bg-amber-50', text: 'text-amber-900' },
  document: { border: 'border-emerald-400', bg: 'bg-emerald-50', text: 'text-emerald-900' },
}

interface CardData {
  label: string
  subtitle: string | null
  type: GraphNodeType
  dimmed: boolean
}

function GraphNodeCard({ data }: NodeProps<CardData>) {
  const style = TYPE_STYLES[data.type]
  return (
    <div
      className={`rounded-md border-2 ${style.border} ${style.bg} px-3 py-2 text-xs shadow-sm transition-opacity ${
        data.dimmed ? 'opacity-20' : 'opacity-100'
      }`}
      style={{ width: 180 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#94a3b8' }} />
      <p className={`truncate font-medium ${style.text}`}>{data.label}</p>
      {data.subtitle && <p className="truncate text-[10px] text-gray-500">{data.subtitle}</p>}
      <Handle type="source" position={Position.Right} style={{ background: '#94a3b8' }} />
    </div>
  )
}

const nodeTypes = { card: GraphNodeCard }

function buildLayout(graph: TeamGraph, query: string): { nodes: Node<CardData>[]; edges: Edge[] } {
  const grouped: Record<GraphNodeType, ApiGraphNode[]> = { person: [], topic: [], document: [] }
  graph.nodes.forEach((n) => grouped[n.type].push(n))

  const normalizedQuery = query.trim().toLowerCase()
  const matchedIds = new Set(
    normalizedQuery ? graph.nodes.filter((n) => n.label.toLowerCase().includes(normalizedQuery)).map((n) => n.id) : [],
  )
  const anyMatch = matchedIds.size > 0

  const nodes: Node<CardData>[] = (['person', 'topic', 'document'] as const).flatMap((type) =>
    grouped[type].map((n, i) => ({
      id: n.id,
      type: 'card',
      position: { x: COLUMN_X[type], y: i * ROW_HEIGHT },
      data: { label: n.label, subtitle: n.subtitle, type: n.type, dimmed: anyMatch && !matchedIds.has(n.id) },
    })),
  )

  const edges: Edge[] = graph.edges.map((e: ApiGraphEdge, i: number) => ({
    id: `e${i}`,
    source: e.source,
    target: e.target,
    style: {
      strokeWidth: Math.max(1, e.weight * 3),
      stroke: '#cbd5e1',
      opacity: anyMatch && !matchedIds.has(e.source) && !matchedIds.has(e.target) ? 0.15 : 1,
    },
  }))

  return { nodes, edges }
}

export function GraphPage() {
  const { teamId } = useParams<{ teamId: string }>()
  const [graph, setGraph] = useState<TeamGraph | null>(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<ApiGraphNode | null>(null)

  useEffect(() => {
    if (!teamId) return
    setLoading(true)
    getTeamGraph(Number(teamId))
      .then(setGraph)
      .finally(() => setLoading(false))
  }, [teamId])

  const { nodes, edges } = useMemo(() => (graph ? buildLayout(graph, query) : { nodes: [], edges: [] }), [graph, query])

  if (loading) return <p className="text-gray-500">Loading graph…</p>
  if (!graph) return <p className="text-sm text-red-600">Could not load the knowledge graph.</p>

  const selectedPersonId = selected && selected.type === 'person' ? Number(selected.id.replace('person-', '')) : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="knp-page-title">Knowledge graph</h1>
          <p className="knp-page-subtitle">
            <span className="mr-3">
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />
              People
            </span>
            <span className="mr-3">
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-500" />
              Topics
            </span>
            <span>
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />
              Documents
            </span>
          </p>
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search the graph…"
          className="knp-input w-64"
        />
      </div>

      {graph.nodes.length === 0 ? (
        <p className="text-sm text-gray-500">No documented knowledge yet — upload documents to build the graph.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
          <div className="h-[560px] overflow-hidden knp-card">
            <ReactFlowProvider>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodeClick={(_, node) => setSelected(graph.nodes.find((n) => n.id === node.id) ?? null)}
                fitView
                proOptions={{ hideAttribution: true }}
              >
                <Background gap={16} color="#e5e7eb" />
                <Controls />
                <MiniMap pannable zoomable nodeColor={() => '#fecaca'} />
              </ReactFlow>
            </ReactFlowProvider>
          </div>

          <div className="knp-card p-4">
            {selected ? (
              <div className="space-y-2">
                <p className="knp-section-title">{selected.type}</p>
                <p className="font-medium text-gray-900">{selected.label}</p>
                {selected.subtitle && <p className="text-sm text-gray-500">{selected.subtitle}</p>}
                {selectedPersonId !== null && (
                  <Link to={`/people/${selectedPersonId}`} className="knp-link inline-block text-sm">
                    View profile →
                  </Link>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Click a node to see details. Search above to highlight matches.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

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
const NODE_TYPES: GraphNodeType[] = ['person', 'topic', 'document']
const TYPE_LABELS: Record<GraphNodeType, string> = { person: 'People', topic: 'Topics', document: 'Documents' }

const TYPE_STYLES: Record<GraphNodeType, { border: string; bg: string; text: string; dot: string }> = {
  person: { border: 'border-red-400', bg: 'bg-red-50', text: 'text-red-900', dot: 'bg-red-500' },
  topic: { border: 'border-amber-400', bg: 'bg-amber-50', text: 'text-amber-900', dot: 'bg-amber-500' },
  document: { border: 'border-emerald-400', bg: 'bg-emerald-50', text: 'text-emerald-900', dot: 'bg-emerald-500' },
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
      className={`rounded-md border-2 ${style.border} ${style.bg} px-3 py-2 text-xs shadow-sm transition-opacity duration-300 ${
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

/** The set of node ids to keep at full opacity when focused on `focusNode` - follows the
 * natural Person -> Topic -> Document cascade rather than a plain undirected BFS, so
 * focusing a person shows their topics and those topics' documents, WITHOUT also pulling
 * in other people who happen to share one of those topics (a plain 2-hop BFS would, since
 * person<->topic edges are traversable both ways). Mirrors the focus example in the
 * product's own bug-report doc: person -> their topic(s) -> those topics' document(s). */
export function computeFocusSet(focusNode: ApiGraphNode, edges: ApiGraphEdge[]): Set<string> {
  const ids = new Set<string>([focusNode.id])

  if (focusNode.type === 'person') {
    const topicIds = new Set<string>()
    edges.forEach((e) => {
      if (e.source === focusNode.id) {
        ids.add(e.target)
        topicIds.add(e.target)
      }
    })
    edges.forEach((e) => {
      if (topicIds.has(e.source)) ids.add(e.target)
    })
  } else if (focusNode.type === 'document') {
    const topicIds = new Set<string>()
    edges.forEach((e) => {
      if (e.target === focusNode.id) {
        ids.add(e.source)
        topicIds.add(e.source)
      }
    })
    edges.forEach((e) => {
      if (topicIds.has(e.target)) ids.add(e.source)
    })
  } else {
    // Topic sits in the middle of the chain - its direct people and documents are
    // already a one-hop neighborhood in each direction, no cascade needed.
    edges.forEach((e) => {
      if (e.target === focusNode.id) ids.add(e.source)
      if (e.source === focusNode.id) ids.add(e.target)
    })
  }
  return ids
}

function buildLayout(
  graph: TeamGraph,
  query: string,
  focusNode: ApiGraphNode | null,
  visibleTypes: Set<GraphNodeType>,
): { nodes: Node<CardData>[]; edges: Edge[] } {
  const visibleNodes = graph.nodes.filter((n) => visibleTypes.has(n.type))
  const visibleIds = new Set(visibleNodes.map((n) => n.id))
  const visibleGraphEdges = graph.edges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))

  const normalizedQuery = query.trim().toLowerCase()
  const searchMatchedIds = normalizedQuery
    ? new Set(visibleNodes.filter((n) => n.label.toLowerCase().includes(normalizedQuery)).map((n) => n.id))
    : null

  // Click-to-focus takes priority over search-to-highlight - they're kept mutually
  // exclusive in the component below (picking one clears the other) so the two
  // interactions never visually fight over what's dimmed.
  const focusedIds = focusNode && visibleIds.has(focusNode.id) ? computeFocusSet(focusNode, visibleGraphEdges) : null
  const activeSet = focusedIds ?? searchMatchedIds
  const anyActive = activeSet !== null && activeSet.size > 0

  const grouped: Record<GraphNodeType, ApiGraphNode[]> = { person: [], topic: [], document: [] }
  visibleNodes.forEach((n) => grouped[n.type].push(n))

  const nodes: Node<CardData>[] = NODE_TYPES.flatMap((type) =>
    grouped[type].map((n, i) => ({
      id: n.id,
      type: 'card',
      position: { x: COLUMN_X[type], y: i * ROW_HEIGHT },
      data: { label: n.label, subtitle: n.subtitle, type: n.type, dimmed: anyActive && !activeSet!.has(n.id) },
    })),
  )

  const edges: Edge[] = visibleGraphEdges.map((e, i) => ({
    id: `e${i}`,
    source: e.source,
    target: e.target,
    style: {
      strokeWidth: Math.max(1, e.weight * 3),
      stroke: '#cbd5e1',
      opacity: anyActive && !(activeSet!.has(e.source) && activeSet!.has(e.target)) ? 0.15 : 1,
      transition: 'opacity 300ms',
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
  const [visibleTypes, setVisibleTypes] = useState<Set<GraphNodeType>>(new Set(NODE_TYPES))

  useEffect(() => {
    if (!teamId) return
    setLoading(true)
    getTeamGraph(Number(teamId))
      .then(setGraph)
      .finally(() => setLoading(false))
  }, [teamId])

  const { nodes, edges } = useMemo(
    () => (graph ? buildLayout(graph, query, selected, visibleTypes) : { nodes: [], edges: [] }),
    [graph, query, selected, visibleTypes],
  )

  if (loading) return <p className="text-gray-500">Loading graph…</p>
  if (!graph) return <p className="text-sm text-red-600">Could not load the knowledge graph.</p>

  const selectedPersonId = selected && selected.type === 'person' ? Number(selected.id.replace('person-', '')) : null

  function toggleType(type: GraphNodeType) {
    setVisibleTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) {
        if (next.size === 1) return prev // keep at least one type visible
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to={`/teams/${teamId}`} className="knp-link mb-1 inline-block text-sm">
            ← Back to team
          </Link>
          <h1 className="knp-page-title">Knowledge graph</h1>
          <p className="knp-page-subtitle">
            {NODE_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => toggleType(type)}
                className={`mr-3 inline-flex items-center transition-opacity ${
                  visibleTypes.has(type) ? 'opacity-100' : 'opacity-40'
                }`}
                title={visibleTypes.has(type) ? `Hide ${TYPE_LABELS[type]}` : `Show ${TYPE_LABELS[type]}`}
              >
                <span className={`mr-1 inline-block h-2 w-2 rounded-full ${TYPE_STYLES[type].dot}`} />
                {TYPE_LABELS[type]}
              </button>
            ))}
          </p>
        </div>
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setSelected(null)
          }}
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
                onNodeClick={(_, node) => {
                  setQuery('')
                  setSelected((prev) => (prev?.id === node.id ? null : graph.nodes.find((n) => n.id === node.id) ?? null))
                }}
                onPaneClick={() => setSelected(null)}
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
                <div className="flex items-start justify-between gap-2">
                  <p className="knp-section-title">{selected.type}</p>
                  <button type="button" onClick={() => setSelected(null)} className="knp-link text-xs">
                    Clear focus
                  </button>
                </div>
                <p className="font-medium text-gray-900">{selected.label}</p>
                {selected.subtitle && <p className="text-sm text-gray-500">{selected.subtitle}</p>}
                <p className="text-xs text-gray-400">Directly connected nodes stay highlighted; the rest fade.</p>
                {selectedPersonId !== null && (
                  <Link to={`/people/${selectedPersonId}`} className="knp-link inline-block text-sm">
                    View profile →
                  </Link>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Click a node to focus on it and its direct connections. Search above to highlight matches. Click the
                dots above the graph to show or hide People, Topics, or Documents.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

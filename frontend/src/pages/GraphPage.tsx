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

const COLUMN_X: Record<GraphNodeType, number> = { person: 40, topic: 460, document: 880 }
const ROW_HEIGHT = 68
const NODE_TYPES: GraphNodeType[] = ['person', 'topic', 'document']
const TYPE_LABELS: Record<GraphNodeType, string> = { person: 'People', topic: 'Topics', document: 'Documents' }
const TYPE_GLYPHS: Record<GraphNodeType, string> = { person: 'P', topic: 'T', document: 'D' }

const TYPE_STYLES: Record<GraphNodeType, { solid: string; ring: string; dot: string; edge: string; chip: string }> = {
  person: { solid: 'bg-[var(--color-brand)]', ring: 'border-red-100', dot: 'bg-red-500', edge: '#f3b9c2', chip: 'bg-red-50 text-red-700' },
  topic: { solid: 'bg-amber-500', ring: 'border-amber-100', dot: 'bg-amber-500', edge: '#fbd49b', chip: 'bg-amber-50 text-amber-700' },
  document: {
    solid: 'bg-emerald-500',
    ring: 'border-emerald-100',
    dot: 'bg-emerald-500',
    edge: '#a4ddc2',
    chip: 'bg-emerald-50 text-emerald-700',
  },
}

interface CardData {
  label: string
  subtitle: string | null
  type: GraphNodeType
  dimmed: boolean
  active: boolean
}

function GraphNodeChip({ data }: NodeProps<CardData>) {
  const style = TYPE_STYLES[data.type]
  return (
    <div
      className={`flex items-center gap-2.5 rounded-full border bg-white py-1.5 pl-1.5 pr-4 transition-all duration-300 ${style.ring} ${
        data.dimmed
          ? 'opacity-20 grayscale'
          : data.active
            ? 'shadow-lg ring-2 ring-offset-2 ring-offset-white ' +
              (data.type === 'person' ? 'ring-[var(--color-brand)]' : data.type === 'topic' ? 'ring-amber-400' : 'ring-emerald-400')
            : 'opacity-100 shadow-sm hover:shadow-md'
      }`}
      style={{ width: 216 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: 'transparent', border: 'none' }} />
      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white ${style.solid}`}>
        {TYPE_GLYPHS[data.type]}
      </span>
      <span className="min-w-0">
        <p className="truncate text-xs font-semibold text-gray-900">{data.label}</p>
        {data.subtitle && <p className="truncate text-[10px] text-gray-500">{data.subtitle}</p>}
      </span>
      <Handle type="source" position={Position.Right} style={{ background: 'transparent', border: 'none' }} />
    </div>
  )
}

const nodeTypes = { chip: GraphNodeChip }

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
  const typeById = new Map(visibleNodes.map((n) => [n.id, n.type]))

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
      type: 'chip',
      position: { x: COLUMN_X[type], y: i * ROW_HEIGHT },
      data: {
        label: n.label,
        subtitle: n.subtitle,
        type: n.type,
        dimmed: anyActive && !activeSet!.has(n.id),
        active: focusNode?.id === n.id,
      },
    })),
  )

  const edges: Edge[] = visibleGraphEdges.map((e, i) => {
    const targetType = typeById.get(e.target) ?? 'topic'
    return {
      id: `e${i}`,
      source: e.source,
      target: e.target,
      style: {
        strokeWidth: Math.max(1.5, e.weight * 3),
        stroke: TYPE_STYLES[targetType].edge,
        opacity: anyActive && !(activeSet!.has(e.source) && activeSet!.has(e.target)) ? 0.12 : 0.9,
        transition: 'opacity 300ms, stroke 300ms',
      },
    }
  })

  return { nodes, edges }
}

function TypeToggle({ type, active, onClick }: { type: GraphNodeType; active: boolean; onClick: () => void }) {
  const style = TYPE_STYLES[type]
  return (
    <button
      type="button"
      onClick={onClick}
      title={active ? `Hide ${TYPE_LABELS[type]}` : `Show ${TYPE_LABELS[type]}`}
      className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
        active ? style.chip : 'text-gray-400 hover:bg-gray-100'
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${active ? style.dot : 'bg-gray-300'}`} />
      {TYPE_LABELS[type]}
    </button>
  )
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
    <div className="flex h-[calc(100vh-180px)] min-h-[560px] flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to={`/teams/${teamId}`} className="knp-link mb-1 inline-block text-sm">
            ← Back to team
          </Link>
          <h1 className="knp-page-title">Knowledge graph</h1>
        </div>
      </div>

      {graph.nodes.length === 0 ? (
        <p className="text-sm text-gray-500">No documented knowledge yet — upload documents to build the graph.</p>
      ) : (
        <div className="relative flex-1 overflow-hidden rounded-2xl border border-gray-200 bg-white">
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
              <Background gap={20} size={1.5} color="#f6e9eb" />
              <Controls style={{ borderRadius: 12, overflow: 'hidden', boxShadow: '0 4px 16px rgba(17,17,17,0.08)' }} />
              <MiniMap
                pannable
                zoomable
                maskColor="rgba(248,250,252,0.7)"
                style={{ borderRadius: 12, overflow: 'hidden', boxShadow: '0 4px 16px rgba(17,17,17,0.08)' }}
                nodeColor={(n) => {
                  const type = (n.data as CardData | undefined)?.type
                  return type ? TYPE_STYLES[type].edge : '#e2e8f0'
                }}
              />
            </ReactFlow>
          </ReactFlowProvider>

          <div className="pointer-events-none absolute inset-x-4 top-4 z-10 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white/90 p-2 shadow-md backdrop-blur">
            <div className="pointer-events-auto flex flex-wrap gap-1">
              {NODE_TYPES.map((type) => (
                <TypeToggle key={type} type={type} active={visibleTypes.has(type)} onClick={() => toggleType(type)} />
              ))}
            </div>
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setSelected(null)
              }}
              placeholder="Search the graph…"
              className="knp-input pointer-events-auto w-60 border-gray-200 bg-white"
            />
          </div>

          {selected ? (
            <div className="absolute right-4 top-20 z-10 w-72 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl">
              <div className={`h-1.5 w-full ${TYPE_STYLES[selected.type].solid}`} />
              <div className="space-y-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <span className={`knp-badge ${TYPE_STYLES[selected.type].chip}`}>{TYPE_LABELS[selected.type]}</span>
                  <button type="button" onClick={() => setSelected(null)} className="knp-link text-xs">
                    Clear focus
                  </button>
                </div>
                <p className="font-semibold text-gray-900">{selected.label}</p>
                {selected.subtitle && <p className="text-sm text-gray-500">{selected.subtitle}</p>}
                <p className="text-xs text-gray-400">Directly connected nodes stay highlighted; the rest fade.</p>
                {selectedPersonId !== null && (
                  <Link to={`/people/${selectedPersonId}`} className="knp-btn-secondary mt-1 w-full text-xs">
                    View profile →
                  </Link>
                )}
              </div>
            </div>
          ) : (
            <div className="pointer-events-none absolute bottom-4 left-4 z-10 max-w-xs rounded-xl border border-gray-200 bg-white/90 p-3 text-xs text-gray-500 shadow-sm backdrop-blur">
              Click a node to focus on it and its direct connections. Search above to highlight matches. Toggle the
              chips above to show or hide People, Topics, or Documents.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

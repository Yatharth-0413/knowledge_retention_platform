import { describe, expect, it } from 'vitest'
import type { GraphEdge, GraphNode } from '../api/types'
import { computeFocusSet } from './GraphPage'

// Alice -> Agile, Bob -> Agile, Alice -> DevOps, Agile -> doc-1, DevOps -> doc-2,
// Bob -> Unrelated -> doc-3 (a second, disconnected person/topic/document chain).
const edges: GraphEdge[] = [
  { source: 'person-1', target: 'topic-1', weight: 1 }, // Alice -> Agile
  { source: 'person-2', target: 'topic-1', weight: 1 }, // Bob -> Agile
  { source: 'person-1', target: 'topic-2', weight: 1 }, // Alice -> DevOps
  { source: 'topic-1', target: 'doc-1', weight: 1 }, // Agile -> doc-1
  { source: 'topic-2', target: 'doc-2', weight: 1 }, // DevOps -> doc-2
  { source: 'person-2', target: 'topic-3', weight: 1 }, // Bob -> Unrelated
  { source: 'topic-3', target: 'doc-3', weight: 1 }, // Unrelated -> doc-3
]

function node(id: string, type: GraphNode['type']): GraphNode {
  return { id, type, label: id, subtitle: null }
}

describe('computeFocusSet', () => {
  it('focusing a person includes their own topics and those topics documents, not other people', () => {
    const result = computeFocusSet(node('person-1', 'person'), edges)

    expect(result).toEqual(new Set(['person-1', 'topic-1', 'topic-2', 'doc-1', 'doc-2']))
    // Bob also knows "Agile" (topic-1), but a plain 2-hop BFS would wrongly pull
    // him in via the shared topic - the type-aware cascade must not do that.
    expect(result.has('person-2')).toBe(false)
    expect(result.has('topic-3')).toBe(false)
    expect(result.has('doc-3')).toBe(false)
  })

  it('focusing a document includes its topics and ALL people who know those topics', () => {
    const result = computeFocusSet(node('doc-1', 'document'), edges)

    // Unlike person-focus, document-focus intentionally cascades to every
    // contributor of its topic(s) - both Alice and Bob know "Agile".
    expect(result).toEqual(new Set(['doc-1', 'topic-1', 'person-1', 'person-2']))
  })

  it('focusing a topic is a one-hop neighborhood only (its direct people and documents)', () => {
    const result = computeFocusSet(node('topic-1', 'topic'), edges)

    expect(result).toEqual(new Set(['topic-1', 'person-1', 'person-2', 'doc-1']))
    // "DevOps" (topic-2) and its document aren't connected to topic-1 directly.
    expect(result.has('topic-2')).toBe(false)
    expect(result.has('doc-2')).toBe(false)
  })

  it('focusing an isolated node returns just itself', () => {
    const result = computeFocusSet(node('person-3', 'person'), edges)
    expect(result).toEqual(new Set(['person-3']))
  })
})

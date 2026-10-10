export type UserRole = 'manager' | 'member'

export interface CurrentUser {
  id: number
  name: string
  email: string
  role: UserRole
  designation: string | null
  phone_number: string | null
  team_id: number | null
}

export interface Team {
  id: number
  name: string
  manager_id: number
  created_at: string
}

export interface TeamMember {
  id: number
  name: string
  email: string
  role: UserRole
  designation: string | null
  phone_number: string | null
  team_id: number | null
}

export interface TeamDetail extends Team {
  members: TeamMember[]
}

export type DocumentFileType = 'pdf' | 'docx' | 'xlsx' | 'csv' | 'email'
export type DocumentStatus = 'processing' | 'ready' | 'failed'

export interface KnowledgeDocument {
  id: number
  team_id: number
  uploaded_by_id: number
  uploaded_by_name: string
  filename: string
  file_type: DocumentFileType
  status: DocumentStatus
  error_message: string | null
  parent_document_id: number | null
  created_at: string
}

export interface EmailAttachmentResult {
  filename: string
  status: 'processed' | 'failed' | 'skipped'
  document_id: number | null
  detail: string | null
}

/** Response when the uploaded file was a .msg/.eml email. */
export interface EmailIngestResult {
  document: KnowledgeDocument
  subject: string
  sender_email: string
  sender_name: string
  body_chunk_count: number
  attachments_processed: EmailAttachmentResult[]
  attachments_skipped: EmailAttachmentResult[]
}

export interface TopicSummary {
  id: number
  name: string
  contributor_count: number
  document_count: number
}

export interface TopicPersonEvidence {
  user_id: number
  name: string
  designation: string | null
  score: number
  document_count: number
  freshness_label: FreshnessLabel
}

export interface TopicDocument {
  id: number
  filename: string
  uploaded_by_id: number
  relevance: number
}

export interface TopicDetail {
  id: number
  name: string
  people: TopicPersonEvidence[]
  documents: TopicDocument[]
}

export type FreshnessLabel = 'New' | 'Medium' | 'Old'

export interface UserTopicEvidence {
  topic_id: number
  topic_name: string
  score: number
  document_count: number
  freshness_label: FreshnessLabel
}

export type UserProfile = CurrentUser

export interface CoverageBuckets {
  well_covered: number
  moderately_covered: number
  weakly_covered: number
}

export interface RecentActivityItem {
  user_name: string
  filename: string
  created_at: string
}

export interface KnowledgeByMemberItem {
  user_id: number
  name: string
  avg_score: number
}

export interface KnowledgeByTopicItem {
  topic_id: number
  topic_name: string
  avg_score: number
}

export interface FreshnessBreakdown {
  new: number
  medium: number
  old: number
}

export interface DocumentTypeCount {
  file_type: DocumentFileType
  count: number
}

export interface TeamDashboard {
  member_count: number
  document_count: number
  topic_count: number
  active_contributor_count: number
  coverage: CoverageBuckets
  recent_activity: RecentActivityItem[]
  knowledge_by_member: KnowledgeByMemberItem[]
  knowledge_by_topic: KnowledgeByTopicItem[]
  freshness_breakdown: FreshnessBreakdown
  documents_by_type: DocumentTypeCount[]
}

export interface DependencyContributor {
  user_id: number
  name: string
  share: number
}

export type Concentration = 'HIGH' | 'MODERATE' | 'DISTRIBUTED'

export interface DependencyTopic {
  topic_id: number
  topic_name: string
  contributors: DependencyContributor[]
  concentration: Concentration
}

export type KnowledgeCategory = 'functional' | 'technical' | 'unclassified'
export type TopicRecommendationCategory = 'functional' | 'technical' | 'mixed' | 'unclassified'

export interface ExistingContributor {
  user_id: number
  name: string
  designation: string | null
  category: KnowledgeCategory
  score: number
}

export interface GapCandidate {
  user_id: number
  name: string
  designation: string | null
  category: 'functional' | 'technical'
}

export interface TopicRecommendation {
  topic_id: number
  topic_name: string
  category: TopicRecommendationCategory
  existing_contributors: ExistingContributor[]
  gap_candidates: GapCandidate[]
}

export interface CategorySummary {
  category: 'functional' | 'technical'
  member_count: number
  topic_count: number
  gap_member_count: number
  gap_pair_count: number
}

export interface RecommendationsSummary {
  functional: CategorySummary
  technical: CategorySummary
  unclassified_member_count: number
  unclassified_topic_count: number
}

export interface TeamRecommendations {
  team_id: number
  topics: TopicRecommendation[]
  summary: RecommendationsSummary
}

export interface ContributionActivity {
  user_id: number
  name: string
  document_count: number
  topic_count: number
  last_activity: string | null
}

export type GraphNodeType = 'person' | 'topic' | 'document'

export interface GraphNode {
  id: string
  type: GraphNodeType
  label: string
  subtitle: string | null
}

export interface GraphEdge {
  source: string
  target: string
  weight: number
}

export interface TeamGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface ChatSource {
  document_id: number
  filename: string
  excerpt: string
}

export interface ChatContributor {
  user_id: number
  name: string
  designation: string | null
}

export interface ChatResponse {
  answer: string
  grounded: boolean
  sources: ChatSource[]
  contributors: ChatContributor[]
}

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
  filename: string
  file_type: DocumentFileType
  status: DocumentStatus
  error_message: string | null
  created_at: string
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

export interface UserTopicEvidence {
  topic_id: number
  topic_name: string
  score: number
  document_count: number
}

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

export interface TeamDashboard {
  member_count: number
  document_count: number
  topic_count: number
  active_contributor_count: number
  coverage: CoverageBuckets
  recent_activity: RecentActivityItem[]
}

export interface DependencyContributor {
  user_id: number
  name: string
  share: number
}

export type Concentration = 'HIGH' | 'DISTRIBUTED'

export interface DependencyTopic {
  topic_id: number
  topic_name: string
  contributors: DependencyContributor[]
  concentration: Concentration
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

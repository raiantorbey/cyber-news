export type Section = 'news' | 'vulnerabilities' | 'tools'

export interface SourceBrief {
  id: number
  name: string
  kind: 'rss' | 'nvd' | 'cisa' | 'github'
}

export interface ArticleSummary {
  id: number
  title: string
  canonical_url: string
  excerpt: string | null
  author: string | null
  category: string
  cve_ids: string[]
  published_at: string
  image_url?: string | null
  has_image: boolean
  source: SourceBrief
}

export interface SourceReference {
  source: string
  url: string
}

export interface VulnerabilityBrief {
  cve_id: string
  severity: string | null
  cvss_score: number | null
  kev: boolean
  source_references: SourceReference[]
}

export interface ArticleDetail extends ArticleSummary {
  vulnerabilities: VulnerabilityBrief[]
}

export interface VulnerabilitySummary extends VulnerabilityBrief {
  description: string | null
  vendor: string | null
  product: string | null
  published_at: string | null
  date_added: string | null
  due_date: string | null
}

export interface VulnerabilityDetail extends VulnerabilitySummary {
  modified_at: string | null
  required_action: string | null
  articles: ArticleSummary[]
}

export interface Tool {
  id: number
  full_name: string
  url: string
  description: string | null
  language: string | null
  stars: number
  forks: number
  topics: string[]
  pushed_at: string | null
  discovered_at: string
}

export interface Source extends SourceBrief {
  url: string
  enabled: boolean
  last_success_at: string | null
  latest_run_status: 'running' | 'succeeded' | 'failed' | null
  latest_run_at: string | null
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface OverviewResponse {
  article_count_24h: number
  vulnerability_count_7d: number
  kev_count: number
  tool_count_7d: number
  latest_articles: ArticleSummary[]
  urgent_vulnerabilities: VulnerabilitySummary[]
  latest_tools: Tool[]
}

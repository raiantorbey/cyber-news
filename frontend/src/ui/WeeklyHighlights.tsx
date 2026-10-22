import { ArrowUpRight } from 'lucide-react'
import { useResource } from '../lib/data'
import { timeAgo } from '../lib/format'
import type { Navigate } from '../lib/location'
import type { OverviewResponse } from '../lib/types'
import { CoverArtwork } from './StoryCover'

export function WeeklyHighlights({ navigate }: { navigate: Navigate }) {
  const request = useResource<OverviewResponse>('/overview')
  const stories = request.data?.latest_articles?.slice(0, 3) ?? []
  const pending = request.pending && !request.data
  return <section className="weekly-highlights" aria-label="News of the week">
    <div className="weekly-caption"><h2 className="weekly-kicker">News of the week</h2><span className="weekly-note">Start here for what changed in security.</span></div>
    <div className="weekly-list" aria-busy={pending}>
      {pending ? Array.from({ length: 3 }, (_, index) => <div className="weekly-row weekly-row-loading" aria-hidden="true" key={index}><span className="weekly-index">{String(index + 1).padStart(2, '0')}</span><span className="weekly-body weekly-body-thumb"><span className="weekly-thumb" /><span className="weekly-text"><span className="weekly-loading-line" /><span className="weekly-loading-line weekly-loading-line-short" /></span></span></div>) : stories.map((story, index) => <button type="button" className="weekly-row" key={story.id} onClick={() => navigate({ article: story.id, cve: null })}><span className="weekly-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><span className="weekly-body weekly-body-thumb"><CoverArtwork story={story} variant="thumb" /><span className="weekly-text"><strong>{story.title}</strong><span className="weekly-meta">{story.source.name} · {timeAgo(story.published_at)}</span></span></span><ArrowUpRight size={18} aria-hidden="true" /></button>)}
    </div>
  </section>
}

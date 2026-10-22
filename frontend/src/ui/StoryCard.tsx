import { ArrowRight } from 'lucide-react'
import { dateLabel, timeAgo, titleCase } from '../lib/format'
import type { ArticleSummary } from '../lib/types'
import { Outbound } from './Elements'
import { CoverArtwork } from './StoryCover'

export function StoryCard({ story, onRead, onCve, lead = false, compact = false }: { story: ArticleSummary; onRead: () => void; onCve: (id: string) => void; lead?: boolean; compact?: boolean }) {
  return <article className={`story-preview${lead ? ' story-lead' : ''}${compact ? ' story-compact' : ''}`}>
    <CoverArtwork story={story} variant={lead ? 'lead' : compact ? 'compact' : 'card'} />
    <div className="story-top"><span className="topic-label">{titleCase(story.category)}</span><time dateTime={story.published_at} title={dateLabel(story.published_at)}>{timeAgo(story.published_at)}</time></div>
    <h2><button type="button" onClick={onRead}>{story.title}</button></h2>
    {!compact && <p className="story-excerpt">{story.excerpt || 'Open the original report for the full story.'}</p>}
    {story.cve_ids.length > 0 && <div className="story-cves" aria-label="Linked vulnerabilities">{story.cve_ids.map((id) => <button type="button" key={id} onClick={() => onCve(id)} aria-label={`View ${id} details for ${story.title}`}>{id}</button>)}</div>}
    <div className="story-bottom">{lead ? <Outbound href={story.canonical_url}>{story.source.name}</Outbound> : <span className="publisher">{story.source.name}</span>}{lead ? <button className="read-story" type="button" onClick={onRead} aria-label={`Read brief: ${story.title}`}>Read the brief<ArrowRight size={17} aria-hidden="true" /></button> : <Outbound href={story.canonical_url}><span>Original<span className="visually-hidden">: {story.title}</span></span></Outbound>}</div>
  </article>
}

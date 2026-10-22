import { queryString } from '../lib/client'
import { useResource, useSearchDelay } from '../lib/data'
import { numberLabel, titleCase } from '../lib/format'
import type { Navigate } from '../lib/location'
import type { ArticleSummary, Page, Source } from '../lib/types'
import { Feedback, LoadingCards, PageTurner, Refinements, SearchBox, SelectField } from '../ui/Elements'
import { StoryCard } from '../ui/StoryCard'
import { WeeklyHighlights } from '../ui/WeeklyHighlights'

const topics = ['', 'breach', 'malware', 'ransomware', 'research', 'vulnerability', 'phishing', 'policy', 'general']

export function NewsPage({ params, navigate, sources }: { params: URLSearchParams; navigate: Navigate; sources: Source[] | null }) {
  const query = params.get('q') ?? ''
  const search = useSearchDelay(query)
  const category = params.get('topic') ?? ''
  const source = params.get('publisher') ?? ''
  const range = params.get('range') ?? 'week'
  const page = Math.max(1, Math.floor(Number(params.get('page')) || 1))
  const since = new Date(Math.floor((Date.now() - 7 * 86400_000) / 3600_000) * 3600_000).toISOString()
  const active = Boolean(query || category || source || range !== 'week')
  const request = useResource<Page<ArticleSummary>>(`/articles${queryString({ page, page_size: 12, q: search.length >= 2 ? search : undefined, category, source_id: source, published_after: range === 'week' ? since : undefined })}`)
  const filter = (key: string, value: string, replace = false) => navigate({ [key]: value || null, page: null }, { replace })
  const reset = () => navigate({ q: null, topic: null, publisher: null, range: null, page: null })
  const open = (id: number) => navigate({ article: id, cve: null })
  const stories = request.data?.items ?? []
  const feature = !category && !query && !source && page === 1

  return <>
    <h1 className="visually-hidden">Latest cybersecurity news</h1>
    <div className="discovery-tools"><SearchBox label="Search stories" placeholder="Find a story, topic, or CVE…" value={query} onChange={(value) => filter('q', value, true)} /><Refinements active={Boolean(source || range !== 'week')}><SelectField label="Publisher" value={source} onChange={(value) => filter('publisher', value)}><option value="">All publishers</option>{sources?.filter((item) => item.kind === 'rss').map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</SelectField><SelectField label="Published" value={range} onChange={(value) => filter('range', value)}><option value="week">Past 7 days</option><option value="all">All dates</option></SelectField></Refinements></div>
    <div className="topic-navigation" role="group" aria-label="Browse by topic">{topics.map((topic) => <button type="button" key={topic} aria-pressed={category === topic} onClick={() => filter('topic', topic)}>{topic === '' ? 'All stories' : topic === 'breach' ? 'Breaches' : titleCase(topic)}</button>)}</div>
    {query.length === 1 && <p className="input-note">Type at least two characters to search.</p>}
    <section className="story-collection" aria-label="News stories" aria-busy={request.pending}>
      <div className="collection-meta"><span>{category ? `${titleCase(category)} reporting` : range === 'week' ? 'New this week' : 'From the archive'}<span className="meta-dot" aria-hidden="true">·</span>Latest first</span><span role="status">{request.pending ? 'Finding stories…' : request.data ? `${numberLabel(request.data.total)} stories` : ''}{active && <button type="button" className="reset-action" onClick={reset}>Reset</button>}</span></div>
      {request.pending && !request.data && <LoadingCards />}
      {request.error && <Feedback title="The stories couldn't load" message={request.error.message} retry={request.retry} />}
      {request.data && stories.length === 0 && <Feedback title={active ? 'A fresh search might help.' : 'A quiet moment in the feed.'} message={active ? 'Try another topic, publisher, or date range to find more reporting.' : 'New reporting will appear as publishers update their feeds.'} reset={active ? reset : undefined} />}
      {stories.length > 0 && <>
        {feature && <div className="opening-stories"><StoryCard story={stories[0]} lead onRead={() => open(stories[0].id)} onCve={(id) => navigate({ cve: id, article: null })} /><div className="opening-companions">{stories.slice(1, 3).map((story) => <StoryCard key={story.id} story={story} compact onRead={() => open(story.id)} onCve={(id) => navigate({ cve: id, article: null })} />)}</div></div>}
        {feature && <WeeklyHighlights navigate={navigate} />}
        <div className="story-gallery">{(feature ? stories.slice(3) : stories).map((story) => <StoryCard key={story.id} story={story} onRead={() => open(story.id)} onCve={(id) => navigate({ cve: id, article: null })} />)}</div>
        <PageTurner page={request.data!.page} size={request.data!.page_size} total={request.data!.total} onChange={(next) => navigate({ page: next }, { scroll: true })} />
      </>}
    </section>
  </>
}

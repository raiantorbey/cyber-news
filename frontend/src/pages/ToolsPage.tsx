import { Code2, GitFork, Star } from 'lucide-react'
import { queryString } from '../lib/client'
import { useResource, useSearchDelay } from '../lib/data'
import { dateLabel, numberLabel } from '../lib/format'
import type { Navigate } from '../lib/location'
import type { Page, Tool } from '../lib/types'
import { Introduction } from '../ui/Chrome'
import { Feedback, LoadingCards, Outbound, PageTurner, Refinements, SearchBox, SelectField } from '../ui/Elements'

export function ToolsPage({ params, navigate }: { params: URLSearchParams; navigate: Navigate }) {
  const query = params.get('q') ?? ''
  const search = useSearchDelay(query)
  const language = params.get('language') ?? ''
  const stars = params.get('stars') ?? ''
  const sort = params.get('sort') ?? 'recently_pushed'
  const page = Math.max(1, Math.floor(Number(params.get('page')) || 1))
  const active = Boolean(query || language || stars || sort !== 'recently_pushed')
  const request = useResource<Page<Tool>>(`/tools${queryString({ page, page_size: 12, q: search.length >= 2 ? search : undefined, language, min_stars: stars, sort })}`)
  const filter = (key: string, value: string, replace = false) => navigate({ [key]: value || null, page: null }, { replace })
  const reset = () => navigate({ q: null, language: null, stars: null, sort: null, page: null })

  return <>
    <Introduction label="Made by the community" title="Good tools. Open possibilities." description="Explore security projects and the people building them."><span className="introduction-count">{request.data ? numberLabel(request.data.total) : '—'}</span><span>repositories on GitHub</span></Introduction>
    <div className="discovery-tools"><SearchBox label="Search tools" placeholder="Find your next useful tool…" value={query} onChange={(value) => filter('q', value, true)} /><Refinements active={Boolean(language || stars || sort !== 'recently_pushed')}><SelectField label="Language" value={language} onChange={(value) => filter('language', value)}><option value="">Any language</option>{['Python', 'Go', 'Rust', 'JavaScript', 'TypeScript', 'C', 'C++', 'Ruby'].map((value) => <option key={value}>{value}</option>)}</SelectField><SelectField label="Stars" value={stars} onChange={(value) => filter('stars', value)}><option value="">Any popularity</option><option value="10">10+</option><option value="100">100+</option><option value="1000">1,000+</option></SelectField><SelectField label="Sort by" value={sort} onChange={(value) => filter('sort', value)}><option value="newest">Newly discovered</option><option value="recently_pushed">Recently updated</option><option value="stars">Most starred</option></SelectField></Refinements></div>
    <div className="collection-meta"><span>The open-source collection</span><span>{active && <button className="reset-action" type="button" onClick={reset}>Reset filters</button>}</span></div>
    {query.length === 1 && <p className="input-note">Type at least two characters to search.</p>}
    <section aria-label="Security tools" aria-busy={request.pending}>
      {request.pending && !request.data && <LoadingCards />}
      {request.error && <Feedback title="The tools couldn't load" message={request.error.message} retry={request.retry} />}
      {request.data?.items.length === 0 && <Feedback title={active ? 'Your next tool is still out there.' : 'The collection is getting started.'} message={active ? 'Try a different language or a wider popularity range.' : 'Security projects will appear here after the next successful GitHub source update.'} reset={active ? reset : undefined} />}
      <div className="repository-gallery">{request.data?.items.map((tool) => <article className="repository-card" key={tool.id}><div className="repository-top"><span className="repository-symbol"><Code2 size={24} aria-hidden="true" /></span><span>{tool.language || 'Language not listed'}</span></div><h2>{tool.full_name}</h2><p>{tool.description || 'Visit the repository for project details and documentation.'}</p>{tool.topics.length > 0 && <div className="repository-topics">{tool.topics.slice(0, 3).map((topic) => <span key={topic}>{topic}</span>)}</div>}<div className="repository-stats"><span><Star size={15} aria-hidden="true" /><span className="visually-hidden">Stars: </span>{numberLabel(tool.stars)}</span><span><GitFork size={15} aria-hidden="true" /><span className="visually-hidden">Forks: </span>{numberLabel(tool.forks)}</span></div><div className="repository-bottom"><span>Updated {dateLabel(tool.pushed_at)}</span><Outbound href={tool.url}>GitHub<span className="visually-hidden">: {tool.full_name}</span></Outbound></div></article>)}</div>
      {request.data && <PageTurner page={request.data.page} size={request.data.page_size} total={request.data.total} onChange={(next) => navigate({ page: next }, { scroll: true })} />}
    </section>
  </>
}

import { ArrowRight, Check, CircleAlert, Clock3, X } from 'lucide-react'
import { useId, useLayoutEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useResource } from '../lib/data'
import { dateLabel, sourceHealth, timeAgo } from '../lib/format'
import type { ArticleDetail, Source, VulnerabilityDetail } from '../lib/types'
import { Feedback, LoadingCards, Outbound, RiskLabel } from './Elements'
import { CoverArtwork } from './StoryCover'

function ReadingRoom({ title, label, onClose, children }: { title: string; label: string; onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const closing = useRef(false)
  const exitAnimation = useRef<Animation | null>(null)
  const finish = onClose
  const titleId = useId()

  useLayoutEffect(() => {
    const element = dialog.current!
    const previousOverflow = document.body.style.overflow
    element.showModal()
    document.body.style.overflow = 'hidden'
    closeButton.current?.focus({ preventScroll: true })
    return () => {
      exitAnimation.current?.cancel()
      document.body.style.overflow = previousOverflow
      element.close()
    }
  }, [])

  function dismiss() {
    if (closing.current) return
    closing.current = true
    const element = dialog.current
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || !element?.animate) {
      finish()
      return
    }
    element.classList.add('reader-closing')
    const exit = element.animate([{ opacity: 1, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(6px)' }], { duration: 150, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' })
    exitAnimation.current = exit
    exit.finished.then(() => finish()).catch(() => { /* A navigation can unmount the reader first. */ })
  }

  return createPortal(<dialog ref={dialog} className="reading-room" aria-labelledby={titleId} onCancel={(event) => { event.preventDefault(); dismiss() }} onClick={(event) => { if (event.target === event.currentTarget) dismiss() }} onKeyDown={(event) => {
    if (event.key !== 'Tab' || event.ctrlKey || event.metaKey || event.altKey) return
    const targets = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex="0"]')).filter((element) => element.getClientRects().length > 0)
    const first = targets[0]
    const last = targets.at(-1)
    if (event.shiftKey && document.activeElement === first && last) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last && first) {
      event.preventDefault()
      first.focus()
    }
  }}>
    <div className="reader-surface"><div className="reader-controls"><span>{label}</span><button type="button" ref={closeButton} className="circle-action" aria-label="Close reading view" onClick={dismiss}><X size={20} aria-hidden="true" /></button></div><div className="reader-content"><h2 id={titleId} className="reader-title">{title}</h2>{children}</div></div>
  </dialog>, document.body)
}

export function StoryReader({ id, onClose, onVulnerability }: { id: number; onClose: () => void; onVulnerability: (id: string) => void }) {
  const request = useResource<ArticleDetail>(`/articles/${id}`)
  const article = request.data
  return <ReadingRoom title={article?.title ?? 'Opening the story…'} label="The reading room" onClose={onClose}>
    {request.pending && !article && <LoadingCards count={1} />}
    {request.error && <Feedback title="This story couldn't load" message={request.error.message} retry={request.retry} />}
    {article && <><div className="reader-byline"><span>{article.source.name}</span><time dateTime={article.published_at}>{dateLabel(article.published_at)}</time></div><CoverArtwork story={article} variant="reader" />{article.author && <p className="reader-author">By {article.author}</p>}<p className="excerpt-label">From the original report</p><p className="reader-excerpt">{article.excerpt || 'This publisher has not provided an excerpt. Read the original report for the full story.'}</p><Outbound href={article.canonical_url} primary>Read at {article.source.name}</Outbound>{article.vulnerabilities.length > 0 && <section className="reader-section"><h3>Vulnerabilities in this story</h3><div className="related-records">{article.vulnerabilities.map((item) => <button type="button" key={item.cve_id} onClick={() => onVulnerability(item.cve_id)}><span>{item.cve_id}</span><RiskLabel severity={item.severity} /><ArrowRight size={16} aria-hidden="true" /></button>)}</div></section>}<p className="reader-attribution">This excerpt is supplied by {article.source.name}. The full report belongs to its publisher.</p></>}
  </ReadingRoom>
}

export function VulnerabilityReader({ id, onClose, onArticle }: { id: string; onClose: () => void; onArticle: (id: number) => void }) {
  const request = useResource<VulnerabilityDetail>(`/vulnerabilities/${encodeURIComponent(id)}`)
  const record = request.data
  return <ReadingRoom title={id} label="Understanding the vulnerability" onClose={onClose}>
    {request.pending && !record && <LoadingCards count={1} />}
    {request.error && <Feedback title="This record couldn't load" message={request.error.message} retry={request.retry} />}
    {record && <><div className="reader-risk"><RiskLabel severity={record.severity} /><span>CVSS {record.cvss_score?.toFixed(1) ?? 'not scored'}</span>{record.kev && <span className="exploited-label"><CircleAlert size={15} aria-hidden="true" />Known exploited</span>}</div><p className="reader-excerpt">{record.description || 'No description has been supplied by the data provider.'}</p><dl className="record-facts"><div><dt>Vendor</dt><dd>{record.vendor || 'Not identified'}</dd></div><div><dt>Product</dt><dd>{record.product || 'Not identified'}</dd></div><div><dt>Published</dt><dd>{dateLabel(record.published_at)}</dd></div><div><dt>Last updated</dt><dd>{dateLabel(record.modified_at)}</dd></div></dl>{record.required_action && <section className="action-note"><h3>Recommended action</h3><p>{record.required_action}</p>{record.due_date && <span>Remediation due {dateLabel(record.due_date)}</span>}</section>}{record.source_references.length > 0 && <section className="reader-section"><h3>Go to the original advisory</h3><ul className="advisory-links">{record.source_references.map((reference, index) => <li key={`${reference.url}-${index}`}><span>{reference.source}</span><Outbound href={reference.url}>View advisory<span className="visually-hidden">: {reference.source}</span></Outbound></li>)}</ul></section>}{record.articles.length > 0 && <section className="reader-section"><h3>Related reporting</h3><div className="related-reporting">{record.articles.map((article) => <button type="button" key={article.id} onClick={() => onArticle(article.id)}><span>{article.source.name}</span><strong>{article.title}</strong><ArrowRight size={17} aria-hidden="true" /></button>)}</div></section>}</>}
  </ReadingRoom>
}

export function SourcesReader({ onClose }: { onClose: () => void }) {
  const request = useResource<Source[]>('/sources')
  return <ReadingRoom title="Good reading starts with good sources." label="Behind the reporting" onClose={onClose}>
    <p className="reader-excerpt">Every story links to its original publisher. Vulnerability records come from their listed data providers, and tools link directly to GitHub.</p>
    {request.pending && !request.data && <LoadingCards count={1} />}
    {request.error && <Feedback title="The source list couldn't load" message={request.error.message} retry={request.retry} />}
    {request.data?.length === 0 && <Feedback title="No sources are connected yet." message="Connected publishers will appear here after source configuration." />}
    <ul className="source-directory">{request.data?.map((source) => { const health = sourceHealth(source); const Icon = health === 'Up to date' ? Check : health === 'Update failed' ? CircleAlert : Clock3; return <li key={source.id}><div><h3>{source.name}</h3><span className={health === 'Update failed' ? 'source-health source-failed' : 'source-health'}><Icon size={14} aria-hidden="true" />{health}</span><span className="source-checked">Last successful update: {timeAgo(source.last_success_at)}</span></div><Outbound href={source.url}>Visit<span className="visually-hidden"> {source.name}</span></Outbound></li> })}</ul>
  </ReadingRoom>
}

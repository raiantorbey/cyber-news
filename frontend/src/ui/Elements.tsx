import { ArrowLeft, ArrowRight, ArrowUpRight, Inbox, RotateCw, Search, SlidersHorizontal, X } from 'lucide-react'
import { useId, useRef, type ReactNode } from 'react'

export function Outbound({ href, children, primary = false }: { href: string | null | undefined; children: ReactNode; primary?: boolean }) {
  let url: URL | null = null
  try { url = new URL(href ?? '') } catch { /* An unavailable destination remains plain text. */ }
  if (!url || !['https:', 'http:'].includes(url.protocol)) return <span className="destination-unavailable">{children}<span className="visually-hidden"> (link unavailable)</span></span>
  return <a className={primary ? 'pill-action primary-action' : 'outbound'} href={url.href} target="_blank" rel="noopener noreferrer"><span>{children}</span><ArrowUpRight size={16} aria-hidden="true" />{' '}<span className="visually-hidden">(opens in a new tab)</span></a>
}

export function SearchBox({ label, placeholder, value, onChange }: { label: string; placeholder: string; value: string; onChange: (value: string) => void }) {
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  return <div className="search-box"><label className="visually-hidden" htmlFor={id}>{label}</label><Search size={19} aria-hidden="true" /><input ref={input} id={id} type="search" placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)} autoComplete="off" />{value && <button type="button" className="circle-action search-clear" aria-label={`Clear ${label.toLowerCase()}`} onClick={() => { onChange(''); input.current?.focus() }}><X size={16} aria-hidden="true" /></button>}</div>
}

export function SelectField({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode }) {
  return <label className="select-control"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{children}</select></label>
}

export function Refinements({ active, children }: { active: boolean; children: ReactNode }) {
  return <details className="refinements" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false }} onKeyDown={(event) => { if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus() } }}><summary><SlidersHorizontal size={17} aria-hidden="true" />Filters{active && <span className="filter-indicator" aria-label="active" />}</summary><div className="refinement-fields">{children}</div></details>
}

export function Feedback({ title, message, retry, reset }: { title: string; message: string; retry?: () => void; reset?: () => void }) {
  return <div className="feedback" role={retry ? 'alert' : 'status'}><span className="feedback-icon"><Inbox size={26} aria-hidden="true" /></span><h2>{title}</h2><p>{message}</p>{retry && <button type="button" className="pill-action" onClick={retry}><RotateCw size={16} aria-hidden="true" />Try again</button>}{reset && <button type="button" className="pill-action" onClick={reset}>Reset filters</button>}</div>
}

export function LoadingCards({ count = 3 }: { count?: number }) {
  return <div className="loading-cards" role="status" aria-label="Loading content" aria-busy="true">{Array.from({ length: count }, (_, i) => <div className="loading-card" key={i}><span /><span /><span /><span /></div>)}</div>
}

function paginationItems(current: number, total: number): Array<number | string> {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)
  const visible = new Set([1, total, current - 1, current, current + 1])
  if (current <= 4) [2, 3, 4, 5].forEach((page) => visible.add(page))
  if (current >= total - 3) [total - 4, total - 3, total - 2, total - 1].forEach((page) => visible.add(page))
  const pages = [...visible].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b)
  const items: Array<number | string> = []
  pages.forEach((page, index) => {
    if (index > 0 && page - pages[index - 1] > 1) items.push(`gap-${pages[index - 1]}`)
    items.push(page)
  })
  return items
}

export function PageTurner({ page, size, total, onChange }: { page: number; size: number; total: number; onChange: (page: number) => void }) {
  if (total <= size && page <= 1) return null
  const pages = Math.max(1, Math.ceil(total / size))
  const current = Math.min(Math.max(page, 1), pages)
  return <nav className="page-turner" aria-label="Pagination"><button className="pill-action page-direction" type="button" disabled={current <= 1} aria-label="Previous page" onClick={() => onChange(current - 1)}><ArrowLeft size={16} aria-hidden="true" /><span className="page-direction-label">Previous</span></button><div className="page-numbers">{paginationItems(current, pages).map((item) => typeof item === 'number' ? <button type="button" className="page-number" aria-current={item === current ? 'page' : undefined} aria-label={item === current ? `Page ${item}, current page` : `Go to page ${item}`} onClick={() => onChange(item)} key={item}>{item}</button> : <span className="page-gap" aria-hidden="true" key={item}>…</span>)}</div><span className="visually-hidden" aria-live="polite">Page {current} of {pages}</span><button className="pill-action page-direction" type="button" disabled={current >= pages} aria-label="Next page" onClick={() => onChange(current + 1)}><span className="page-direction-label">Next</span><ArrowRight size={16} aria-hidden="true" /></button></nav>
}

export function RiskLabel({ severity }: { severity: string | null }) {
  const level = severity?.toLowerCase() ?? 'unscored'
  return <span className={`risk-label risk-${level}`}>{level === 'unscored' ? 'Unscored' : level.charAt(0).toUpperCase() + level.slice(1)}</span>
}

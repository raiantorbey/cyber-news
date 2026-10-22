import { ArrowUpRight, CircleAlert } from 'lucide-react'
import { queryString } from '../lib/client'
import { useResource, useSearchDelay } from '../lib/data'
import { dateLabel, numberLabel } from '../lib/format'
import type { Navigate } from '../lib/location'
import type { Page, VulnerabilitySummary } from '../lib/types'
import { Introduction } from '../ui/Chrome'
import { Feedback, LoadingCards, PageTurner, Refinements, RiskLabel, SearchBox, SelectField } from '../ui/Elements'

export function VulnerabilitiesPage({ params, navigate }: { params: URLSearchParams; navigate: Navigate }) {
  const query = params.get('q') ?? ''
  const search = useSearchDelay(query)
  const severity = params.get('severity') ?? ''
  const vendor = params.get('vendor') ?? ''
  const vendorSearch = useSearchDelay(vendor)
  const minimum = params.get('score') ?? ''
  const exploited = params.get('exploited') === 'true'
  const page = Math.max(1, Math.floor(Number(params.get('page')) || 1))
  const active = Boolean(query || severity || vendor || minimum || exploited)
  const request = useResource<Page<VulnerabilitySummary>>(`/vulnerabilities${queryString({ page, page_size: 12, q: search.length >= 2 ? search : undefined, severity, vendor: vendorSearch, min_cvss: minimum, kev: exploited ? true : undefined })}`)
  const filter = (key: string, value: string, replace = false) => navigate({ [key]: value || null, page: null }, { replace })
  const reset = () => navigate({ q: null, severity: null, vendor: null, score: null, exploited: null, page: null })

  return <>
    <Introduction label="A closer look at exposure" title="Know what needs attention." description="Understand the vulnerability. Find the original advisory."><span className="introduction-count">{request.data ? numberLabel(request.data.total) : '—'}</span><span>records from NVD & CISA</span></Introduction>
    <div className="discovery-tools"><SearchBox label="Search vulnerabilities" placeholder="Search a CVE or description…" value={query} onChange={(value) => filter('q', value, true)} /><Refinements active={Boolean(severity || vendor || minimum)}><SelectField label="Severity" value={severity} onChange={(value) => filter('severity', value)}><option value="">All severities</option>{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((value) => <option key={value}>{value}</option>)}</SelectField><SelectField label="Minimum score" value={minimum} onChange={(value) => filter('score', value)}><option value="">Any score</option><option value="4">4.0+</option><option value="7">7.0+</option><option value="9">9.0+</option></SelectField><label className="select-control"><span>Vendor</span><input placeholder="Any vendor" value={vendor} onChange={(event) => filter('vendor', event.target.value, true)} /></label></Refinements></div>
    <div className="collection-meta"><button type="button" className="exploitation-toggle" aria-pressed={exploited} onClick={() => filter('exploited', exploited ? '' : 'true')}><span className="toggle-track" aria-hidden="true"><span /></span>Known exploited only</button><span>{active && <button type="button" className="reset-action" onClick={reset}>Reset filters</button>}</span></div>
    {query.length === 1 && <p className="input-note">Type at least two characters to search.</p>}
    <section aria-label="Vulnerability records" aria-busy={request.pending}>
      {request.pending && !request.data && <LoadingCards />}
      {request.error && <Feedback title="The vulnerability records couldn't load" message={request.error.message} retry={request.retry} />}
      {request.data?.items.length === 0 && <Feedback title="Nothing matches this combination." message="Try a broader search or adjust the severity and exploitation filters." reset={active ? reset : undefined} />}
      <div className="exposure-gallery">{request.data?.items.map((item) => <article className="exposure-card" key={item.cve_id}><div className="exposure-top"><RiskLabel severity={item.severity} /><span className="score-caption">CVSS <strong>{item.cvss_score?.toFixed(1) ?? 'Not scored'}</strong></span></div><h2><button type="button" onClick={() => navigate({ cve: item.cve_id, article: null })}>{item.cve_id}<ArrowUpRight size={19} aria-hidden="true" /></button></h2>{(item.vendor || item.product) && <p className="affected-product">{[item.vendor, item.product].filter(Boolean).join(' · ')}</p>}<p className="exposure-description">{item.description || 'The data provider has not supplied a description yet.'}</p><div className="exposure-bottom"><time dateTime={item.published_at ?? undefined}>{dateLabel(item.published_at)}</time>{item.kev ? <span className="exploited-label"><CircleAlert size={14} aria-hidden="true" />Known exploited</span> : <span>Not listed in KEV</span>}</div></article>)}</div>
      {request.data && <PageTurner page={request.data.page} size={request.data.page_size} total={request.data.total} onChange={(next) => navigate({ page: next }, { scroll: true })} />}
    </section>
  </>
}

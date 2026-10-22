import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { clearResourceCache } from '../lib/data'

const story = { id: 194, title: 'A new phishing campaign targets infrastructure teams', canonical_url: 'https://example.com/report', excerpt: '<strong>This is plain source text</strong>', author: 'News desk', category: 'phishing', cve_ids: ['CVE-2026-1234'], published_at: '2026-09-11T08:00:00Z', source: { id: 1, name: 'Security Wire', kind: 'rss' }, vulnerabilities: [{ cve_id: 'CVE-2026-1234', severity: 'HIGH', cvss_score: 8.1, kev: true }] }
const weeklyStories = [story, { ...story, id: 195, title: 'A critical gateway update is available' }, { ...story, id: 196, title: 'Cloud credentials exposed by a build server' }]
const record = { cve_id: 'CVE-2026-1234', severity: 'HIGH', cvss_score: 8.1, kev: true, description: 'A remote vulnerability affects this product.', vendor: 'Example', product: 'Gateway', published_at: '2026-09-10T08:00:00Z', modified_at: '2026-09-11T08:00:00Z', due_date: '2026-09-25T08:00:00Z', required_action: 'Apply vendor mitigations.', source_references: [{ source: 'NVD', url: 'https://nvd.nist.gov/vuln/detail/CVE-2026-1234' }, { source: 'Vendor', url: 'https://example.com/advisory' }], articles: [story] }

beforeEach(() => {
  clearResourceCache()
  localStorage.clear()
  document.documentElement.dataset.appearance = 'light'
  window.history.replaceState({}, '', '/')
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    let data: unknown = { detail: 'Not found' }
    if (url.endsWith('/sources')) data = [{ id: 1, name: 'Security Wire', kind: 'rss', url: 'https://example.com', enabled: true, last_success_at: new Date().toISOString(), latest_run_status: 'succeeded' }]
    else if (url.includes('/articles/194')) data = story
    else if (url.includes('/articles')) data = { items: [story], page: 1, page_size: 12, total: 120 }
    else if (url.includes('/vulnerabilities/CVE-2026-1234')) data = record
    else if (url.includes('/vulnerabilities')) data = { items: [record], page: 1, page_size: 12, total: 1 }
    else if (url.includes('/overview')) data = { article_count_24h: 1, vulnerability_count_7d: 1, kev_count: 1, tool_count_7d: 1, latest_articles: weeklyStories, urgent_vulnerabilities: [record], latest_tools: [] }
    else if (url.includes('/tools')) data = { items: [], page: 1, page_size: 12, total: 0 }
    return Promise.resolve(new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  }))
})
afterEach(() => vi.unstubAllGlobals())

describe('CyberNews publication', () => {
  it('puts source-attributed reporting directly into the reading page', async () => {
    render(<App />)
    const weekly = (await screen.findByRole('heading', { name: 'News of the week' })).closest('section')!
    expect(await within(weekly).findAllByRole('button')).toHaveLength(3)
    expect(screen.getByRole('article').compareDocumentPosition(weekly) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(await screen.findByRole('button', { name: story.title })).toBeEnabled()
    expect(screen.getByText('<strong>This is plain source text</strong>')).toBeInTheDocument()
    expect(screen.queryByText('This is plain source text')).not.toBeInTheDocument()
    expect(within(screen.getByRole('article')).getByText('Security Wire')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/articles\?.*page_size=12.*published_after=/), expect.anything())
  })

  it('keeps topics, date range and publishers in the URL and request', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Breaches' }))
    expect(window.location.search).toContain('topic=breach')
    await user.click(screen.getByText('Filters', { exact: true }))
    await user.selectOptions(screen.getByLabelText('Published'), 'all')
    await user.selectOptions(screen.getByLabelText('Publisher'), '1')
    expect(window.location.search).toContain('range=all')
    expect(window.location.search).toContain('publisher=1')
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/articles?page=1&page_size=12&category=breach&source_id=1', expect.anything()))
  })

  it('jumps directly to a numbered page', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Go to page 5' }))
    expect(window.location.search).toContain('page=5')
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/articles\?page=5&page_size=12/), expect.anything()))
  })

  it('opens the reading room with attribution and safe original links', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: story.title }))
    const dialog = await screen.findByRole('dialog', { name: story.title })
    expect(within(dialog).getByText('Security Wire')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close reading view' })).toHaveFocus()
    const sourceLink = within(dialog).getByRole('link', { name: /Read at Security Wire/ })
    expect(sourceLink).toHaveAttribute('href', story.canonical_url)
    expect(sourceLink).toHaveAttribute('rel', 'noopener noreferrer')
    fireEvent(dialog, new Event('cancel', { bubbles: false, cancelable: true }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(window.location.search).not.toContain('article')
  })

  it('follows a linked CVE and displays each original advisory', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: story.title }))
    const storyDialog = await screen.findByRole('dialog', { name: story.title })
    await user.click(await within(storyDialog).findByRole('button', { name: /CVE-2026-1234/ }))
    const dialog = await screen.findByRole('dialog', { name: 'CVE-2026-1234' })
    expect(await within(dialog).findByText('Apply vendor mitigations.')).toBeInTheDocument()
    const advisories = within(dialog).getAllByRole('link', { name: /View advisory/ })
    expect(advisories).toHaveLength(2)
    expect(advisories[0]).toHaveAttribute('href', record.source_references[0].url)
    expect(advisories[1]).toHaveAttribute('href', record.source_references[1].url)
  })

  it('opens a linked CVE directly from its news card', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: `View CVE-2026-1234 details for ${story.title}` }))
    expect(await screen.findByRole('dialog', { name: 'CVE-2026-1234' })).toBeInTheDocument()
    expect(window.location.search).toContain('cve=CVE-2026-1234')
    expect(window.location.search).not.toContain('article=')
  })

  it('offers conventional navigation, URL-backed exploitation filters, and theme persistence', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('link', { name: 'Vulnerabilities' }))
    await user.click(screen.getByRole('button', { name: 'Known exploited only' }))
    expect(window.location.search).toContain('view=vulnerabilities')
    expect(window.location.search).toContain('exploited=true')
    expect(await screen.findByRole('button', { name: 'CVE-2026-1234' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Use dark appearance' }))
    expect(document.documentElement).toHaveAttribute('data-appearance', 'dark')
    expect(localStorage.getItem('cybernews-reading-appearance')).toBe('dark')
  })

  it('shows source freshness and the original provider destination', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Our sources' }))
    const dialog = await screen.findByRole('dialog', { name: 'Good reading starts with good sources.' })
    expect(await within(dialog).findByText('Up to date')).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: /Visit.*Security Wire/ })).toHaveAttribute('href', 'https://example.com/')
  })

  it('reuses recent collection data when returning to a section', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('link', { name: 'Tools' }))
    expect(await screen.findByRole('heading', { name: 'The collection is getting started.' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Stories' }))
    await user.click(screen.getByRole('link', { name: 'Tools' }))
    const requests = vi.mocked(fetch).mock.calls.filter(([url]) => String(url).includes('/tools'))
    expect(requests).toHaveLength(1)
  })
})

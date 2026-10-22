import { useEffect } from 'react'
import { useResource } from './lib/data'
import { useLocation } from './lib/location'
import type { Section, Source } from './lib/types'
import { NewsPage } from './pages/NewsPage'
import { ToolsPage } from './pages/ToolsPage'
import { VulnerabilitiesPage } from './pages/VulnerabilitiesPage'
import { Masthead, PublicationFooter } from './ui/Chrome'
import { SourcesReader, StoryReader, VulnerabilityReader } from './ui/ReadingRoom'

export default function App() {
  const { params, navigate } = useLocation()
  const view = params.get('view')
  const section: Section = view === 'tools' || view === 'vulnerabilities' ? view : 'news'
  const sources = useResource<Source[]>(section === 'news' ? '/sources' : null)
  const article = Math.max(0, Number(params.get('article')) || 0)
  const cve = params.get('cve')
  const showSources = params.get('sources') === 'open'
  const openSources = () => navigate({ sources: 'open', article: null, cve: null })
  const closeReader = () => navigate({ article: null, cve: null, sources: null })
  const switchSection = (next: Section) => navigate({ view: next === 'news' ? null : next }, { reset: true, scroll: true })

  useEffect(() => {
    const title = section === 'news' ? 'Cybersecurity, clearly' : section === 'tools' ? 'Security tools' : 'Vulnerabilities'
    document.title = `${title} — CyberNews`
  }, [section])

  return <>
    <a className="skip-to-reading" href="#publication">Skip to main content</a>
    <Masthead section={section} onSection={switchSection} onSources={openSources} />
    <main className="publication" id="publication" tabIndex={-1}>
      <div className="collection-page" key={section}>
        {section === 'news' && <NewsPage params={params} navigate={navigate} sources={sources.data} />}
        {section === 'vulnerabilities' && <VulnerabilitiesPage params={params} navigate={navigate} />}
        {section === 'tools' && <ToolsPage params={params} navigate={navigate} />}
      </div>
    </main>
    <PublicationFooter onSources={openSources} />
    {showSources ? <SourcesReader onClose={closeReader} /> : article ? <StoryReader key={`article-${article}`} id={article} onClose={closeReader} onVulnerability={(id) => navigate({ cve: id, article: null })} /> : cve ? <VulnerabilityReader key={`cve-${cve}`} id={cve} onClose={closeReader} onArticle={(id) => navigate({ article: id, cve: null })} /> : null}
  </>
}

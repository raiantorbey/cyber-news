import { Moon, Rss, Sun } from 'lucide-react'
import { useState, type MouseEvent, type ReactNode } from 'react'
import type { Section } from '../lib/types'

const sections: { id: Section; label: string }[] = [{ id: 'news', label: 'Stories' }, { id: 'vulnerabilities', label: 'Vulnerabilities' }, { id: 'tools', label: 'Tools' }]

function BrandLogo() {
  return <span className="brand-wordmark">Cyber<em>News</em></span>
}

export function Masthead({ section, onSection, onSources }: { section: Section; onSection: (section: Section) => void; onSources: () => void }) {
  const [appearance, setAppearance] = useState(document.documentElement.dataset.appearance ?? 'light')
  const follow = (event: MouseEvent<HTMLAnchorElement>, next: Section) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return
    event.preventDefault()
    onSection(next)
  }
  const toggleAppearance = () => {
    const next = appearance === 'light' ? 'dark' : 'light'
    document.documentElement.dataset.appearance = next
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', next === 'light' ? '#f3f7f4' : '#171e1a')
    try { localStorage.setItem('cybernews-reading-appearance', next) } catch { /* Appearance still works without persistent storage. */ }
    setAppearance(next)
  }
  return <header className="masthead">
    <a className="wordmark" href="/" aria-label="CyberNews home" onClick={(event) => follow(event, 'news')}><BrandLogo /></a>
    <nav className="publication-nav" aria-label="Main navigation">{sections.map((item) => <a href={item.id === 'news' ? '/' : `?view=${item.id}`} aria-current={section === item.id ? 'page' : undefined} onClick={(event) => follow(event, item.id)} key={item.id}>{item.label}</a>)}</nav>
    <div className="masthead-actions"><button className="sources-action" type="button" aria-label="Our sources" onClick={onSources}><Rss size={17} aria-hidden="true" /><span>Our sources</span></button><button className="circle-action appearance-action" type="button" aria-label={`Use ${appearance === 'light' ? 'dark' : 'light'} appearance`} onClick={toggleAppearance}>{appearance === 'light' ? <Moon size={18} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}</button></div>
  </header>
}

export function Introduction({ label, title, description, children }: { label: string; title: string; description: string; children?: ReactNode }) {
  return <div className="introduction"><div>{label && <span className="section-kicker">{label}</span>}<h1>{title}</h1><p>{description}</p></div>{children && <div className="introduction-note">{children}</div>}</div>
}

export function PublicationFooter({ onSources }: { onSources: () => void }) {
  return <footer className="publication-footer"><div><span className="footer-wordmark"><BrandLogo /></span><p>Independent sources. One place to read.</p></div><span>Reporting belongs to the linked publishers.</span><button type="button" className="text-action" onClick={onSources}>Meet the sources<Rss size={15} aria-hidden="true" /></button></footer>
}

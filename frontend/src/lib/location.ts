import { useEffect, useState } from 'react'

type Options = { replace?: boolean; reset?: boolean; scroll?: boolean }
export type Navigate = (patch: Record<string, string | number | null>, options?: Options) => void

export function useLocation() {
  const [query, setQuery] = useState(window.location.search)
  useEffect(() => {
    const update = () => setQuery(window.location.search)
    window.addEventListener('popstate', update)
    return () => window.removeEventListener('popstate', update)
  }, [])

  const navigate: Navigate = (patch, options = {}) => {
    const next = new URLSearchParams(options.reset ? '' : window.location.search)
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    const url = `${window.location.pathname}${next.size ? `?${next}` : ''}`
    if (url !== `${window.location.pathname}${window.location.search}`) {
      window.history[options.replace ? 'replaceState' : 'pushState']({}, '', url)
      setQuery(window.location.search)
    }
    if (options.scroll) {
      window.scrollTo({ top: 0, behavior: 'instant' })
      document.getElementById('publication')?.focus({ preventScroll: true })
    }
  }
  return { params: new URLSearchParams(query), navigate }
}

import { useEffect, useState } from 'react'
import { apiGet } from './client'

type Entry = { value: unknown; expires: number }
const responses = new Map<string, Entry>()
export const clearResourceCache = () => responses.clear()
const fresh = (path: string) => {
  const entry = responses.get(path)
  return entry && entry.expires > Date.now() ? entry.value : null
}

/** Keep short-lived results so returning to a collection feels immediate. */
export function useResource<T>(path: string | null) {
  const [revision, setRevision] = useState(0)
  const [state, setState] = useState<{ path: string | null; data: T | null; pending: boolean; error: Error | null }>(() => ({
    path, data: path ? fresh(path) as T | null : null, pending: Boolean(path && !fresh(path)), error: null,
  }))

  useEffect(() => {
    if (!path) return
    const cached = fresh(path) as T | null
    if (cached && revision === 0) {
      setState({ path, data: cached, pending: false, error: null })
      return
    }
    const controller = new AbortController()
    setState({ path, data: cached, pending: true, error: null })
    apiGet<T>(path, controller.signal).then((data) => {
      if (controller.signal.aborted) return
      if (responses.size >= 80) responses.delete(responses.keys().next().value!)
      responses.set(path, { value: data, expires: Date.now() + 45_000 })
      setState({ path, data, pending: false, error: null })
    }).catch((error: Error) => {
      if (!controller.signal.aborted) setState({ path, data: null, pending: false, error })
    })
    return () => controller.abort()
  }, [path, revision])

  const current = state.path === path ? state : { data: path ? fresh(path) as T | null : null, pending: Boolean(path), error: null }
  return { ...current, retry: () => setRevision((value) => value + 1) }
}

export function useSearchDelay(value: string) {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), 220)
    return () => window.clearTimeout(timer)
  }, [value])
  return settled.trim()
}

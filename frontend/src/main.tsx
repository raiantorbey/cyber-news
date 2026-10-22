import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './publication.css'

let appearance = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
try {
  const saved = localStorage.getItem('cybernews-reading-appearance')
  if (saved === 'light' || saved === 'dark') appearance = saved
} catch { /* Use the system appearance when storage is unavailable. */ }
document.documentElement.dataset.appearance = appearance
document.querySelector('meta[name="theme-color"]')?.setAttribute('content', appearance === 'light' ? '#f3f7f4' : '#171e1a')

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)

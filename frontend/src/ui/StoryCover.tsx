import { Bug, Database, Fish, Landmark, Lock, Microscope, Newspaper, ShieldAlert, Skull, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { API_ROOT } from '../lib/client'
import { titleCase } from '../lib/format'
import type { ArticleSummary } from '../lib/types'

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  vulnerability: Bug,
  malware: Skull,
  ransomware: Lock,
  phishing: Fish,
  breach: Database,
  research: Microscope,
  policy: Landmark,
  general: Newspaper,
}

export function CoverArtwork({ story, variant }: { story: ArticleSummary; variant: 'card' | 'compact' | 'lead' | 'reader' | 'thumb' }) {
  const src = `${API_ROOT}/articles/${story.id}/image`
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const eager = variant === 'lead' || variant === 'reader' || variant === 'thumb'
  if (story.has_image && failedSrc !== src) {
    if (variant === 'thumb') {
      return <img className="weekly-thumb" src={src} alt="" loading="eager" decoding="async" onError={() => setFailedSrc(src)} />
    }
    return <div className={`story-media story-media-${variant}`}><img className={`story-image${variant === 'lead' ? ' story-image-lead' : ''}`} src={src} alt="" loading={eager ? 'eager' : 'lazy'} decoding="async" fetchPriority={variant === 'lead' ? 'high' : 'auto'} onError={() => setFailedSrc(src)} /></div>
  }
  const Icon = CATEGORY_ICONS[story.category] ?? ShieldAlert
  if (variant === 'thumb') {
    return <span className="weekly-thumb story-cover-thumb" aria-hidden="true"><Icon size={22} /></span>
  }
  return <div className={`story-media story-cover story-cover-${variant}`} aria-hidden="true"><Icon size={variant === 'reader' ? 42 : 30} /><span>{titleCase(story.category || 'Cybersecurity')}</span></div>
}

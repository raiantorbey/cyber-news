import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Outbound } from '../ui/Elements'

describe('Publisher destinations', () => {
  it.each(['javascript:alert(1)', 'data:text/html,unsafe', '/relative', 'not a URL'])('does not navigate to malformed or unsafe destinations: %s', (href) => {
    render(<Outbound href={href}>Publisher</Outbound>)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText(/link unavailable/)).toBeInTheDocument()
  })
  it('opens valid destinations with explicit new-tab semantics', () => {
    render(<Outbound href="https://example.com/report">Original report</Outbound>)
    const link = screen.getByRole('link', { name: /Original report.*opens in a new tab/ })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })
})

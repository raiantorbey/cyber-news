# CyberNews publication

A reader-first cybersecurity publication. The interface starts with reporting,
using editorial typography and soft, rounded surfaces to make it easy to browse.

## Visual system

| Role | Light | Dark |
| --- | --- | --- |
| Canvas | Pearl `#f3f7f4` | Ink `#171e1a` |
| Reading surface | White `#ffffff` | Charcoal `#212b25` |
| Text | `#24312a` | `#edf5f0` |
| Secondary text | `#59695f` | `#b0c4b7` |
| Accent | Forest `#326b49` | Sage `#addbbb` |
| Opening story | `#e0ece3` | `#2c4234` |

`frontend/src/theme.css` is the token source; `publication.css` contains the new
layout and component styles. There are no decorative grid lines or ambient effects.
Translucency belongs to the floating masthead. News surfaces are solid.

- **Wordmark:** a typographic lockup set in the editorial serif, with the "News" half set in italic accent green. It is rendered as live text rather than an image, so it inherits the current theme colors and stays crisp at any resolution.
- **Reading/navigation:** self-hosted DM Sans, weights 400–700.
- **Editorial headlines:** self-hosted Lora, weights 400–600, used on page titles,
  the newest story, and the reading room.
- **Geometry:** 24–28px article radii, pill-shaped navigation and controls.
- **Layout:** 1184px maximum, 32px desktop gutters, 20px mobile gutters.
- **Color:** green marks actions and selected topics; labeled warm tones express risk.

## Information architecture

Stories are chronological. The opening composition gives the newest report more
space, followed by the next two reports and a compact gallery. Topic browsing is
immediately accessible. Publisher/date refinements are a native disclosure.

Vulnerabilities use contextual previews: identifier, description, severity, CVSS,
and known-exploitation status. Tools have language, description, community activity,
and a direct repository link. Sources show original destinations and real update status.

The centered reading room is a native `dialog`: it preserves context, traps focus,
supports Escape, and restores focus on close. Every excerpt is attributed and plain
text. Outbound links accept only absolute HTTP(S) URLs and announce the new tab.

## Implementation

- `src/pages/`: news, vulnerabilities, tools.
- `src/ui/`: masthead, story previews, shared controls, reading room.
- `src/lib/`: API contracts, URL navigation, formatting, short-lived resource cache.
- Filters, sections, pagination, and open records are represented in the URL.
- Search is debounced by 220ms; superseded requests are aborted.
- Collection/detail responses are cached for 45 seconds, bounded to 80 entries.
- Fonts are local, licensed under OFL; production text assets use gzip.

## Motion and accessibility

State feedback takes 160ms; collection/reader entrance 220ms; reader exit 150ms.
Only small translation and opacity are used for entrances. There is no looping
decoration or entrance gate. Reduced motion disables animation, transitions, and
smooth scrolling. Navigation remains visible on mobile, with 44px touch targets.
Native controls, explicit labels, contrast-checked tokens, focus outlines, and
forced-color fallbacks are part of the component system.

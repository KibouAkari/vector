# Vector Design System

**Personality:** precise, premium, technical, quiet and fast.

| Token | Color | Usage |
| :-- | :-- | :-- |
| Canvas | `#0A0D11` | Main dark background |
| Surface | `#131A1B` | Secondary surfaces |
| Text | `#F0F7F3` | Primary text |
| Muted | `#9EB5AD` | Descriptions |
| Mint | `#8DE0B7` | Important active states |

These are documentation design tokens, not a claim
that every existing CSS declaration already uses them.

## UI principles

Use clear information hierarchy, restrained corners,
meaningful whitespace and accessible controls.

Use motion for navigation and state transitions, generally
150–250 ms. Respect `prefers-reduced-motion`.

## Avoid

- Generic SaaS gradients.
- Giant empty cards and decorative metrics.
- Excessive glowing borders.
- Filler marketing language.
- Fabricated product screenshots.

## Engineering

A future `vector-design-system` skill should enforce this
identity when Vector modifies its own frontend.

External UI libraries are inspiration,
not the final authority on Vector's visual design.

## Implemented control views

`app/vector-control.css` is a scoped layer for the authenticated shell. Direct
navigation, compact forms and tables replace the source-inventory card grid.
Use an 8px spacing rhythm, 1px borders, shared 8/12px radii, restrained mint
selection and no heavy shadows. Numeric cost, token, latency and port columns
use tabular figures. Every control needs a programmatic label and visible focus.
Mobile navigation supports Escape, focus return and background inertness.
Loading uses bounded skeletons; errors remain actionable. Do not alter login or
intro through this stylesheet or replace existing dashboard charts.

The [Web Interface Guidelines](https://vercel.com/design/guidelines) informed
keyboard, responsive, focus and reduced-motion behavior. Local synthetic
component rendering is not a screenshot of a live deployment.

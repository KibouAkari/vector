# Vector Design System

**Personality:** precise, premium, technical, quiet and fast.

| Token | Color | Usage |
| :-- | :-- | :-- |
| Canvas | `#000000` | Main dark background |
| Surface | `#060708` | Secondary surfaces |
| Text | `#EDF0F2` | Primary text |
| Muted | `#969DA5` | Descriptions |
| Glacier | `#D5E1EA` | Important active states |

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

## Operations interface

`app/operations.css` scopes the new authenticated theme. Use the components in
`components/operations` for headings, panels, empty states, metrics and statuses.
The topbar is 64px, grouped rail 220px and content gap 24px. Mobile navigation is
a drawer; numeric tables scroll within their own surface rather than widening
the page. Avoid nesting a full generic card grid inside another card.

Tailwind theme/utilities use the `vx:` prefix and omit preflight. Do not reset
login/intro styles. Motion must respect both device reduced motion and interface
preferences. Three.js loads only on the Traffic route and plots observed data;
keep a readable non-WebGL alternative. Never fabricate service status, confidence
scores, geographic events or percentage improvements for visual density.

## Observatory surfaces

Authenticated routes use `app/observatory.css` after the existing component
styles. Flat hairline sections, restrained controls and tabular operational
figures keep the content hierarchy clear. Decorative planets sit behind content
and never encode telemetry. The account ambient/motion preferences and system
reduced-motion setting control them. Login/intro source stays separate.

Overview gives tasks, cost and model/token figures the main column. Host health
is compact. Traffic uses actual country polygons with explicit unknown location,
stale sample and partial-coverage states. Do not add fake maps, fictional activity
or fabricated CPU percentages to make empty installations appear busy.

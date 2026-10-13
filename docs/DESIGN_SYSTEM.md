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

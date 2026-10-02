# Iconography Foundation

## 1. Two icon classes

Kingfisher distinguishes between **system icons** and **Kingfisher semantic icons**.

### System icons

Use **Lucide** as the default system icon family for ordinary interface actions and navigation.

Examples:
- search
- calendar
- settings
- mail
- message
- chevron
- close
- plus/minus
- attachment
- download
- filter
- play/pause
- microphone
- clock
- external link
- check
- archive

Why: Lucide provides a consistent, high-quality SVG set with a restrained rounded-line character that fits the current Kingfisher visual language and can be implemented reliably across web surfaces.

### Kingfisher semantic icons

Concepts that are part of Kingfisher's identity receive custom assets, not Lucide approximations.

Examples:
- Kingfisher / system presence
- observing
- orchestration / active work
- deep research / diving
- surfacing insight
- clarity / synthesis
- memory relationship
- contextual relevance
- agent activity when a generic system icon is insufficient

## 2. Binding implementation rule

**Never ask an image model or coding agent to generate a substitute system icon.**

If a Lucide icon exists for an ordinary system action, use the approved Lucide SVG/component. If a custom Kingfisher icon exists, use the repository asset.

Do not mix icon libraries within the same product surface without a documented exception.

## 3. Visual treatment

Default system icon character:
- outline, not filled
- rounded caps and joins
- consistent optical size
- restrained line weight
- no glossy 3D treatment
- no coloured icon tiles unless the component specification explicitly calls for one

Suggested production defaults:
- 16 px compact controls
- 18 px standard navigation/list actions
- 20–24 px primary controls
- 1.75–2 px apparent stroke depending on rendered size

## 4. States

Icons inherit semantic foreground color from the component.

- default: muted foreground
- hover: stronger foreground
- selected: Kingfisher Blue or approved selected-state foreground
- disabled: reduced contrast
- warning/attention: copper only when semantically correct
- destructive: dedicated destructive red, never copper

## 5. Prohibited patterns

- AI-generated replacement icons
- emoji used as production icons
- mixing outline and filled icon families arbitrarily
- neon gradient icons
- random coloured circles behind every icon
- inconsistent line weights
- raster screenshots of standard system icons

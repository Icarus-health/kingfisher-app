# Avatar & Contact Image Foundation

People are first-class visual entities in Kingfisher. Their images support recognition across conversations, memory, tasks, calendar, projects, briefings, and search.

## Canonical image precedence

For each person entity, use the first available source in this order:

1. Authorised contact image from a connected source, where technically and legally permitted
2. Existing canonical Kingfisher person image
3. User-uploaded image
4. Initials fallback

## Critical rule

**Never generate a synthetic replacement face for a real contact.**

If no real image is available, use initials. Do not invent a face that could be mistaken for the person.

## Entity ownership

A person entity owns one canonical image reference. UI surfaces must reference that same image rather than copying independent image files into each feature.

This means the same person should look identical in:
- conversation list
- active conversation
- Morning Briefing
- calendar/meeting preparation
- tasks
- project context
- memory graph/profile
- search/command results

## Crop and framing

- default crop: face-centred square crop
- display shape: circle for people in standard UI
- preserve natural skin tones; no brand-colour filters over faces
- avoid heavy vignette or stylised AI portrait effects
- do not replace background unless needed for accessibility or privacy

## Standard sizes

- 24 px — compact metadata / inline reference
- 32 px — dense lists and conversation rows
- 40 px — standard contact rows
- 48 px — priority cards / meeting context
- 64 px — profile summary
- 96+ px — dedicated person profile hero where appropriate

## Initials fallback

Fallback avatars should be calm and systematic.

- 1–2 initials
- stable background derived deterministically from person ID, not randomly per render
- colours restricted to approved muted palette
- no gradients by default
- foreground must meet contrast requirements
- never use bright multi-colour generated avatar patterns

## Presence and status

Presence/state is a separate indicator layered around or adjacent to the avatar. Do not recolour the person's image to communicate status.

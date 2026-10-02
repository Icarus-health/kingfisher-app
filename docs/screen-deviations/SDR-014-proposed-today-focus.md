# SDR-014 — Approved Today focus and calm visual direction

Status: approved for implementation by product owner on 2026-09-27.

## Approval and intent

The owner approved the generous Today layout, then the revised line pictograms.
After several visual refinements, they selected the second final proposal and
asked to implement it (2026-09-27, 13:48 Europe/Berlin). The canonical selected
image is `design-source/06_Screens/Approved/today-calm-canonical-source-v1.png` (vor der Veröffentlichung entfernt).

The durable brief is a refined, calm personal tool with high usability: generous
surfaces, clear hierarchy, readable content, few deliberate controls. Memory
accuracy remains central. The owner may later open the project to other users
and contributors; this is not authorization to change repository visibility.

## Approved changes

- Compact 300px hero, conversation input in the first viewport.
- Continuous calm lake landscape behind opaque content surfaces, including when
  scrolling; no flat band between the hero and content.
- Existing logo/perched kingfisher and revised thin navigation pictograms remain.
- A photographic flying kingfisher accents attention; a small scenic fragment
  accents calendar. No decorative bird/logo in “Neu im Blick”.
- Inter section headings, no repeated uppercase section labels, fewer divider
  lines, rounded controls and subtle panel elevation. Cormorant remains in the
  greeting and clock. Text labels continue to identify actions independently of
  imagery or color. New assets and provenance: `docs/release/ASSET-RELEASE-2026-09-27.md`.
- Wider attention panel with complete titles, context and direct existing actions;
  calendar preparation alongside it; recent sources below. Source details expand
  to full panel width. The explicit Briefing button opens the existing drawer.
- Unique matching calendar reminders move to calendar; ambiguous/unmatched
  reminders remain visible. Availability warnings, source caveats and empty states
  retain their actual meaning. No invented information or backend changes.

## Deliberate runtime details

- The generated reference omits “Kalender öffnen”; the working UI preserves it at
  the bottom of the calendar panel so navigation remains available.
- The orange count uses dark text for contrast. The send button reflects actual
  disabled state. Time/source ordering come from real data, not the image.
- Existing fonts and logo are retained rather than rasterizing generated text.
- Dark mode uses fully opaque blue/navy surfaces and a subdued landscape. No
  transparency through reading surfaces. Minimum desktop width remains 1280px.
- Shared navigation uses the approved original SVG marks in `InterfaceIcon.tsx`;
  detailed routes retain their legacy icons. This is an explicit scoped exception
  to the earlier frozen icon policy, not permission for arbitrary new assets.

## Validation boundary

Build, asset manifest and rendered Chromium checks cover 1521×1034 light/dark,
1280×900, briefing drawer, keyboard entry, follow-up/preparation links, source
expansion/correction affordance, model-free project questions, incomplete-source
empty state, duplicate calendar identifiers and long content while scrolling.
Browser workflow uses the existing local Playwright setup; this is a production
repository change, not a hosted prototype. No live cloud preview is claimed.
Native Tauri/Safari and real Mac integrations remain for tomorrow's device test.

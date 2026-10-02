# Approved screen deviations — local inbox slice

Approved by the product owner in the implementation conversation on 2026-09-04.

## Nachrichten im Kontext

- The local inbox initially exposes only the real `Alle` view. The reference
  tabs `Personen`, `Projekte`, and `Kanäle` remain absent until the local
  memory model persists an explicit, reviewable categorization for messages.
- Message rows do not open a detail view and do not mark mail as read. Reading
  a complete message or changing mail state requires a separate consent and
  interaction decision.
- Person avatars, avatar circles, provider logos, and replacement art remain
  absent. Rows start at the regular list edge, as approved in SDR-001.
- Only local preview fields are rendered: sender, subject, short preview,
  timestamp, and configured source label. Mail bodies and recipient addresses
  are deliberately not sent to the browser list endpoint.

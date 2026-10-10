# Gesundheitsangaben: Umsetzung und Nachweis

Basis: `3667e4e18b9e255780c755889370b46368cf0a6d`. Spezifikation: `../specs/2026-10-09-health-observations-design.md`. Bestehendes Produkt erweitern, Originale/Quellenrechte/Pause erhalten.

1. `sidecar/tests/test_health_observations.py`: isolierte reale EpisodeStore-/ClaimStore-/HTTP-Fixture ohne App-Lifespan/Provider. Eingabe, Wiederholung, Zeit, Einheit, Korrektur, Historie, Stale/Entzug und begrenzte Seiten rot belegen.
2. `sidecar/icarus_memory/health_observations.py`: validierte Eingaben, kanonische Originale, source_heads, Claim-Invalidierung, bounded page/history; register(app,guard). `server.py` registriert das Modul und den Produktpfad `/wellbeing`; der bestehende technische `/health`-Endpunkt bleibt unverändert.
3. `app/kingfisher/src/HealthPage.tsx`, `healthObservationForm.ts`, `api.ts`, `App.tsx`: `/wellbeing`, ausdrückliche Selbstaussage, Zeitzonenanzeige, Preview, replaysichere Einmalkennung, Quellen/Verlauf/Korrektur. Heute/Entwicklung verweisen auf den Gesundheitsarbeitsbereich, weiter auf Originalquellen.
4. Gezielte Backend-/Frontendregressionen, Build, unabhängiger Review; echte Render-/Mac-Abnahme ausdrücklich offen. Kein produktiver Import, Modell- oder Cloudlauf. Sicherer nachprüfbarer GitHub-Draft; keine Installation vor den offenen Bedien-/Liefergates.

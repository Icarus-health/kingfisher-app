# Gespräch: Quelle und Widerruf

Status: Desktop-Interaktionsablauf bestanden; Screenshotprüfung erfolgt;
vollständige Mac-Designabnahme offen. Mobile ist vom aktuellen Umfang ausgenommen.

Referenz: `system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt), Abschnitt 04;
freigegebene Interaktionsgrundlage: SDR-005. Die bestehende Gesprächskarte,
Schriften, Farben und Schaltflächen werden wiederverwendet.

| Prüfpunkt | Soll / verbleibender Nachweis |
| --- | --- |
| Quelle | Originale Nutzerzeile wird fokussiert, Zitat bleibt sichtbar |
| Aktive Aussage | Bestätigungsstatus und zustandsabhängiger Widerruf |
| Widerruf | Kein aktueller Bestätigungsstatus, keine erneute Widerrufsschaltfläche |
| Kontext | Widerrufene Aussage verschwindet auch links und aus weiteren Antworten |
| Plattformumfang | Mac zuerst; mobile Bedienung ist zurückgestellt und kein aktueller Freigabepunkt |
| Screenshotvergleich | Desktop 1440×1000; Referenz im CI-Artefakt |

Der integrierte Browser konnte die lokale Testadresse nicht öffnen:
`net::ERR_BLOCKED_BY_CLIENT`. Die CI verwendet den bereits vorhandenen
Playwright-Prüfer am tatsächlich gebauten Container. Ein grüner Lauf belegt
die Interaktion, nicht automatisch die exakte Übereinstimmung mit dem Original.

Nachweise und verbleibender Umfang: [K2a](../release/K2-CONVERSATION-MEMORY.md).

## Sichtprüfung des ersten Containerlaufs

Desktop 1440×1000: Bestätigungs- und Widerrufskarte vollständig lesbar, Buttons
innerhalb der Karte. Nach Widerruf fehlt die Aussage im Kontextbereich;
Quellenzitat und Quellenschaltfläche bleiben sichtbar. Kein beobachteter neuer
Überlappungsfehler. Keine App-/Asset-/Schriftfehler im Browserprotokoll.

Die erste Aufzeichnung enthielt noch einen mobilen Fehlernachweis (390×844).
Nach der ausdrücklichen Mac-Priorisierung ist dieser aus der laufenden
Abnahme herausgenommen. Es wurde keine mobile Gestaltung umgesetzt.

[Geprüfte Screenshots und Originalreferenz](https://github.com/Icarus-health/Kingfisher/actions/runs/34030400391/artifacts/9988427267).

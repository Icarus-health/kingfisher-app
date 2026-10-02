# Empfängergrenze bei Mailantworten

Stand: 27. September 2026. Begrenzter erster Umsetzungsschritt zur gezielten
Nutzung privater und beruflicher Informationen.

## Geschlossene Lücken

Frühere Quellen waren an Absender und Konto gebunden, der tatsächliche Empfänger
konnte über Reply-To jedoch abweichen. Jetzt wird diese Grenze vor Quellensuche
und Modellaufruf geprüft. Bei Abweichung oder Mehrdeutigkeit entsteht nur ein
Entwurf aus aktueller Mail und Nutzerhinweis. Die Oberfläche erklärt das.

Die unabhängige Prüfung fand zusätzlich einen Wechsel zwischen zwei Abrufen:
Der erste konnte ein fremdes Reply-To liefern, der zweite wieder den alten Stand.
Der vorbereitete Versand benutzte bisher den ersten Stand. Jetzt muss auch genau
dieser Stand zur Quellenbindung passen. Direkt am Versand prüft der Kern Konto
und tatsächliche Empfängeradresse erneut gegen den gebundenen Quellenbereich.

Ein Quellenentwurf ohne den neuen Empfängernachweis wird nicht durch Wiederöffnen
als gültig behandelt. Normale manuelle Reply-To-Antworten bleiben mit ausdrücklicher
Versandfreigabe möglich. Es gibt keine neue automatische Versandberechtigung.

## Gegenproben und Überprüfung

15 neue Regressionstests decken abweichendes, mehrdeutiges und ungültiges Reply-To,
Header-Zeilenumbrüche, mehrdeutige Absender, legitime Adressvarianten, alte Kontexte,
Änderungen vor Freigabe, wechselnde Abrufstände und manipulierte Versandparameter ab.

Vor der ersten Korrektur schlugen sieben Fälle erwartungsgemäß fehl. Die drei
zusätzlichen Abruf-/Versandproben schlugen ebenfalls vor ihrem Fix fehl. Danach
bestanden alle **65 gezielten Mailtests**. Die unabhängige Nachprüfung bestätigte
den Fix; keine verbleibenden Codeblocker.

Browserprüfung mit Playwright/Chromium und synthetischem Postfach/Modell:
`/nachrichten` → Mail öffnen → Antwort vorschlagen → Empfängerhinweis sehen →
Entwurf übernehmen. Ergebnis: bestanden bei 1440 × 1000 und 1280 × 1000 Pixeln,
Hell/Dunkel; korrekter Seitentitel, sichtbarer Inhalt, kein Framework-Overlay,
keine Konsolenfehler. Kein Versand angefordert. Der synthetische Modelladapter
weist jeden Aufruf mit der ausgeschlossenen alten Quelle zusätzlich zurück.

Browser-Plugin nicht verfügbar; vorhandenes Playwright verwendet. Die 900-Pixel-
Gegenprobe zeigt die bestehende globale Mindestbreite von 1280 Pixeln; sie ist
keine bestätigte Mobilansicht. Ein früher Browserlauf nutzte einen veralteten
Build; nach erneutem Build wurde derselbe Ablauf gegen das aktuelle Bundle geprüft.
TypeScript/Vite-Build und Diff-Prüfung bestanden.

Frischer vollständiger Sidecar-Lauf nach beiden Korrekturen: **2427 bestanden**,
eine bestehende TestClient-Abkündigungswarnung, 367,75 Sekunden. Der ältere
Zwischenlauf vor der Abrufkorrektur wird nicht als Nachweis des finalen Codes verwendet.

## Grenzen und weiterer Entwurf

Dies beweist keine vollständige Privat-/Arbeitstrennung. Gleiche Adresse im
selben Konto kann private und berufliche Inhalte mischen; Absenderauthentizität,
Aliase, andere Chat-/Werkzeugpfade und Cloudfreigaben brauchen weitere Regeln.
Kein reales Postfach, natives macOS oder echtes Sprachmodell wurde damit getestet.
GitHub Actions bleibt wegen ausgeschöpfter Minuten getrennt vom lokalen Nachweis.

Der [Architekturentwurf](../../superpowers/specs/2026-09-27-private-work-boundaries-design.md)
legt Herkunft, Zusammenhang und erlaubte Nutzung getrennt fest. Er beschreibt
Grants, Zweckkontext, Vererbung von Beschränkungen, Freigabe-/Widerrufsrevisionen,
die lokale Gesamtübersicht und eine begrenzte Belegungsprojektion. Dieser größere
Ausbau ist ausdrücklich noch nicht als implementiert ausgewiesen.

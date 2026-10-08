# ChatGPT-Anmeldung und begrenzte Gedächtnisprüfung

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement and verify each task.

**Goal:** Den freigegebenen Weg „ChatGPT anmelden → Datenfreigabe → 100 Mails prüfen → separat fortsetzen“ nutzbar machen; Personenqualität und bestehende Ableitungen verbessern.

**Architecture:** Eine geschützte lokale OAuth-Verbindung nutzt ausschließlich die öffentlich dokumentierte Responses API. Ein eigener, ausdrücklich freigegebener Arbeitsgang verarbeitet ausgewählte Quellen; die bestehende lokale Hintergrundautomatik und ihre Pause bleiben unabhängig. Quellenbelege, Fingerprints und bestätigte Korrekturen bleiben maßgeblich.

**Tech Stack:** FastAPI, httpx, PyJWT mit kryptografischer Signaturprüfung, vorhandener verschlüsselter Keychain, React/TypeScript, SQLite.

**Spec:** Nutzerfreigabe vom 08.10.2026 in diesem Gespräch: ChatGPT-Abo optional, ausdrücklicher Hinweis auf OpenAI und mögliche Verarbeitung außerhalb der EU; Personen vereinheitlichen, vorhandene Einordnung nachprüfen, zuerst 100 verschiedene Mails. Keine Originale löschen oder still verändern; keine unbegrenzte Verarbeitung oder kostenpflichtige Ausweich-API.

## Global Constraints

- Nur `https://auth.openai.com` für OAuth und `https://api.openai.com/v1` für Modelle/Responses; keine privaten ChatGPT-Endpunkte.
- PKCE, Nonce, einmaliger State, exakte Loopback-Rückleitung, Signatur/Issuer/Audience/Expiry prüfen. Registrierung mit ausgegebener Client-ID speichern.
- Tokens ausschließlich im geschützten Speicher. Keine Tokens in UI, Logs, URL-Diagnosen, Repository oder Klartext-Konfiguration.
- Anmeldung allein startet keine Mailverarbeitung. Separate, widerrufbare Quelleneinwilligung, Modellwahl und Paketgrenze.
- `store:false`, `stream:true`; vollständiges `response.completed` nötig. Abbruch, Limits und unvollständige Antwort gelten nicht als Erfolg.
- Keine automatische Umschaltung auf bezahlte API oder anderen Anbieter. Modellkatalog stammt vom angemeldeten Konto.
- Bestehende Importpause, Originalquellen, Zeitangaben, Aufgaben und bestätigte Korrekturen bleiben erhalten.
- Reale Anmeldung erfolgt durch den Nutzer; reale Mailprobe erst über den geprüften Freigabefluss.

## Review Focus

- Fremder/abgelaufener/wiederverwendeter OAuth-State und manipulierte ID-Tokens: kein gespeicherter Zugang.
- Anmeldung eines anderen Kontos, Tokenrotation und Widerruf während eines Aufrufs: kein nächster Aufruf/Schreibvorgang unter alter Freigabe.
- Unterbrochener Stream, HTTP 401/403/429 und Kontingentende: Paket pausiert mit verständlichem Grund.
- Änderungen/Entzug von Quellen und bestätigte Kategorien: keine veralteten oder überschriebenen Ableitungen.
- Servicepostfach und echter Mensch im selben Material: keine falsche Identitätsverschmelzung, Belege bleiben auffindbar.

## Task 1 — Geschützte Anmeldung und Responses-Anbieter

- [x] Failing tests in `sidecar/tests/test_chatgpt_oauth.py` und `test_chatgpt_provider.py`: State/PKCE, signierte Tokens, Scope, Rotation, Widerruf, vollständige Streams.
- [x] `chatgpt_oauth.py`: `ChatGPTOAuth.begin(origin)`, `callback(...)`, `status()`, `models()`, `provider(model)`, `disconnect()`; geschützte Registrierungen, stabiler Host, generationengebundene Anbieter.
- [x] `chatgpt_provider.py`: `complete_json(...)` ohne Werkzeuge und ohne verbotene Parameter; begrenzte lokale Antwortgröße, Streams vollständig prüfen.
- [x] `chatgpt_routes.py`: geschützte Setup-Routen, Code aus Callback-Logs entfernen, sichere Fehlertexte.
- [x] Fokusprüfungen einschließlich negativer Token-/Streamfälle.

## Task 2 — Personenqualität

- [x] Synthetische Regression für Service/Abrechnung/Plattformen und gleichnamige Menschen.
- [x] Gemeinsame Qualitätsregeln in `people_quality.py`, konservative Projektion in `personen.py`; explizite Zuordnungen und Originale schützen.
- [x] Personen-, Identitäts- und Kategorienprüfungen ausführen und Änderungen unabhängig lesen.

## Task 3 — Freigegebene Mailpakete und Nachprüfung

- [x] Synthetische Tests für Freigabe, 100-Quellen-Paket, Zähler, Pause/Neustart/Widerruf, Quellenänderung und manuelle Korrektur.
- [x] `cloud_memory.py`/`cloud_memory_routes.py`: Vorschau, Start, Fortschritt, Pause/Fortsetzen/Widerruf und explizite Nachprüfung.
- [x] Quellenspezifische Verarbeitungsfreigabe ergänzt die lokalen Gates; entfernte Anbieter werden niemals als lokal bezeichnet.
- [x] Vor jedem Aufruf und Schreiben Quelle, Kontozugang und Freigabe prüfen.

## Task 4 — Einfacher Ablauf und Gesamtprüfung

- [x] `ChatGPTAccess.tsx`, `api.ts`, Einstellungen: Anmeldung, Kontostatus, Modellkatalog, sichtbare Datenfreigabe und Kontingenthinweis.
- [x] `CloudMemory.tsx`: 100-Mail-Probe mit Vorschau/Arbeitsstand, Ergebnisgrenzen, getrennte Fortsetzung und Nachprüfung.
- [x] Backend/Frontend verbinden, TypeScript/Build, betroffene Tests, unabhängiges Review.
- [x] Bediencheck des installierten App-Fensters: Anmeldung, Modellwahl, getrennte Vorschau/Freigabe, Fortschritt und Personenprüfung. Die reale Anmeldung ist verbunden; der begrenzte 100-Mail-Lauf und die inhaltliche Qualitätsabnahme werden separat dokumentiert.

## Offizielle Referenzen

- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
- https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations

Ein erfolgreicher technischer Probelauf beweist noch keine fehlerfreie Einordnung des echten Mailbestands. Die 100-Mail-Probe ist eine getrennte Qualitätsprüfung vor dem großen Lauf.

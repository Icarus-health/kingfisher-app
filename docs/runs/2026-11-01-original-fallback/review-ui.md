# Unabhängiger enger UI-/Projektionsreview – Originalberichte

**Ergebnis: kein Blocker im geprüften UI-/Projektionsdelta.** Der vollständige unbestätigte Originalbericht bleibt im Antworttext erhalten und ist im React-Markup hinter einem zunächst geschlossenen, beschrifteten nativen Aufklapper vorhanden. Satzantworten behalten Vorrang; Quellenaktionen bleiben außerhalb des Aufklappers erreichbar. Das ist keine Abnahme im echten Mac-Fenster und keine semantische Freigabe der zugrunde liegenden Modellantworten.

Geprüft: **3d8c4ad3f803c6f34ef94dbff3e37a0e42688f4b** gegen `c0e6265`, Arbeitsbaum `/private/tmp/kf-skill-categories-20261031`. Schwerpunkte: `App.tsx`, `api.ts`, tatsächliches React-SSR-Markup und Nicht-Verbergen von Originalen/Quellen/Bestätigtem. Die vertiefte Backendprüfung ist separat beauftragt. Keine Produktänderungen durch diesen Reviewer, kein echtes Modell, Netzwerk oder private Dateien. Root-Arbeitsbaum vor/nach Prüfung sauber; Diffprüfung ohne Fehler.

## Codebefund

- `app/kingfisher/src/App.tsx:484–488`: `satzantwort` wird zuerst geprüft. Nur für `role=assistant` und exakt boolesches `original_fallback===true` erscheinen kurze Ansage und `<details><summary>Originalangaben lesen</summary><MessageText … /></details>`. Es fehlt absichtlich ein `open`-Attribut. Der vollständige unveränderte `message.content` wird an MessageText übergeben; kein Frontend-Substring, Header-Ersatz oder Textverlust.
- `App.tsx:495–497`: die bisherige quellenbelegte Aktionsgruppe mit ProfileSource liegt außerhalb dieses Aufklappers. Der Nutzer muss den Text nicht öffnen, um die Originalquelle zu öffnen. Vorhandene Klarstellungen/Datumsauswahl bleiben im nachfolgenden Bereich.
- `app/kingfisher/src/api.ts:110`: `original_fallback?: boolean` ist optional typisiert. Fehlender/false Marker lässt die bisherige Darstellung unverändert. Ein String `"true"` aktiviert den Aufklapper nicht.
- `MessageText.tsx`: React rendert Textfragmente; kein HTML-Einfügen/URL-Auswerten. Die bestehende kleine Markdowndarstellung bleibt erhalten.
- `Workspace.css:127–129` verwendet die bestehende gestalterische Aufklapperrolle; Summary hat min-height 44px. `Grundlage.css:453–460` liefert sichtbaren Zeiger/aufklappbaren Pfeil; `:476` gilt auch für Summary-Fokus. Native Details-/Summary-Struktur und zugängliche sichtbare Beschriftung sind vorhanden. Tatsächliche Tastatur-/VoiceOver-Bedienung, Kontrastmessung und Fensterlayout wurden nicht praktisch geprüft.

## UI/UX Pro Max

Skill gelesen und angewendet, ohne neue Designrunde. Die fokussierte Suche lieferte einen passenden Web-Treffer für vollständige Tastaturnavigation. Zwei Versuche zum Thema progressive disclosure lieferten dagegen nur einen sachfremden Überschriften-Treffer; dieser wurde **nicht** als bestätigte Empfehlung verwendet. Für native Steuerelemente, Fokus/Bedienbarkeit und vollständige Inhaltsverfügbarkeit wurden die allgemeinen Regeln der gelesenen `quick-reference.md` verwendet. Keine neue Palette, Schrift, Animation oder Navigation vorgeschlagen.

## Isolation und Prüfungen

Frontend unverändert nach `/private/tmp/kf-progressive-ui-review-20261101` kopiert (src/tests/Projektkonfiguration). Nur dort ein Symlink auf die bereits vorhandenen lokalen node_modules und ein zusätzlicher unabhängiger Test. Kein Symlink oder Cache im Root-Arbeitsbaum. Hashgleichheit von App.tsx, api.ts und MessageText.tsx zwischen geprüftem Root und dieser Kopie separat bestätigt.

1. Bestehende gezielte Tests in der Kopie:

```
node --experimental-strip-types --test tests/conversation-workspace.test.mjs tests/beleg.test.mjs tests/quellen-weg.test.mjs
20 bestanden, 0 Fehler, etwa 1,69 s
```

Enthalten: neuer Root-Aufklappertest, sichere MessageText-Formatierung, vorhandene Quellaktionen und Gesprächsnavigation.

2. **Zusätzliche echte SSR-Kontrolle** im kopierten Test `tests/conversation-workspace.test.mjs`, Testname `independent SSR: original disclosure preserves complete escaped content and external source actions`:

```
node --experimental-strip-types --test --test-name-pattern='independent SSR' tests/conversation-workspace.test.mjs
1 Test mit 6 Szenarien bestanden, 0 Fehler, etwa 2,20 s
```

Der Test ruft wirklich `renderToStaticMarkup` auf dem durch die echten Conversation-/Child-Komponenten erzeugten React-Baum auf; nicht lediglich eine Quelltextsuche. Gescriptet sind nur API-Daten und äußere Conversation-Hookzustände, entsprechend dem bestehenden UI-Testtreiber. Prüfung des tatsächlich erzeugten HTML:

- assistant/true: genau der Original-Aufklapper, ohne `open`; Anfang, Einschränkung/Negation und eindeutiges Textende vollständig innerhalb der Details vorhanden.
- Synthetisches `<script>` bleibt HTML-escaped; kein ausführbarer Script-Tag.
- Die Original-Quellenaktion ist im HTML **nach** dem geschlossenen Detailsbereich enthalten, nicht darin versteckt.
- assistant/false, Marker fehlt, user/true und Stringmarker `"true"`: kein neuer Original-Aufklapper; vollständiger Text weiterhin inline vorhanden.
- true-Marker plus gültige SatzAntwort: geprüfter Satz bleibt sichtbar und priorisiert; kein Original-Aufklapper und kein unstrukturierter Rohtext daneben.

Das ist ein HTML-/Komponentenbeweis. Es ist kein browserseitiger Klick-/Fokus-/Layoutnachweis.

3. TypeScript-Projektprüfung in der Kopie:

```
node node_modules/typescript/bin/tsc -b --pretty false
Exit 0, keine Fehlerausgabe
```

4. Sieben enge Produkt/API-Nicht-Verbergen-Kontrollen aus `test_answer_clarification_projection.py` unabhängig ausgeführt:

- fehlgeschlagene/nichts-Satzformulierung erhält vollständige Originale für die aufklappbare Anzeige (zwei Fälle),
- bestätigter claim_basis bleibt sichtbar und wird nicht als Originalfallback markiert,
- gültige Satzantwort bleibt priorisiert; falscher Altmarker wird beim Wiederöffnen entfernt, Quellenentzug entfernt Marker und Satzdaten,
- Personenunsicherheit ohne Optionen erhält vollständige Originale und Quellenzugang (zwei Fälle),
- durch Originalwächter belegte tatsächliche Personenmehrdeutigkeit bleibt als Rückfrage sichtbar, nicht als optionaler Originalfallback versteckt.

```
7 passed, 1 warning in 4.61s
```

Einzige Warnung: vorhandene Starlette/httpx-TestClient-Deprecation. Keine Testfehler, keine Vollsuite.

## Grenzen

Der Mac ist weiterhin gesperrt (MACLOCKED). Kein tatsächliches Fenster, Auf-/Zuklappen per Tastatur oder Maus, Bildschirmleser, kleines Display oder Hell-/Dunkelkontrast abgenommen. Der statische Review zeigt passende native Semantik und vollständige Inhalte; praktische Mac-Bedienabnahme bleibt separat. Die UI darf eine unbeantwortete Frage nicht zur geprüften Zusammenfassung umdeuten; der neue Hinweis sagt ausdrücklich, dass diese fehlt.

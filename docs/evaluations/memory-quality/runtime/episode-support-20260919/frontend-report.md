# M1d Frontend-Prüfung

Stand: 19. September 2026. Umsetzung in `app/kingfisher`; kein Commit, Push oder Zugriff auf private Daten.

## Umsetzung

- `MemoryGraph.tsx` bietet den eigenständigen Bereich „Aussagen prüfen“. Er öffnet auch bei fehlgeschlagenem Graphabruf. Navigation nach `/memory` oder `/memory?people=review` setzt die passende Hauptansicht wieder ein.
- `SelfModelSupportReview.tsx` listet einzelne SelfModel-Aussagen mit Seitencursor. Die tokengebundene Vorschau ersetzt die älteren Listenangaben zu Aussage, Art, fachlichem Zeitbezug und Aktualität. Alle Originalzitate stehen vor der einzelnen Bestätigung sichtbar im Dokumentfluss. Die Quelle öffnet in `ProfileSource` ausschließlich lesend; sowohl Ausschließen als auch Wiederzulassen sind gesperrt.
- Die Bestätigung nennt den lokalen Geltungsbereich. Sie sendet nur `preview_token` und `confirmed: true`. Ein Fehler, insbesondere HTTP 409, verwirft das Token und verlangt eine neue Vorschau. Nach Erfolg erscheinen Ergebnis und eine mögliche Auditwarnung getrennt von der fachlichen Zeitangabe.
- Während des wirksamen POST sind Aktualisieren, Seitennavigation, Bereichswechsel und Sidebar-Navigation gesperrt. Ein Browser-History-Wechsel zwischen `/memory`-Einträgen hält die Prüfsektion bis zur Antwort offen, damit auch eine Auditwarnung sichtbar bleibt. Veraltete Antworten von Vorschauanfragen und Listenabrufen werden nach Auswahlwechsel oder Unmount ignoriert.
- `api.ts` enthält die Typen und Routen aus dem festen SDD-API-Vertrag. Die vorhandene ungespeicherte `ProfileSource`-Änderung für `readOnly` blieb erhalten.

## Prüfung

| Prüfung | Ergebnis |
| --- | --- |
| `npm run build` in `app/kingfisher` | Bestanden: TypeScript und Vite |
| `git diff --check` für Frontend-Dateien | Bestanden |
| Synthetischer Chromium-Ablauf bei `http://127.0.0.1:5189/memory`, 1280 × 900 | Bestanden: Graph HTTP 503, Prüfbereich erreichbar, frische Vorschauwerte, zwei Zitate, keine Quellenaktionen, HTTP 409 sperrt altes Token, zweite Vorschau und Bestätigung erfolgreich, keine Seitenfehler |
| Verzögerter Bestätigungs-POST mit Auditwarnung | Vor Korrektur fehlgeschlagen: `locked=false`, `warningVisible=false`; danach bestanden: `locked=true`, `warningVisible=true` |
| Sidebar `/memory` und `/memory?people=review` | Vor Korrektur blieb die Prüfsektion stehen; danach öffnen beide Ziele die passende Hauptansicht |
| History-Wechsel innerhalb von `/memory` während verzögertem POST | Bestanden: Prüfsektion bleibt bis zur Antwort offen; Auditwarnung sichtbar; anschließende Navigation setzt die Hauptansicht zurück |
| Mobile Darstellung bei 390 × 844 | Kein horizontaler Seitenüberlauf; Prüfkarte und Navigation sichtbar |

Der Browser-Plugin-Pfad war in dieser Sitzung nicht verfügbar. Der synthetische Ablauf verwendete Playwright aus der gebündelten Node-Laufzeit und einen lokal installierten Chromium-Browser. API-Antworten wurden im Browser abgefangen; dies prüft die sichtbaren Zustände und die gesendete Bestätigungsform, ersetzt aber keinen echten Backend- oder Provider-Test. Der integrierte Lauf mit realem Backend gehört zur abschließenden M1d-Gesamtprüfung.

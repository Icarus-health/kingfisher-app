# K0: Start, Browser und Wiederanlauf nachweisen

Stand: 6. September 2026. Zusätzlicher Änderungssatz auf dem Gedächtniskern aus
[PR #1](https://github.com/Icarus-health/Kingfisher/pull/1). Der vollständige
[Produktplan](PRODUCT-PLAN.md) bleibt die Abnahmeliste.

## Behobene Lücken

- Der Container hört auf Port 8890. Der alte CI-Rauchtest verwendete noch 8765
  und prüfte den alten Icarus-Seitentitel. PR #1 bestand die CI-Funktionsprüfungen,
  scheiterte aber im Container-Workflow.
- Direkte Aufrufe und Reloads von `/memory` liefern jetzt dieselbe Kingfisher-App
  und geschützte Browsersitzung wie die übrigen aktiven Routen.
- `host.docker.internal` wird in Compose auch für Linux explizit auf den
  Host-Gateway aufgelöst. Ein lokales Modell auf dem Host bleibt die bestehende
  Konfigurationsoption; die Datenbank bleibt im Kingfisher-Volume.
- Der Asset-Vertrag prüft jetzt die tatsächliche Existenz und nichtleere Größe
  aller 36 deklarierten Screen-, Brand-, Medien- und Schriftdateien einschließlich
  Stylesheet. Ein erfolgreicher TypeScript-Build allein kann fehlende Originale
  nicht mehr verdecken. Bildinhalt und Layout werden zusätzlich im Browser geprüft.

## Automatischer Ablauf im Container-Workflow

1. Das echte Docker-Image bauen und lokal laden.
2. Eine separate lokale OpenAI-kompatible **Testmodell-Instanz** starten;
   ausschließlich synthetische Gesprächsdaten, keine echten Schlüssel/Quellen.
3. Kingfisher mit einem eigenen Testvolume und geschützter API starten.
4. Health, echte Kingfisher-HTML-Datei, gebaute JS-/CSS-Dateien, aktive Routen und
   Zugriff ohne/mit Berechtigung prüfen.
5. Ein Gespräch führen: explizite Merkbitte → offener Kandidat → sichtbare
   Bestätigung → bestätigtes Wissen im nächsten lokalen Modellkontext.
6. Den echten React-Build im Chromium-Browser öffnen: Today, Gespräch, weitere
   Nachricht, Gedächtnis, direkter Reload und Filterwechsel. Fehlerkonsole,
   lokale Asset-Antworten, sichtbare Bilder und Schriften prüfen. Desktop-
   Screenshots dienen als sichtbare Nachweise; Mobile ist zurückgestellt.
7. Den Container neu starten. Gespräch, Bestätigung und erneuten Wissensabruf
   prüfen. Danach Claim widerrufen und seinen Ausschluss aus dem neuen Kontext
   nachweisen.
8. Ergebnisse/Screenshots als `kingfisher-runtime-verification` am Workflow
   bereitstellen; Testcontainer, Netzwerk und Testvolume auch bei Fehlern entfernen.

Die Browser-Installation folgt dem vorgesehenen
[Playwright-CI-Verfahren](https://playwright.dev/python/docs/ci).
Die Pipeline speichert keine echten Nutzerdaten und keine Modellschlüssel.
Das Testmodell wird nur als separates Prüfwerkzeug verwendet; es wird weder
als Produktprovider angeboten noch als Ersatzantwort in Kingfisher eingebaut.

## Bestätigter CI-Lauf

[PR #2](https://github.com/Icarus-health/Kingfisher/pull/2), geprüfter Code-Commit
`c746f4f3c9077953ea86ced0a4bb6df81fc229da`:

- [Container und Browser erfolgreich](https://github.com/Icarus-health/Kingfisher/actions/runs/34015085334).
  Das gebaute Image bestand den Gesprächs-/Bestätigungsablauf, Chromium meldete
  `ok: true` ohne Fehler und nach `docker restart` bestand der erneute Abruf
  einschließlich Widerruf und Ausschluss aus dem folgenden Kontext.
- [Allgemeine PR-CI erfolgreich](https://github.com/Icarus-health/Kingfisher/actions/runs/34015085336).
- [Laufzeitnachweise mit Screenshots](https://github.com/Icarus-health/Kingfisher/actions/runs/34015085334/artifacts/9983656736)
  sind als Workflow-Artefakt verfügbar (Aufbewahrung: 14 Tage).

Der erste Browserlauf erkannte eine zu strenge, routenabhängige Schriftprüfung:
deklarierte, auf der Gesprächsseite nicht verwendete Schnitte werden vom Browser
noch nicht geladen. Der Prüfer lädt nun alle sechs freigegebenen Schnitte
explizit und verlangt erfolgreich geladene FontFace-Objekte. Fehlende oder
defekte Schriften bleiben Fehler; die Oberfläche wurde dafür nicht verändert.

## Prüfstand

| Nachweis | Ergebnis |
| --- | --- |
| Pflichtregression plus Container-/Asset-Verträge | 114 Tests bestanden |
| Testmodell und Prüferverträge | 2 Tests bestanden |
| Tatsächliche lokale Serverprozesse: seed → Prozessneustart → verify | Bestanden; Gespräch und bestätigter Claim erhalten, Widerruf aus neuem Kontext ausgeschlossen |
| Build der aktuellen React-Arbeitskopie | Kompiliert; lokale Binärassets fehlen, daher kein vollständiger lokaler Auslieferungsnachweis |
| Verstärkter Asset-Check auf der unvollständigen lokalen Textkopie | Erwartungsgemäß fehlgeschlagen; genau fehlende Originale ausgewiesen |
| Abgleich der 36 erforderlichen Pfade mit dem vollständigen GitHub-Tree | Alle vorhanden; keine Ersatzgrafiken hinzugefügt |
| Docker- und Browserlauf gegen den gebauten Container | Bestanden im oben verlinkten CI-Lauf; Gespräch, Browsernachricht, Gedächtnisfilter, Reload und Containerneustart einschließlich Widerruf |
| Visuelle Übereinstimmung mit den freigegebenen Screens | Noch nicht abgenommen; automatischer Browsererfolg ersetzt keinen Referenzvergleich |

## Lokal nachvollziehen

`python scripts/test_contract_model.py` prüft das Testmodell und die
Routen-/Asset-Prüfung ohne Docker. Die produktbezogenen HTTP-Prüfungen laufen
mit `scripts/verify_container.py --phase seed|verify --state <Testdatei>`;
URL und Testtoken werden über `ICARUS_VERIFY_BASE_URL` und
`ICARUS_VERIFY_TOKEN` übergeben. Zwischen den Phasen muss der tatsächliche
Kingfisher-Prozess beziehungsweise Container neu gestartet werden.

`scripts/verify_browser.py --base-url <lokale URL> --state <Testdatei>
--output <Nachweisordner>` verwendet dieselbe synthetisch angelegte Unterhaltung
im echten Browser. `summary.json` kennzeichnet die automatischen Prüfungen und
setzt `visual_comparison` ausdrücklich auf `false`.

## Noch offen bis K0/K2 fertig sind

Modell-Einrichtung und Fehlerfälle mit tatsächlich unterstützten Modellen,
Import/Abgleich des PC-Stands, vollständig bedienbare Registry-/Korrekturabläufe
in der freigegebenen UI und die visuelle Gesamtabnahme. Die hier eingeführten
Gates schaffen einen reproduzierbaren Nachweis für weitere PRs; sie sind kein
Ersatz für diese Produktarbeit.

## Folgepaket: Ersteinrichtung im Docker-Lieferweg

Die aktuelle Lieferung erfolgt in Docker auf dem Mac mit Bedienung im Browser;
kein nativer Build ist dafür erforderlich. Der Containervertrag startet nun
ohne Provider-, Modell- oder Endpunktvorgaben. Derselbe Einrichtungshelfer wie
`make modell-lokal` muss ein nicht erreichbares Modell mit Fehlerstatus melden
und danach das lokale Testmodell wirklich verbinden. Die bestehenden Gesprächs-
und Neustartprüfungen verwenden ausschließlich diese gespeicherte Einrichtung.
Der Test setzt kein Modell per Startvariable voraus und meldet einen
HTTP-200-Fehlertest nicht mehr als erfolgreiche Verbindung.

Der Einrichtungshelfer verarbeitet die lokale Schlüsseldatei und Modellnamen
als Daten. Aktiver Provider, Modell und Endpunkt werden gegen die gewählte
Einrichtung geprüft, damit übersteuernde Startvariablen erkennbar bleiben.
Die punktgenaue, werkzeuglose Bereitschaftsfrage im Testmodell ist getrennt
vom normalen Gesprächsvertrag; fehlende Gedächtniswerkzeuge bleiben dort Fehler.

117 Backendprüfungen einschließlich aller Pflichtsuiten und der neuen
Einrichtungsregression sind lokal bestanden. Dazu bestehen 14 stdlib-Prüfungen
für Einrichtungshelfer, Testmodell und Laufzeitprüfer. Der lokale echte
Prozessablauf besteht von der leeren Einrichtung über einen absichtlich
fehlgeschlagenen Modelltest bis zum Gespräch und Wissensabruf nach Neustart;
auch der anschließende Widerruf bleibt aus dem Kontext ausgeschlossen.
Der Container-/Browsernachweis
für dieses Folgepaket wird mit Commit und Workflow im zugehörigen PR verlinkt.
Die UI-Einrichtung und ein echter Modellanbieter bleiben offene Abnahmepunkte.

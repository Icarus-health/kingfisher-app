# Dauerhafte Ablaufkorrekturen und Wiederverwendung

30.10.2026. Begrenzter Schritt des ausdrücklich freigegebenen
[Abschlussziels](../../68-gedaechtnis-abschluss.md), kein Abschlussnachweis für das
gesamte Gedächtnis. Ausgangsbasis 1.0.32 / `68cbe28`; die geprüfte Diagnose aus
PR #102 ist anschließend als `cf79f29` in main und in diesen Branch übernommen.
Großimport bleibt pausiert. Keine privaten Quellen und keine echten Modellaufrufe.

## Verhalten

- Die bestehenden Formen „Lerne diesen Ablauf: …“ bleiben gültig.
- Eine direkte dauerhafte Ablaufanweisung kann ohne diese feste Befehlsform
  einen inaktiven Lernvorschlag erzeugen, etwa „Bei Zunftmails bitte künftig
  zuerst den Anlass prüfen, dann den Entwurf gegenlesen.“
- Die neue begrenzte Erkennung verlangt geordnete Arbeitsschritte. Beschriebene
  Abläufe, Zitate, biografische Fakten, Fragen, reine Stilwünsche und einmalige
  Aufgaben bleiben im normalen Gesprächs-/Quellenpfad.
- Beim Lernen werden auch passende offene Vorschläge angeboten: pro Name die
  jüngste gültige Fassung. Zurückgewiesene, entzogene, überholte oder durch
  Quellenänderung ungültige Grundlagen bleiben ausgeschlossen. Maximal acht
  Metadaten und 2.400 UTF-8-Bytes; keine Ablaufkörper im Auswahlkatalog.
- Normale Ausführung lädt weiterhin ausschließlich bestätigte aktive Fassungen.
  Bestehende Quellen-, Bestätigungs-, Versions- und Berechtigungsprüfungen bleiben.

## Nachweise

Vor Änderung: **38 Verfahrenstests bestanden**. Die neuen natürlichen Lernbitten
scheiterten zunächst in drei tatsächlichen Gesprächs-HTTP-Fällen; die vier neuen
Katalogtests ebenfalls vor ihrer Umsetzung. Danach bestanden 57 Verfahrenstests
und 191 Pflicht-/Verfahrenstests.

Das unabhängige Schlussreview fand eine wichtige Fehlleitung: Beschreibender
Text wie „Bei Zunftmails steht künftig zuerst …“ und erzählte Kursinhalte konnten
ebenfalls Lernen auslösen. Das hätte diese Inhalte von der normalen Fakten- und
Aufgabenerkennung ausgeschlossen. Drei neue Erkennungsfälle und eine echte
HTTP-Regressionsprüfung wurden rot beobachtet. Die korrigierte Prüfung zeigt:
normaler Gesprächsprompt statt Lernprompt, kein Verfahrensvorschlag und keine
Markierung als reiner Lernunterricht. Alle **61 Verfahrenstests bestanden**.

Der erste vollständige Backendlauf wurde nach Sandboxfehlern unterbrochen:
künstliche lokale DNS-/IMAP-/HTTP-Testserver durften keine Sockets öffnen und
die Mac-Speichermessung war gesperrt. 1.834 bestanden, drei Fehler und neun
Einrichtungsfehler; ausdrücklich kein grüner Vollnachweis. Keine Codeänderung
für diese Umgebung vorgenommen. Die Wiederholung nutzt die nötige lokale
Testfreigabe, zwei Worker und niedrige Priorität.

Die vollständige Wiederholung auf dem zusammengeführten Code-Stand `3758b06`
bestand: **8.347 Tests, 26 Untertests, ein ausgelassener Fall**, zwei bekannte
Starlette/httpx-Abkündigungswarnungen, 606,95 Sekunden. Keine weiteren
Produktcodeänderungen nach diesem Lauf. Die übrigen Änderungen sind dieser
Nachweis und der präzisierte Entwicklereinstieg.

## Grenzen und weitere Abnahme

Die Erkennung ist bewusst begrenzt; beliebige freie Formulierungen werden nicht
als verstanden ausgegeben. Der ausdrückliche Lernbefehl bleibt verfügbar.
Die Auswahl bekannter Varianten im Lehrkatalog ist nur ein Metadatenhinweis,
keine Bestätigung semantischer Gleichheit. Die Inhaltsprüfung eines Modellentwurfs
und dessen Aktivierung durch den Nutzer bleiben erforderlich.

Die HTTP-Tests benutzen einen künstlichen Sprachadapter. Sie belegen Routing,
Quelle und inaktiven Vorschlag, nicht Qwens Inhaltsqualität. Neue UI, Modellrollen,
Cloudweitergabe, Werkzeugrechte oder Datenbankschemata sind nicht Teil dieser
Änderung. Die persönliche Mac-Bedienprüfung und die Alltagswoche bleiben offen.

Bei der anschließenden lesenden Prüfung des bestehenden Frontends wurde noch
ein konkreter Bedienpunkt festgestellt: „Ablauf prüfen“ führt nur nach
`/settings#ich-ablaeufe`, nicht direkt zum betreffenden Vorschlag. Dieser Punkt
ist hier nicht mit verändert und bildet einen nächsten begrenzten Schritt.

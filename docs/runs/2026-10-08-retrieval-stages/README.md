# Abrufdiagnose und Schutz erkannter Uhrzeitbedingungen

Basis: zusammengeführter CoS-Stand `30593d4`, installierter Produktcode `da5b0e6`. Der eingefrorene Katalog und seine früheren Berichte bleiben unverändert.

Die bisherige Kennzahl `retrieved_expected` prüfte tatsächlich angezeigte Quellen, nicht Suchkandidaten. Version 2 der Diagnose erhält dieses Feld kompatibel, benennt seine Bedeutung ausdrücklich und ergänzt Kandidatenfund, Auswahl, Anzeige und erste fehlende Stufe getrennt. Fehlt `working_answer.basis`, ist der Kandidatenfund **unbeobachtet**, nicht als leer gemessen. Begrenzte Rohantworten des Modells werden nur im synthetischen Werkzeug samt Pending-/Fehlerzustand erfasst.

Vier neue Stufenregressionen und zwei Modellprotokollregressionen schlugen vor der Implementierung erwartungsgemäß fehl. Abschließende betroffene Datei: **19 bestanden**. Das echte Agentenverfahren mit künstlichem Offlineanbieter und Quellenentzug bleibt enthalten. Dieser erste Diagnoseschritt änderte kein Produktverhalten. Die unten ergänzte Uhrzeitkorrektur ist dagegen eine Produktänderung; ihr Installationsnachweis folgt getrennt.

## Befund aus dem unveränderten echten Bericht

- Zwei Fragen haben die erwarteten Kandidaten, aber keine ausgewählten/angezeigten Quellen: Dachreparatur und Berichtsfreigabe. Ohne rohe Modellantwort bleibt Modellentscheidung gegenüber nachträglichem Guard ungeklärt.
- Eine Frage hat Kandidat und Auswahl; der Satzschritt liefert `nichts`: Anmeldung zum Workshop, gefragt als Seminar.
- Fünf Fragen haben keine gespeicherte Abrufspur: Serverausfall, Zugangskarte, Lieferantenverträge, Bildlizenz und Urlaubsvertretung. Daraus kann nicht bewiesen werden, dass die Suche null Kandidaten fand.
- Die direkt formulierten Fragen zu denselben Originalen sind Vergleichsfälle aus demselben Katalog, **keine unabhängige Kontrollmenge**.

## Lokaler Messversuch ohne Ergebnis

Ein getrennter lokaler Ollama-Dienst sollte bge-m3-Scores für 16 Umschreibungen, 16 direkte Vergleiche, vier nicht beantwortbare Fragen und vier zusätzliche nahe Negativfragen messen. Die Startversuche scheiterten mit HTTP 500 beim Metal-Kontext. Ein abschließender expliziter CPU-Versuch (`num_gpu=0`, `num_ctx=2048`, 45-Sekunden-Limit) bestätigte CPU-Offload 0/25, scheiterte nach etwa 1,3 Sekunden weiterhin beim Erzeugen der Metal-Command-Queue. **Keine Scores, Ränge oder Schwellenempfehlung.** Dienst beendet, keine Downloads, Cloud abgeschaltet, fremde Dienste unverändert. Private Daten wurden nicht genutzt.

Nächster Schritt ist ein funktionierender isolierter lokaler Lauf mit Stufenspur, nicht eine Wortliste oder ungemessene Schwellenabsenkung. Der Mac war beim nativen Fenstertest gesperrt; eine Ursache des Metal-Fehlers ist damit nicht bewiesen. Offene Produktqualität bleibt dieselbe wie im vorherigen Liefernachweis.

## Ergänzte Beobachtung im echten Programmweg

Die Diagnose umschließt die tatsächlichen Funktionen für Frageverständnis, Kandidatensuche und Bedeutungssuche, leitet Argumente/Ergebnisse unverändert weiter und entfernt die Wrapper auf jedem Ausgang. Dadurch wird auch ein früher Rückfall ohne gespeichertes `working_answer` sichtbar. Der `offline-trace-example.json` zeigt eine direkte Frage und eine lexikalisch leere Umschreibung mit **deterministischem Testanbieter**; er ist ausschließlich ein Instrumentierungsnachweis, keine neue Modellqualitätsmessung. Bedeutungssuche meldet Aktivierung, Zustand und eigene Referenzen getrennt. Fehler-/Wiederherstellungsregressionen sind enthalten.

## Wiederverwendbare historische Messung

Im bestehenden Repository liegt bereits `docs/evaluations/memory-quality/runs/2026-09-28-mac-acceptance/paraphrase.json`, mit exakt demselben Kataloghash. Seine bge-m3-Messung fand die später unbeobachteten fünf Quellen jeweils auf Rang 1, aber unter 0,55: Serverwartung 0,5296, Zugangskarte 0,5179, Zuliefererverträge 0,5478, Bildlizenz 0,5398, Vertretung 0,5473. `historical-similarity-analysis.json` enthält die betreffenden Werte als abgeleiteten Auszug; er ist ausdrücklich **kein neuer Modelllauf**.

Die unbeantwortbare Bankkarten-PIN-Frage hatte gleichzeitig 0,5410 zur Zugangskarte. Ein niedrigerer Score allein kann also Antwortbarkeit nicht entscheiden. Die alten Werte stützen eine konkrete Erklärung des beobachteten Musters und sparen einen Wiederholungslauf; sie ersetzen weder einen frischen produktiven Vergleich noch unabhängige Kontrollen mit ähnlichen/negierten Quellen. Die Suchschwelle wurde nicht verändert.


## Erkannte Uhrzeitbedingungen und gespeicherte Antworten

Der frühere echte synthetische Modellbericht enthält eine nachweisbare Änderung: „erst nach 10 Uhr“ wurde zu „ab 10.00 Uhr“. Die gemeinsame Satzprüfung vergleicht jetzt erkannte Uhrzeitrelationen ausschließlich mit dem Belegtext. Ein Quellenkopf kann keine zusätzliche Zeitbedingung belegen. Unterstützte Formatvarianten bleiben gleichwertig; unbekannte Modifierkombinationen werden konservativ an ihren Wortlaut gebunden. Mehrere verschiedene Bedingungen zur selben Uhrzeit können zur Zurückweisung eines eigentlich richtigen Satzes führen. Allgemeine Sachzuordnung, Satzklammern und semantische Wahrheit sind damit nicht bewiesen.

`stored-sentence-replay.json` prüft 17 früher tatsächlich erzeugte Einzelsätze mit genau einer bekannten synthetischen Quelle erneut, jeweils mit alter und neuer deterministischer Prüfung. Nur die genannte Abschwächung wird neu verworfen. Dies ist **kein neuer Modell- oder Retrieval-Lauf**. Eine gespeicherte alte Satzantwort mit dieser Abschwächung wird beim erneuten Rendern auf das unveränderte Originalzitat zurückgeführt.

Das unabhängige Review fand außerdem einen Bereichsfehler: „nur zwischen 10–12 Uhr“ ließ zwei genaue Termine „um 10 Uhr und 12 Uhr“ passieren. RED bestätigte diesen Fehler sowie falsche Neu-Paarung von Endpunkten mehrerer Zeitfenster. Zeitbereiche behalten jetzt ihre beiden Endpunkte gemeinsam und unmittelbar davorstehende erkannte Modifier. „zwischen 10 und 12 Uhr“ und „von 10 bis 12 Uhr“ sind als dieselbe Spanne prüfbar; Einzeltermine oder neu gepaarte Fenster ersetzen sie nicht. Die 15 zusätzlichen Bereichsregressionen enthalten negative und positive Fälle, auch Punkt-/Doppelpunkt-Minuten, Uhr an beiden Endpunkten und Doppelpunkt-Zeiten ohne Uhr. Das Review fand die Punkt-Minuten-Lücke in einer zweiten gezielten Kontrolle; die betreffenden Falschannahmen wurden vor der Korrektur reproduziert.

Die ursprünglichen Manipulations-, Versions- und Stichtagstests behalten ihren vorherigen Testkontext. Es wurden keine historischen Quellen oder Antworten umgeschrieben, keine Suchschwelle geändert und kein Cloudmodell aktiviert.


## Abschlussprüfung dieses Änderungsschritts

- 519 betroffene Backend-, Mail-, Zeit-, Antwort- und Diagnostiktests bestanden, eine bestehende Starlette/httpx-Deprecationwarnung. Lokale Test-Postfächer benötigen Loopback-Freigabe; ein erster Sandbox-Lauf scheiterte ausschließlich dort. Die Wiederholung mit Freigabe war erfolgreich.
- 146 Satz-/Antworttests bestanden; das gezielte unabhängige Review bestätigte beide Bereichskorrekturen und unveränderte Minuten. Die Suchwrapper zeigten im unabhängigen Diff-Review keinen konkreten Weitergabe- oder Wiederherstellungsfehler.
- Alle 17 historischen Satzurteile wurden nach der letzten Bereichskorrektur erneut gegen den eingefrorenen Katalog geprüft und bleiben wie im Replay beschrieben.
- Keine Frontendänderung, keine Änderung von Modellrollen, Importbeständen oder Datenbankschemata. Die Trefferquote des echten Modells wird durch diese Prüfung nicht neu gemessen. Der vollständige Gedächtnis-/CoS-Nachweis bleibt offen.


## GitHub und Mac geliefert

[PR 7](https://github.com/Icarus-health/kingfisher-app/pull/7) ist als `25afa58` zusammengeführt. Der geprüfte Quellstand `fc5f33e` ist inhaltsgleich zum Merge. Das aus sauberem Git-Archiv gebaute Bild `ghcr.io/icarus-health/kingfisher-app:1.0.6-local.fc5f33e` hat die Kennung `sha256:69d4712466e011f8207ef39e662fe42bd159ea5f1969a87c4a99d9b333a57413`. Ein netzloser Bildtest verwirft die beiden falschen Zeitformulierungen und akzeptiert die äquivalente Minutenspanne.

Am Mac installiert: **1.0.6-local.fc5f33e**. Vor Austausch wurde die App samt privater Konfiguration und kaltem Datenbestand unter `Kingfisher-Rueckweg/2026-10-08-vor-fc5f33e-b` im lokalen Codex-Dokumentordner gesichert. Nach Neustart wurden alle 344 vorhandenen Eintragskennungen und Inhaltsprüfsummen erhalten; die 17 SQLite-Dateien bestehen vorher und nachher die Integritätsprüfung. Konfigurationsgruppen für Mailkonten, Kalender, Cloudanbieter, Modellrollen und Zeitplan sind unverändert. Der Container nutzt weiterhin dasselbe Datenvolume und den bestehenden Loopback-Port. Der native Starter ist bytegleich, seine Bundle-Fassung und Signatur wurden aktualisiert.

Gesundheits-/Fassungs- und World-Endpunkte sind erreichbar. Dies belegt das Backend und die Datenübernahme, **keinen nativen Bedienablauf**: Der Mac war für die Computersteuerung weiterhin gesperrt, die bereits gestellte Entsperranfrage bleibt offen. Kein öffentliches Image/Release hochgeladen; der öffentliche Updater liefert diese lokale Vorschau nicht aus. Neue echte Modellmessungen waren weiterhin nicht erfolgreich; die vorherigen Metal-Startfehler sind kein gemessener Retrievalfehler.

# Lokale Gedächtnisabnahme – 28. September 2026

**Ergebnis: noch keine Freigabe als verlässlicher autonomer CoS.** Der echte
lokale Vergleich belegt Fortschritte und konkrete Fehler. Ein größeres Modell
allein behebt sie nicht. Ausgangspunkt: main `49a77e964f0a6b83f76ea0837b405246e934a63d`.

## Umgebung und Rückweg

Auf dem Mac wurde aus diesem Quellstand ein neues Containerimage gebaut.
Die bisherige Instanz auf Port 8891 bleibt erhalten und läuft wieder. Eine
konsistente Kopie ihres Datenvolumes liegt als separate Sicherung vor; die
neue Testinstanz läuft mit einer weiteren Kopie auf Port **8892**. Externe
Mail-, Kalender-, Ordner- und MCP-Anbindungen sind nur in dieser Kopie
ausgeschaltet. Automatische Modellverarbeitung wurde für den Aufnahmetest
kurz aktiviert und danach wieder pausiert. Kein Mailversand, keine Cloudaufrufe,
keine Modelldownloads. Der Nutzer bezeichnet den Kingfisher-Bestand als Testdaten.

Elf SQLite-Datenbanken bestanden die Integritätsprüfung. Die Hashes aller
vorhandenen ursprünglichen Tabellenzeilen blieben erhalten, außer der erwarteten
Schemaänderung des Suchindex: v10 ersetzt `working_memory_tokens` durch
`working_memory_terms`. Beide waren in dieser Kopie leer; das belegt ausdrücklich
keine Migration eines befüllten Index. Einstellungen der Kopie wurden für die
Isolation absichtlich geändert. Originalvolume und Sicherung bleiben unverändert.

## Modelle: vorhandener Entwicklungskatalog

Echte installierte Ollama-Modelle; identischer Katalog und unveränderter Produktcode.

| Modell | Absatzart richtig | Quellen und Status beide richtig | Sekunden je Modellaufruf |
|---|---:|---:|---:|
| qwen3.5:4b | 14/17 | 8/10 | 1,74 |
| qwen2.5:14b | 15/17 | 6/10 | 3,41 |

Das ist eine kleine Entwicklungsstichprobe, keine allgemeine Zuverlässigkeitsquote.
Das größere Modell ist hier bei Absatzarten etwas besser, bei Quellenauswahl
schlechter. Beide scheitern an der Projektmehrdeutigkeit und dem adversarialen
Quellentext S10. 14b wählt zusätzlich eine Quelle aus dem falschen Projekt und
entscheidet im Namensfall ohne die erwartete Rückfrage.

## Aufgabenerkennung beim Einspeisen

Der getrennte 16-Fälle-Entwicklungskatalog `probe_memory_requests.py` ergibt für
beide Modelle **14/16**. Die Fehler sind unterschiedlich und relevant:

- qwen3.5:4b erkennt eine ausdrückliche Unterlassungsbitte nicht richtig und macht
  aus einer eingeschleusten Aufforderung zur Kontaktweitergabe einen ungeprüften
  Aufgabenvorschlag. Es wurde nichts versandt oder automatisch als Aufgabe angenommen.
- qwen2.5:14b lässt dieselbe Unterlassungsbitte und eine ausdrückliche Zusage aus.

Eine hohe gemeinsame Punktzahl verdeckt hier verschiedene Fehlertypen. Der
Vorschlags-/Freigabeweg bleibt notwendig. Der Test bewertet zitierte Handlungen,
nicht jede mögliche Titelverfälschung oder allgemeine Sicherheit gegen fremde
Anweisungen. Beide Gewichtskennungen blieben während des jeweiligen Laufs gleich.

## Wiederfinden mit anderen Worten

Der vorhandene Katalog umfasst 16 direkte Fragen, 16 Umschreibungen und vier
unbeantwortbare Fragen. Gemessen wird das Vorkommen der gesuchten Quelle unter
den ersten zwölf Kandidaten, **nicht die endgültige Antwortqualität**.

| Suchweg | Direkt | Umschrieben | Unbeantwortbare Fragen mit Kandidaten |
|---|---:|---:|---:|
| Wortsuche | 16/16 | 3/16 | 0/4 |
| Produktiver Weg mit bge-m3 | 16/16 | 11/16 | 0/4 |

Die vorhandene Freigabeschwelle von 12/16 Umschreibungen wird nicht erreicht.
Die Bedeutungssuche wurde deshalb in der Testapp nicht dauerhaft eingeschaltet.
Die Schwelle wurde nicht nachträglich verändert.

## Neue, vorher festgelegte Prozessfälle

`holdout.json` wurde vor den Modellläufen eingefroren. SHA-256:
`e2668ac61505b420ee8b2ee7cf7205d7af49dedd03b780eb6930714395801907`.

Sieben Fälle: Bedingung in getrenntem Absatz, falsches Projekt, mehrdeutiges
Projekt, gleicher Name mit unterschiedlichen Mailadressen, relative Zeit ohne
Quellenzeit, Berichtigung/Entzug und eine umformulierte Schlüsselfrage.

Beide Modelle bestehen zunächst vier der sieben Fälle. Die Originaltexte werden
in allen Fällen unverändert aufgenommen. Quellen werden über HTTP aufgenommen,
mit dem echten lokalen Modell durch den vorhandenen Worker eingeordnet und über
den HTTP-Gesprächsweg abgefragt. Es werden keine gewünschten Antworten oder
Quellenreferenzen in den Bestand eingefügt.

Einschränkung des ersten Testaufbaus: Der Agent hatte kein Werkzeugregister.
Das beeinflusst den freien Gesprächsweg, nicht den getesteten Quellenbericht.
Der nachfolgende Lauf verwendet das Produkt-Werkzeugregister. Der Ausfall der
Bedingungsfrage wurde außerdem unabhängig in der wirklich laufenden Docker-App
mit deren normalem Agenten bestätigt: „Das weiß ich nicht“, obwohl die Quelle
aufgenommen und automatisch eingeordnet war.

### Gefundener und behobener Routingfehler

„Unter welchen Voraussetzungen …?“ bzw. „Unter welchen Bedingungen …?“ wurde
nicht als Gedächtnisfrage erkannt. Die Frage ging am vorhandenen Quellenbestand
vorbei. Die eng begrenzte Erkennung dieser Frageformen nutzt jetzt bei vorhandenen
Kandidaten denselben Quellenweg wie andere Sachfragen. Zusätzliche Sendeaufträge
bleiben im bestehenden Aktions-/Freigabeweg; allgemeine Fragen ohne Quelle bleiben
im normalen Gespräch.

Vier neue Tests schlugen vor dem Fix erwartungsgemäß fehl, drei Kontrollfälle
bestanden. Nach dem Fix bestehen 91 betroffene Tests. Der echte lokale Wiederlauf
mit qwen3.5:4b liefert jetzt den vollständigen Bedingungstext und die korrekte
Quelle; fünf von sieben Fällen bestehen. Das ist ein Entwicklungsnachtest derselben
Fälle, kein neuer unabhängiger Holdout.

### Weiterhin blockierend

- **Falscher Projektbezug:** Die Frage zu Felsenpark kann eine Birkenhain-Quelle
  zurückbekommen, wenn Projektbezüge nur im Originaltext stehen. Weder die
  Modellaufforderung noch ein größeres Modell sichern diese Grenze zuverlässig.
- **Mehrdeutigkeit:** Eine allgemeine Frage nach der Schlüsselübergabe kann einen
  der beiden Projekttermine herausgreifen, statt die nötige Auswahl anzubieten.
  Das größere Modell liefert in einem Lauf beide Quellen, fragt aber ebenfalls
  nicht nach dem gemeinten Projekt.
- **Unvollständige Bedeutungssuche:** Fünf der 16 Umschreibungen bleiben ohne die
  gesuchte Quelle. Eine Modellaufrüstung ist kein Ersatz für Kandidatenabdeckung.

Projektzuordnung darf deshalb als nächster Schritt nicht bloß durch weitere
Promptformulierungen „verbessert“ werden. Nötig sind beleggebundene Projekt- und
Vorgangsbezüge, ein kontrollierter Umgang mit fehlender Zuordnung und eine Prüfung
gegen vertauschte sowie mehrdeutige Projekte. Automatisch erkannte Zuordnung bleibt
korrigierbare Interpretation und wird nicht zu bestätigter Wahrheit.

## Laufende App und Neustart

Separater synthetischer Vorgang „Ulmenblick“ über echtes HTTP und den automatischen
lokalen Worker: Aufnahme erfolgreich; direkte Frage liefert die Originalquelle
samt noch fehlender Zustimmung. Nach Berichtigung verschwindet die alte Antwort;
die neue Antwort enthält den geänderten Termin. Nach Entzug der Berichtigung
bleibt ihr Inhalt auch nach echtem Docker-Container-Neustart im alten Gespräch
unsichtbar. Das wurde zusätzlich in der Browseroberfläche geprüft.

Die falsche Projektfrage ergab in diesem Lauf eine unpassende Personenrückfrage
mit der Ulmenblick-Quelle. Das ist ebenfalls keine korrekte Antwort; es unterscheidet
sich von der stillen Falschauswahl im isolierten Modelllauf. Kein Erfolg wird daraus
abgeleitet.

## Reproduzieren

Vorhandene Modellskripte stehen unter `scripts/`. Die JSON-Dateien dokumentieren
Katalog, Modell und Einzelfälle. Für den neuen Prozesslauf liegt
`run_holdout_registry.py` neben `holdout.json`; vom Repository aus:

```sh
PYTHONPATH=sidecar python docs/evaluations/memory-quality/runs/2026-09-28-mac-acceptance/run_holdout_registry.py --model qwen3.5:4b
```

Nur synthetische Daten und lokale Ollama-Aufrufe. Ergebnisdateien werden nicht
überschrieben. Der im Runner angegebene Commit bezeichnet den Basisstand;
mit diesem PR ist zusätzlich die dokumentierte Routingkorrektur aktiv.

Die Testapp ist für kontrollierte weitere Prüfung bereit, nicht als fehlerfreies
Gedächtnis abgenommen. Native Tauri-/Keychain-/Kalenderabnahme und mehrtägiger
Alltag sind nicht Teil dieser Messung.

## Abschlussprüfung der Routingänderung

Der vollständige Sidecar-Lauf ergab 2430 bestandene Tests und vier durch die
lokale Sandbox blockierte Port-Bindungen (drei Fehler beim Modelllisten-Testserver,
ein Fehlschlag beim Wiederherstellungsstarter). Diese vier sind Umgebungsfehler
`PermissionError: Operation not permitted`, keine behaupteten grünen Tests.
Die betroffenen Testdateien bestanden anschließend mit erlaubtem Loopback:
15/15, einschließlich aller vier zuvor blockierten Tests. Damit sind alle
2434 Sidecar-Tests auf demselben Code geprüft; es wird kein einzelner
vollständig grüner Lauf behauptet.
Zwei bestehende Bibliotheks-Abkündigungswarnungen bleiben sichtbar.

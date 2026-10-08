# Mailfortschritt: Verlauf, neue Post und Warten auseinanderhalten

## Reproduzierter Nutzerfehler

Bei 6 von 10 aufgenommenen Verlaufsmails und vier neu eingehenden ausgefilterten Newslettern addierte der Status die neuen Newsletter zum alten Bestand: „aktuell“, obwohl vier alte Mails noch fehlten. Bei fertig gelesenem Verlauf entstand entsprechend „2 von 1“. Nach Wiederholung eines fehlgeschlagenen oder ausgefilterten neuen Eintrags wurde ebenfalls „aktuell“ behauptet, obwohl `live_pending=1` war; reine Live-Fehler boten in der Technikansicht keinen Wiederholungsknopf.

Zusätzlich stoppt der bestehende Lastschutz weitere Verlaufsmails bei mehr als 200 noch nicht eingeordneten Originalen, während neue Post weiterlaufen darf. Die Anzeige erklärte dieses Warten bisher als aktives Einlesen.

## Änderung

`filtered/filtered_by` gehören nun wie `total/captured/pending` ausschließlich zum Verlauf; `live_filtered/live_filtered_by/live_failed` beschreiben neue Post separat. Der Wiederholungsknopf berücksichtigt Fehler und ausgefilterte Mails aus beiden Wegen. Offene neue Post bleibt im Zustand „liest“ sichtbar, auch wenn der frühere Verlauf vollständig gelesen ist. Die Fortschrittsstufe kann bei offenen neuen Einträgen nicht „current“ heißen.

Die vorhandene Lastschutzabfrage wird gemeinsam für Abrufentscheidung und Anzeige verwendet. `history_waiting_for_analysis` liefert einen eigenen Wartezustand mit Zahlen und Hinweis auf das Sortieren. Einrichtung, Heute-Lernanzeige und Technikansicht übernehmen denselben Postfachsatz; in der Technikansicht führt ein direkter Link zur bestehenden Gedächtnis-Verarbeitung. Globale Pause bleibt vorrangig, Kontopause separat. Keine Änderung an Schwelle, Abrufpriorität, Filterregeln, Originalen oder Freigaben; keine neue Datenbankmigration.

## Nachweise

- Sechs unabhängige Backendregressionen: vorher fünf Fehler/ein Kontrollfall bestanden. Zwei zusätzliche Wartefälle vorher rot; drei Warte-/Pausentests danach grün. 72 betroffene Backendprüfungen bestanden.
- Fünf neue UI-Funktionstests. Das unabhängige Review fand einen zusätzlichen Einrichtungsfehler: trotz korrektem Backend nach Live-Retry „Alle 1 Mails gelesen“. Der ergänzte Test wurde vor der Korrektur rot gesehen und danach grün. Alle 391 automatisierten Oberflächenprüfungen sowie TypeScript-/Produktionsbuild bestanden. Ein vorhandener Quelltext-Vertragstest wurde für die nun gemeinsame Filter-Retryzahl angepasst; er ist kein gerenderter Interaktionstest.
- Unabhängiger Reviewer: 9/9 enge Backendtests und 5/5 neue UI-Tests selbst ausgeführt; kein verbliebener bestätigter Funktionsfehler im Diff. Originalbelege, Entzug und Freigaben werden durch diesen Anzeige-/Zählerpatch nicht ersetzt.
- Fertiges Image: 264 Paketdateien und 112 Oberflächendateien byteweise mit dem geprüften Stand identisch. Netzloser Smoke mit echtem Intake/Originalspeicher, künstlichem Mailserver, Filter, Live-Fehler/Retry und Lastschutz-Warten/Fortsetzen besteht bei 128MB und ohne Modellaufruf.

Bestehende Warnungen: Starlette/httpx-Deprecation im Backend und große JavaScript-Chunks im Build. Kein vollständiger Backendlauf ohne neuen Anlass.

## Bedienprüfung und Grenzen

Prüfablauf wäre: Einstellungen → älteren Mailbestand ansehen → Wartegrund erkennen → automatisches Sortieren öffnen; zusätzlich ausschließlich neuen Abruffehler erneut versuchen. Der getrennte künstliche Testserver startete auf dem vom Nutzer genannten Port 8893, ohne Scheduler, echte Konten oder Modell. Die Computersteuerung verweigerte die Navigation ausdrücklich wegen einer gespeicherten Zugriffspräferenz. Kein Wechsel auf alternative Browser, Ports oder Steuerungswege; eigener Testserver anschließend beendet. Native App ebenfalls erneut wegen gesperrtem Mac nicht bedienbar.

| Nachweis | Stand |
|---|---|
| Automatisierte fachliche Backend-/UI-Prüfungen | bestanden |
| Typprüfung und Produktionsbuild | bestanden |
| Paketinhalt und netzloser Backend-Paketablauf | bestanden |
| Gerenderte Seitenidentität, Layout, Konsole, Screenshot, Klickfolge | gesperrt / nicht geprüft |
| Native Tages-/Akkuabnahme | offen |

Die gemeinsame Metadatenabfrage begrenzt die Ergebnismenge auf 201, garantiert aber keine konstante Laufzeit über beliebig viele schon abgearbeitete Einträge. Große persönliche Bestände wurden hier nicht als performant abgenommen. Die bekannte pauschale Angabe „Anhänge nicht unterstützt“ bleibt ein separater offener Produktfehler: vorhandener begrenzter PDF-/Bildpfad und dessen Lücken müssen korrekt durch API/Anzeige geführt werden. Kein vollständiger Postfachimport, keine allgemeine Gedächtnis-/Antwortqualitätsabnahme und kein fertiger CoS behauptet.

## Lokale Lieferung

Produktcommit `540f75e65d23206e765e3705531f05c11cf848b1`, lokal **1.0.6-local.540f75e**. Image `sha256:23a2e9d818a3fdeab0f2c6071fb20ebad36c0cc0a1144c2188d6df165adeebc4`. Kalte Sicherung `Kingfisher-Rueckweg/2026-10-08-vor-540f75e`; 344 Original-IDs/Inhaltsdigests und 17 SQLite-Dateien erhalten/geprüft, gleiches Datenvolume. Konten, Kalender, Anbieter, Modellrollen und Zeitpläne erhalten. Native Binärdatei unverändert, Signatur geprüft, Backend gesund. Importpause besteht; Ollama bleibt aus, Bedeutungssuche deshalb `unavailable`.

Kein öffentlicher Imageupload/Release, keine Cloudinferenz, keine Modellinstallation, keine CI-Wiederholung, kein Abonnement und kein Check-in.

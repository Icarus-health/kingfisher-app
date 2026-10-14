# Mail und Gedächtnis: Abschluss der vier offenen Abläufe

Stand: 14.10.2026. Code 1.0.13; installierte Mac-Fassung 1.0.12 bleibt bis zur anschließenden Abnahme erhalten. Umsetzung nach `docs/superpowers/specs/2026-10-14-workflow-completion.md`. PR #64.

## Ergebnis

| Ablauf | Sichtbares Verhalten |
| --- | --- |
| Gmail-Liste | IMAP lädt höchstens 64 KiB je Vorschau einschließlich Größenangabe; auch ein regelwidrig vollständiger Serverreply wird vor dem Parsen begrenzt. Einzelmail-Lesen bleibt separat. |
| Gespeicherte Mail | Lokaler Originalüberblick, Aufgaben- und Projektprüfung nach ausdrücklicher Aktion; gemeinsame Annahme, erneute Projektprüfung und erhaltene Entwürfe. |
| Organisationen | Konservative lokale Namensvorschläge, ausdrückliche editierbare Vorschau, Ablehnung und Undo. Einzelakten/Rechnungsaussteller bleiben getrennt. |
| Dokumente | Vollständige aktuelle Titel-/Inhaltssuche, Bereiche/Projekte/Unterordner und echte Trefferzahlen/Seiten. Offene Notizen folgen aktuellen Revisionen. |

Quellenstand, Entzug, Projektabschluss, doppelte Annahme und Metadatenrevision werden vor Schreibvorgängen erneut geprüft. GET/Blättern startet keine Modellarbeit. Der kleine Mail-Hintergrundhook verwendet den RAW-Rollenprovider und bindet Agent, Modellkennung, Freigabeplan, Automationgeneration und laufende Schedulerfreigabe. Er schaltet keine Pause um.

## Prüfungen

- 697 UItests bestanden; TypeScript und Produktionsbuild erfolgreich. Bestehende Warnung über ein großes JS-Bundle bleibt.
- 69 betroffene Backendtests nach den letzten Domainkorrekturen bestanden.
- Abschließender vollständiger Backendlauf: **6.604 passed, 1 skipped, 26 subtests passed**, 993,04 Sekunden. Zwei bestehende Warnungen (Starlette/httpx; ungültige Escape-Sequenz in bestehendem Regex). Backend unverändert seit 498215c; abschließende UI-Text-/Kontrastkorrektur in 1951961 gesondert durch 697 UItests/Build und Browser bestätigt.
- Im ersten Vollauf gab es eine veraltete strikte API-Felderwartung für das neue `truncated=False`. Sie wurde ausdrücklich ergänzt; Volltext und Reply-Adresse bleiben in der Listenantwort verboten. Danach beide betroffenen Verträge und der obige gesamte Lauf bestanden.
- Pakete unabhängig reviewed; Gegenfälle vor Korrektur reproduziert und per Sabotage gesichert. Abschlussreview und Nachreviews ohne verbleibendes P1/P2 im geprüften Umfang.
- Reale Browserbedienung mit getrenntem FastAPI-Server und künstlichen Daten bei 900 und 1.280 Pixeln; installierte App unberührt. Vollständiger WCAG-Audit und reale Modellqualität sind damit nicht belegt.

Browserabläufe: historische Mail vorbereiten, Aufgabe und neues Projekt gemeinsam bestätigen, Aufgabe unter „Ohne Termin“ wiederfinden; direkte Aufgabenverknüpfung; Speicherbestätigung nach lokalem Refresh; Dokumentseite 2 von 3 und Inhaltsfund, bestätigte Ordnerzuordnung; bereits geöffnete Notiz nach separater API-Änderung vonRevision 1 auf 2; Organisationsbestätigung, Ablehnung/Rücknahme und Gruppen-Undo. Kein horizontaler Überlauf in beiden Breiten, keine relevanten Browserkonsolenfehler.

Die synthetischen Modellantworten prüfen UI/Server-Verträge. Sie beweisen keine reale Extraktionsqualität oder Qwen-Latenz auf dem Mac. Auszüge sind ausgewählte vollständige Originalpassagen, keine frei erfundenen Zusammenfassungen.

## Relevante Gegenfälle

Das erste Task2-Testfixture verwendete einen RLock und verdeckte einen echten Produktionsdeadlock. Die Browserprobe blockierte nach der Modellantwort; Ursache:verschachtelter Erwerb des nicht-reentranten `create_app`-Locks. Behoben mit einem nur unter gehaltenem Lock verwendeten Lesehelper und gemeinsamer gesperrter Annahme. Globale Locksemantik unverändert. 24 bestehende Workflowtests verwenden jetzt den tatsächlichen Locktyp; vier zusätzliche begrenzte create_app-Endpunkttests prüfen Erstvorbereitung/Cache/Fehler/Retry/Annahme/Duplikat und gehaltene Schreibsperre.

Weitere behobene Befunde:permanent hinter fertigem Cache verborgenes Projekt-Retry; Entwurfsverlust bei Original-503; veraltete Gruppenrevision/Kandidatenkennung nach Konflikt; Gruppenmitglied doppelt nach Undo; Quellenentzug bei Gruppenrestaurierung; alter Body einer geöffneten aktualisierten Notiz; verschwundene Speicherbestätigung nach der nächsten leeren Vorschlagsliste.

## Grenzen und Mac-Abnahme

- Gmail-TLS/Anmeldung waren erreichbar. Die alte Liste mit 30 vollständigen MIME-Nachrichten überschritt 6 Sekunden; begrenzte Probe mit 30 Vorschauen dauerte 1,451 Sekunden innerhalb unveränderter 6 Sekunden. Ein vorheriger begrenzter Abruf hatte dennoch einen Timeout. Das ist eine beobachtete Laufzeit, keine zukünftige Netzgarantie. Keine Inhalte/Konten/Zugänge in dieser Dokumentation.
- Synthetischer Maßstab: 6.001 Dokumente/Zuordnungen und 601 Bereichskorrekturen. Vollabfragen etwa 0,73–0,82 Sekunden; 25 Treffer etwa 14 KiB. Größere/längere persönliche Bestände sind nicht abgenommen; Vollscan-/Lockdauer wächst mit dem Bestand.
- Mailüberblick maximal 8.000 Quellzeichen und drei Passagen à 1.200 Zeichen; Ausschnitte erzeugen keine neuen Aufgaben. Ein begrenzter Hintergrundtakt bearbeitet den jüngsten Bestand; ältere Quellen lassen sich ausdrücklich öffnen/vorbereiten.
- Vergleich 16 maßgeblicher installierter Original-/Arbeitstabellen:unverändert. Großimport und Cloud-/Onlinefreigaben nicht geändert.
- Noch offen:Mac-Update mit Sicherung und normalem Updater, anschließend reales Qwen-/Konten-/Kalender-/Speicherverbrauch-Verhalten im App-Fenster. Keine Produktivinstallation oder Alltagstauglichkeit allein aus diesen künstlichen Proben behauptet.

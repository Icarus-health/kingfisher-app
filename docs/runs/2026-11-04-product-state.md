# Produktabnahme: belastbarer Stand vom 4. November 2026

Diese Matrix unterscheidet gebauten Code, isolierte Prüfungen und die tatsächlich
benutzte App. Sie ersetzt keine historischen Protokolle und erklärt deren
unterschiedliche Aussagekraft. Aktualisiert nach der gemeinsamen Prüffassung
[PR #124](https://github.com/Icarus-health/kingfisher-app/pull/124). Die jeweiligen
Produktionscode-Prüfsummen stehen bei den einzelnen Läufen. Veröffentlichte
Mac-Fassung und aktuelle Prüffassung sind weiterhin verschiedene Stände.

| Bereich | Gebaut / Regressionen | Echtes Modell, getrennte künstliche Daten | Aktualisierte Mac-App | Alltag |
|---|---|---|---|---|
| Auftraggeber, Ausführender, Empfänger; Bitte/Zusage; Termin/Frist | Rollenhinweise korrigiert, betroffene Worker-/Harness-Tests bestanden | Qwen9B: 9/9 eingefrorene Fälle in der getrennten Laufzeit inhaltlich geprüft | Mit 1.0.44 installiert; persönliche Modellabnahme nach Update offen | Offen |
| Kategorien und Beleganker | Genaue Belegprüfung unverändert; vorhandener einzelner Cloud-Korrekturversuch erhält gezielte Fehlerangaben; 68 betroffene Tests bestanden | Lokale künstliche Aufnahme: 7/7 Prüffälle; konkrete entfernte Ankerkorrektur noch nicht live abgenommen | Mit 1.0.44 installiert; breite Qualitätsprobe offen | Offen |
| Suchkontext | Abfrage-Hilfswörter eingegrenzt, keine persistente Indexänderung; 522 betroffene Tests bestanden | BGE-M3: 9/10 exakte Quellensätze, erwartete Quellen immer enthalten; ein zusätzlicher Alex-Treffer bleibt dokumentiert | Mit 1.0.44 installiert; Suche und Original geöffnet, keine neue Modellabnahme | Offen |
| Personenwahl und belegte Antwort | Frühere 162 Tests; nach im Fenster gefundenem Paraphrasefehler 538 betroffene Tests bestanden, Originalauswahl und bestätigte Personenwahl korrigiert | Frühere sechs Fragen bestanden; neue echte API-Probe: Kontakt und zwei Fristen 3/3 korrekt, gespeichert und erneut gelesen | Getrenntes natives Fenster: finale drei Antworten korrekt angezeigt, Schuloriginal geöffnet, Kalender-Rückweg und neuer Entwurf erhalten; anschließend normal auf 1.0.44 aktualisiert | Offen |
| Speicher und Hintergrundlast | Unveränderte Probegrenzen, sichere Unterbrechung bei zu wenig Reserve | Ressourcenabbrüche bleiben dokumentiert; letzte drei Antworten Minimum 31% frei, Druck maximal 2, je 4–11 Sekunden | Kalender/Rückweg und Entwurf im Testfenster geprüft; zusammenhängender Mail-/Kalender-/Eingabeablauf während Dauerlast noch offen | Dauerbetrieb offen |
| Skillbibliothek und CoS-Abläufe | Einmalige Konfliktauswahl, inaktive Lernvorschläge, begrenzte Mistral-Prüfung, gemeinsame Mailaufgabe/Projekt und Kalender-Ausfallvorschau in PR124 zusammengeführt; 857 betroffene Backendtests, nach weiterer Mistral-Aufgabenergänzung 1.076 UI-Tests bestanden | Begrenzte echte Qwen-Lernprobe dokumentiert; kein Mistral-Schlüssel/keine echte Mistral-Probe | Künstlicher gemeinsamer Browserablauf geprüft; jüngste Anzeige-Nacharbeit und separates natives Gesamtfenster noch nicht abgenommen | Offen |
| Mistral-Aufgabenpakete | Ausdrücklicher Aufgabenumfang, vorhandene Extraktion/Gegenprüfung, lokale Belegregeln, erhaltene Ablehnung und passende Pilot-Schranke; 217 betroffene plus 57 angrenzende Tests bestanden | Kein Schlüssel, keine echte Modellqualität; nur simulierte Anbieterantworten | Noch nicht installiert oder nativ geprüft | Offen |
| Sicherung und Wiederherstellung | Verschlüsselter Roundtrip erhält alle Bereiche; lesende Vorprüfung und nun getrennte schreibbare Arbeitskopie mit frischen Rechten. Gefüllten Bestand lesen, Aufgabe speichern, Stores neu verdrahten und nach App-Neustart wiederfinden geprüft; 37 direkte Tests und unabhängiger Review bestanden | Keine Modellarbeit beim Restore; eigene neue Schlüssel und Freigaben erforderlich | Normale Update-Sicherung bei 1.0.44 nachgewiesen; Prüfansicht und Arbeitskopie noch nicht nativ abgenommen | Nativer Wiederherstellungsablauf und Nutzungswoche offen |
| Erweiterungsplattform | Vorhandene begrenzte Laufzeit; voller P6-Modulvertrag ist weiterhin Planarbeit | Isolierte Rollenprobe ist kein Nachweis einer vollständigen Pluginplattform | Offen | Offen |

## Nachweise

- [Rollen, Aufnahme und Beleganker](2026-11-04-source-roles/README.md)
- [Suchkontext und bewusst offener Gegenfall](2026-11-04-retrieval-precision/README.md)
- [Personenwahl: Fehler, Ressourcenabbruch und vollständig bestandener Folgelauf](2026-11-04-person-choice/README.md)
- [Im Mac-Fenster gefundener Paraphrasefehler und korrigierte Originalauswahl](2026-11-04-person-original-answer/README.md)
- [Abschlussreview: widersprüchliche Zusätze verlangen eine Personenwahl](2026-11-04-person-continuation/README.md)
- [Gemeinsamer Ablauf und weiterhin offene Auslieferung](2026-11-04-product-integration/README.md)
- [Historischer Zugriff auf gesicherte Skills und Korrekturen](2026-11-04-workflow-recovery/README.md)
- [Lesende Sicherungsprüfung, unabhängige Reviews und verbleibende P5-Lücke](2026-11-04-recovery-preflight/README.md)
- [Getrennte Arbeitskopie: normale Weiterbearbeitung, Neustart und frische Rechte](2026-11-04-recovery-working-copy/README.md)
- [Verbindlicher Produktplan P0–P6](../superpowers/plans/2026-11-04-kingfisher-product-completion.md)

Die Testzahlen stammen aus unterschiedlichen abgegrenzten Läufen und werden
nicht zu einem vermeintlichen Gesamt-Abnahmeergebnis addiert. Der Suchtest misst
gelieferten Kontext; der Personenlauf prüft tatsächlich ausgegebene Antworten.
Die Aufnahmefälle ersetzen weder die persönliche Mailstichprobe noch einen
bislang unbenutzten Prüfungssatz. Die Satzprüfung verwendet dasselbe Modell;
der gesonderte inhaltliche Review ist deshalb ausdrücklich ausgewiesen.

Der letzte vorliegende Installationsnachweis betrifft den Dienst einschließlich
Oberfläche **1.0.44**, am 04.11.2026 über den normalen Updateknopf installiert.
Der unveränderte native Starter trägt weiter 1.0.43. Die geschützte lokale
Updatequittung dokumentiert automatische Sicherung, identische Originalquellen,
erhaltene Konten/Modellwahl und weiterhin pausierten Großimport. Diese Matrix
behauptet keine neue Live-Inventur. **PR124 ist noch nicht gemergt, veröffentlicht
oder auf dem persönlichen Mac installiert.** Für jedes Update bleiben Sicherung,
Datenprüfung und normaler Updateweg verbindlich.

Großimport weiterhin pausiert. Keine persönlichen Quellen veröffentlicht, keine
bezahlten Modellaufrufe, keine andere App geschlossen. P0 ist noch nicht als
Ganzes abgenommen; P1–P6 und die Nutzungswoche bleiben offen.

- [Mistral-Aufgabenpakete und Grenzen](2026-11-04-mistral-task-package/README.md)
- [Bereichsablage mit 50.000 Kunstquellen](2026-11-04-memory-area-scale/README.md)

# Produktabnahme: belastbarer Stand vom 4. November 2026

Diese Matrix unterscheidet gebauten Code, isolierte Prüfungen und die tatsächlich
benutzte App. Sie ersetzt keine historischen Protokolle und erklärt deren
unterschiedliche Aussagekraft. Aktueller Reparaturzweig: PR #117,
Die jeweiligen Produktionscode-Prüfsummen stehen bei den einzelnen Läufen;
die neueste Korrektur betrifft die Auswahl unveränderter Personen-Originalsätze.

| Bereich | Gebaut / Regressionen | Echtes Modell, getrennte künstliche Daten | Aktualisierte Mac-App | Alltag |
|---|---|---|---|---|
| Auftraggeber, Ausführender, Empfänger; Bitte/Zusage; Termin/Frist | Rollenhinweise korrigiert, betroffene Worker-/Harness-Tests bestanden | Qwen9B: 9/9 eingefrorene Fälle in der getrennten Laufzeit inhaltlich geprüft | Noch offen; der Fehler wurde zuvor in 1.0.43 beobachtet | Offen |
| Kategorien und Beleganker | Genaue Belegprüfung unverändert; vorhandener einzelner Cloud-Korrekturversuch erhält gezielte Fehlerangaben; 68 betroffene Tests bestanden | Lokale künstliche Aufnahme: 7/7 Prüffälle; konkrete entfernte Ankerkorrektur noch nicht live abgenommen | Noch offen | Offen |
| Suchkontext | Abfrage-Hilfswörter eingegrenzt, keine persistente Indexänderung; 522 betroffene Tests bestanden | BGE-M3: 9/10 exakte Quellensätze, erwartete Quellen immer enthalten; ein zusätzlicher Alex-Treffer bleibt dokumentiert | Noch offen | Offen |
| Personenwahl und belegte Antwort | Frühere 162 Tests; nach im Fenster gefundenem Paraphrasefehler 538 betroffene Tests bestanden, Originalauswahl und bestätigte Personenwahl korrigiert | Frühere sechs Fragen bestanden; neue echte API-Probe: Kontakt und zwei Fristen 3/3 korrekt, gespeichert und erneut gelesen | Getrenntes natives Fenster: finale drei Antworten korrekt angezeigt, Schuloriginal geöffnet, Kalender-Rückweg und neuer Entwurf erhalten; normale Installation noch offen | Offen |
| Speicher und Hintergrundlast | Unveränderte Probegrenzen, sichere Unterbrechung bei zu wenig Reserve | Ressourcenabbrüche bleiben dokumentiert; letzte drei Antworten Minimum 31% frei, Druck maximal 2, je 4–11 Sekunden | Kalender/Rückweg und Entwurf im Testfenster geprüft; zusammenhängender Mail-/Kalender-/Eingabeablauf während Dauerlast noch offen | Dauerbetrieb offen |
| Skillbibliothek und CoS-Abläufe | Vorhandene Implementierung ist Grundlage; keine neue vollständige Abnahme in diesem Reparaturpaket | Zusammenhängende P2-/P3-Prüfung noch offen | Offen | Offen |
| Erweiterungsplattform | Vorhandene begrenzte Laufzeit; voller P6-Modulvertrag ist weiterhin Planarbeit | Isolierte Rollenprobe ist kein Nachweis einer vollständigen Pluginplattform | Offen | Offen |

## Nachweise

- [Rollen, Aufnahme und Beleganker](2026-11-04-source-roles/README.md)
- [Suchkontext und bewusst offener Gegenfall](2026-11-04-retrieval-precision/README.md)
- [Personenwahl: Fehler, Ressourcenabbruch und vollständig bestandener Folgelauf](2026-11-04-person-choice/README.md)
- [Im Mac-Fenster gefundener Paraphrasefehler und korrigierte Originalauswahl](2026-11-04-person-original-answer/README.md)
- [Verbindlicher Produktplan P0–P6](../superpowers/plans/2026-11-04-kingfisher-product-completion.md)

Die Testzahlen stammen aus unterschiedlichen abgegrenzten Läufen und werden
nicht zu einem vermeintlichen Gesamt-Abnahmeergebnis addiert. Der Suchtest misst
gelieferten Kontext; der Personenlauf prüft tatsächlich ausgegebene Antworten.
Die Aufnahmefälle ersetzen weder die persönliche Mailstichprobe noch einen
bislang unbenutzten Prüfungssatz. Die Satzprüfung verwendet dasselbe Modell;
der gesonderte inhaltliche Review ist deshalb ausdrücklich ausgewiesen.

Der letzte vorliegende Installationsnachweis betrifft 1.0.43. Dieser Zweig wurde
noch nicht installiert, gemergt oder als neue Fassung veröffentlicht. Alte
Angaben zu erhaltenen Originalen/Kalendern sind datierte Installationsnachweise,
keine in diesem Dokument neu gezählten Bestände. Für jedes Update bleiben
Sicherung, Datenprüfung und normaler Updateweg verbindlich.

Großimport weiterhin pausiert. Keine persönlichen Quellen veröffentlicht, keine
bezahlten Modellaufrufe, keine andere App geschlossen. P0 ist noch nicht als
Ganzes abgenommen; P1–P6 und die Nutzungswoche bleiben offen.

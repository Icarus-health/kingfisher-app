# Personenwahl vor allgemeiner Frist-/Aufgabenfrage

30. Oktober 2026. Basis `origin/main` = `b7ffa30e05c849946c562fe15684bbd4199a4349` (1.0.30). **Code und lokale Prüfungen abgeschlossen; keine neue Fassung veröffentlicht oder in der persönlichen Mac-App installiert.** Keine Datenmigration, keine Änderung bestätigter Personen und keine Fortsetzung des Großimports.

## Konkreter Fehler und Korrektur

Im getrennten Hermes-/Kingfisher-Vergleich wählte „Welche Frist hat Alex?“ ohne Rückfrage Winter, obwohl auch Alex Sommer vorkam. Der einzige Träger des Betreffworts „Frist“ galt in `personenfrage.unterscheidet` als gemeinte Person. Zudem konnten gleiche fünf Anfangsbuchstaben ganz verschiedene Projektnamen verbinden.

Die Entscheidung trennt jetzt:

- ausdrückliche vollständige E-Mail-Adresse (bisheriger Vorrang),
- ausdrücklich genannte vollständige Domäne als eigener Kandidatenrahmen; eine gemeinsame Domäne allein wählt keinen Menschen und widersprüchlicher Projekt-/Domänenkontext bleibt offen,
- passende Domänenwörter und ausdrücklich benannten Zusammenhang wie „Projekt Atlas“, „beim Catering“, „von dem Institut“ oder eine konkrete Preisfrage „Catering von Alex“.

Beliebige Betreffwörter allein genügen nicht mehr. Allgemeine Inhalts-/Vorgangsarten wie Nachricht, Termin und Aufgabe, Zeitbegriffe und reine Zahlen belegen auch hinter Präpositionen keine Identität. Echte Adressen bleiben davon unberührt; vollständige eindeutige Domänen werden nicht versehentlich durch den Wortfilter verloren. Wörter werden nach vorhandener Umschriftnormalisierung exakt verglichen, ohne Fünfbuchstaben-Raten.

Vorhandene gespeicherte, still zugeordnete Antworten verlieren durch den neu berechneten `person_scope_basis` ihre Gültigkeit. Kein Zurückschreiben oder Löschen von Originalquellen nötig. Die normale Rückfrage und die Auswahl eines Menschen werden wiederverwendet.

## Verifikation

| Prüfung | Ergebnis |
|---|---|
| Unveränderter Ausgangsstand, zwei betroffene Dateien | 34 bestanden |
| Finale betroffene Personen-/Abrufdateien | 75 bestanden, davon 41 neue Parameterfälle |
| Breite Pflicht-/Gedächtnisregression, 42 Dateien | 796 bestanden; vorhandene Starlette-Testclient-Warnung |
| Sabotage: finale Tests in separatem `git archive origin/main sidecar` | 29 erwartet fehlgeschlagen, 46 bestanden; alter Modulpfad vorab protokolliert |
| Unabhängiger read-only Review | 14 zusätzliche synthetische Kontrollen bestanden; keine verbliebenen blockierenden Befunde im Parserfix |
| Mac-lokaler echter Gesprächs-HTTP-Weg, gleiche zehn künstliche Mails | Drei getrennte Alex-Identitäten vor jeder Modellarbeit; ausdrückliche Wahl → exakte geänderte Originalfrist 04.11.2026, 18 Uhr |

Der Review fand und beseitigte generische Präpositionsumgehungen („aus der Nachricht“, „beim Termin“), fehlende ausgeschriebene/quotierte Organisationsformen sowie die zunächst verlorene vollständige Domäne `frist.example`. Diese Fälle stehen dauerhaft in den Tests. Monate/Wochentage stammen aus bestehenden Datumsmodulen; unauflösbarer Kontext bleibt eine Rückfrage. Dies ist keine vollständige natürlichsprachliche Identitätsprüfung.

Die Sabotage verwendet ausschließlich den unveränderten alten Produktcode und die neuen Tests. Die echte Arbeitskopie wurde nicht zurückgestasht. Negative Läufe aufgrund eines anfänglich zu früh prüfenden Semantic-Service-Testdoubles wurden nicht als Beleg gezählt; das endgültige Double unterscheidet Service-Anmeldung von tatsächlicher Suche.

## Mac-/Qwen-Probe und Lastgrenze

`probe.json` enthält die tatsächlich zurückgelesenen Ergebnisse. Die bereits im vorigen Vergleich mit Qwen klassifizierten Textbereiche wurden auf dieselben zehn unveränderten künstlichen Originale in einem neuen lokalen Bestand übertragen. **Kein erneuter Aufnahmegütevergleich.** Der normale Gesprächseinstieg benötigt für die Personenwahl etwa 26 ms und null Modellaufrufe. Nach Wahl der Arbeitsadresse wählte das vorhandene Qwen9B genau die Quelle `deadline-change`; Rückgabe nach 15.8 s.

Ein zusätzlicher Formulierungsaufruf wurde vom **Probe-Guard**, nicht von neuem Produktcode, wegen nur noch 23% freier Systemquote verworfen. Kingfisher zeigte darauf die korrekte Originalstelle statt einer freien Formulierung. Die Probe zählt dies ausdrücklich als vorsichtigen Zitat-Fallback, nicht als erfolgreiche Modell-Satzantwort oder Nachweis jederzeit flüssiger Mac-Bedienung. Qwen wurde nach dem Lauf entladen; nach kurzer Beruhigung meldete der Mac Druckstufe 1 und 49% freie Systemquote. Keine privaten Mail-/Kalenderquellen und keine Cloudschlüssel verwendet.

Die installierte persönliche App wurde nicht umgeschaltet. Ein Fenstertest und der normale Updateweg bleiben für diese neue Korrektur ausstehend. Unveränderte Oberfläche; deshalb kein Frontend-/Asset-Umbau.

## Reproduktion

In einer getrennten Python-3.12-Umgebung die vorhandenen `sidecar[dev]`-Abhängigkeiten installieren. Danach:

```sh
ICARUS_DATA_DIR=/private/tmp/kingfisher-person-test python -m pytest -q \
  sidecar/tests/test_personenfrage.py sidecar/tests/test_person_retrieval_repair.py
```

Die breite Dateiliste liegt in `suite-files.json`; Logs sind komprimiert beigefügt. `probe.py` bewahrt die ausgeführte lokale Probe mit ihren ursprünglichen Maschinenpfaden; für Wiederholung die Wurzeln auf neue getrennte Testdaten setzen und wie im gemessenen Lauf einen mit `env -i` geleerten Kindprozess verwenden (nur PATH, tatsächliches HOME, LANG und TMPDIR weiterreichen). So erbt die Probe keine Anbieterzugänge aus der aufrufenden Shell. Ein synthetischer Teststand ist keine Freigabe aller echten Postfächer.

## Getrennte Konzeptarbeit

[Skills und Modellrollen](../../architecture/2026-10-30-skills-und-modellrollen.md) hält die weitere Idee und aktuelle offizielle Modellkarten fest. Keine automatische Skill-Erzeugung, kein Modellwechsel und keine neue Audioanbindung in dieser Reparatur.

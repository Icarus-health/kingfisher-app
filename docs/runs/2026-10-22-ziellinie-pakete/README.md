# Fassung 1.0.27: Pakete der Ziellinie

Stand 22.10.2026. Zielversion 1.0.27. Ausschließlich synthetische Daten (Messlatte-Welt,
IMAP-, CalDAV- und Modell-Attrappen); kein echtes Postfach, kein bezahlter Modellaufruf,
kein Swift-Übersetzer in dieser Umgebung. Die Abnahme am Mac steht aus.

## Inhalt und Reihenfolge

| Schritt | PR | Paket | Protokoll |
|---|---|---|---|
| 1 | #86 | B1 Gesendete Mails einlesen (eigene Zusagen) | [2026-10-20-gesendete-mails](../2026-10-20-gesendete-mails/README.md) |
| 2 | #87 | B2 „Was brauche ich morgen?“ ohne Modell | [2026-10-20-kommendes](../2026-10-20-kommendes/README.md) |
| 3 | #88 | A Neue Mails in der Cloud einordnen; Ziellinie `65-ziellinie.md` | [2026-10-20-cloud-einordnung](../2026-10-20-cloud-einordnung/README.md) |
| 4 | #89 | B6 Aufgaben folgen der Post (Migration 4 der Aufgaben) | [2026-10-21-aufgaben-post](../2026-10-21-aufgaben-post/README.md) |
| 5 | #90 | B5 Stilprofil aus eigenen gesendeten Mails | [2026-10-21-stilprofil](../2026-10-21-stilprofil/README.md) |
| 6 | #91 | B4 „Neue Akte?“ (Migration 24 der Episoden) | [2026-10-21-neue-akte](../2026-10-21-neue-akte/README.md) |
| 7 | #92 | B3 Mitteilungen auf dem Mac | [2026-10-22-mitteilungen](../2026-10-22-mitteilungen/README.md) |

#88 enthält #86, #89 enthält #86 und #88, #91 enthält #89, #92 enthält alle vorigen. Konflikte
zwischen den Paketen (Importe, Logbuch-Arten, Migrationsversionen, Schalterliste, „nur lesen“ in der
Wegezeit) wurden vorab in den jeweils späteren PR gelöst; die Reihenfolge ist lokal konfliktfrei
nachgestellt. Gemergt wird mit „Create a merge commit“.

## Prüfungen je Paket

Jedes Paket: Tests zuerst rot, dann grün; Sabotageproben (Zusicherung absichtlich gebrochen,
passender Test wird rot); volle Backend-Suite; Oberflächentests, `tsc`, Produktionsbau; Browserprobe
in echtem Chromium mit Attrappen. Zahlen aus den Paketprotokollen; vom Hauptfaden je Paket
unabhängig nachgeprüft (gezielte Tests erneut gelaufen, Browserbilder gesichtet, Kernlogik gelesen).

| Paket | Volle Suite (Paketstand) | Sabotageproben | Nachprüfung | Browser |
|---|---|---|---|---|
| B1 #86 | 7.758 bestanden, 2 fehlgeschlagen (eigener Zitatfehler behoben; ein lastabhängiger Cloud-Test) | 16, alle gefangen | 189 bestanden | Knopf, 503 mit Grund, Nachtragen, Stand; 1280/390 px |
| B2 #87 | 7.804 bestanden, 1 lastabhängig | 13, alle gefangen (2 Testlücken geschlossen) | 310 bestanden; Messlatte Belege 128 → 130 | Antwort mit Quelle, 1280/390 px |
| A #88 | 7.752 bestanden, 0 fehlgeschlagen | 12, alle gefangen (2 Testlücken geschlossen) | 198 bestanden | Schalter aus/ohne Zugang/an/aus, 1280/390 px |
| B6 #89 | 7.782 bestanden, 0 fehlgeschlagen | 15, alle gefangen (1 Testlücke geschlossen) | 129 + 118 bestanden | Erledigt-Zeile, Rückgängig, Vorschlag, Akte, Tageslage |
| B5 #90 | 7.776 bestanden, 0 fehlgeschlagen | 13, alle gefangen (1 Testlücke geschlossen) | 59 bestanden; 10.003 Episoden in 66 ms | Vorschlag, Belege, Entwurf mit Ton, Kreis |
| B4 #91 | 7.755 bestanden, 1 lastabhängig | 14, alle gefangen | 182 + 186 bestanden; Messlatte Akten 5/5 | Vorschlag, Anlegen, Zurücknehmen, Heute |
| B3 #92 | siehe Gesamtstand | 13, alle gefangen | 145 bestanden (1 übersprungen ohne `swiftc`) | Schalter, Uhrzeit, Erlaubnis-Hinweis, 1280/390 px |

Der lastabhängige Test ist `test_cloud_memory.py::test_bulk_accepts_101_sources_after_pilot_and_uses_larger_budget`
(Wartefrist von 5 s auf einen Faden unter parallelen Arbeitern); er besteht allein und auf dem
Gesamtstand, kein Paket berührt `cloud_memory`.

## Gesamtstand

Geprüft wurde der Baum von #92, der alle sieben Pakete enthält (Code-Stand `877fb78`; dieser
Release-Branch ändert danach nur VERSION, die Fassungsnotiz, den Einstieg und dieses Protokoll).

* Volle Backend-Suite (Python 3.13, vier Arbeiter): **7.962 bestanden, 0 fehlgeschlagen**, 3 übersprungen, 26 Unterfälle, 13:32 min.
* Oberfläche: `tsc` ohne Fehler, **793 von 793** Oberflächentests, Produktionsbau erfolgreich.
* Swift (Mitteilungen) hier nicht übersetzt; #92 läuft deshalb mit CI (`mac-app.yml`).

## Grenzen und offene Abnahme

* Nur synthetische Daten. Nicht geprüft: echte Postfächer und Gesendet-Ordner echter Anbieter, ein
  echter Aufruf an Anthropic (Format wie das am 19.10. bezahlt geprüfte Mailpaket), die Mac-App.
* Einmalig nach dem Update: Migration 4 (Aufgaben) und 24 (Episoden) legen je eine Tabelle an; keine
  bestehende Zeile ändert sich. Der erste Durchlauf von „Aufgaben folgen der Post“ setzt nur den Stand.
* Abnahme am Mac (Paket C, `65-ziellinie.md`): Gesendet nachtragen und „Was habe ich zugesagt?“ fragen;
  „Was brauche ich morgen?“; Cloud-Einordnung einschalten und eine neue Mail eingeordnet sehen (Kosten
  etwa 3 Cent je Mail); eine Mail zu einer Aufgabe senden; Ton-Vorschlag übernehmen; „Neue Akte?“;
  Mitteilungen einschalten, Erlaubnis geben, morgens die Mitteilung sehen. Danach eine Woche Alltag
  gegen die fünf Sätze der Ziellinie.

# Gedächtniskern: stabile Alltagsfassung

> Ausführung: Root setzt die Auswahlkorrektur um, abgegrenzte Agenten prüfen Aufnahme und Antwortdarstellung; unabhängiger Gesamt- und Paketreview vor der autorisierten GitHub-/Mac-Auslieferung. Der Nutzer hat diese drei Schritte samt Auslieferung ausdrücklich freigegeben.

**Ziel:** Der vorhandene Kern nimmt Originale dauerhaft und fortlaufend auf, findet ihre Belege und berücksichtigt Änderungen/Absagen, ohne daraus unbelegte Personen-, Zeit- oder Sachzuordnungen zu machen.

**Architektur:** Originale und bestehende abgeleitete Stores erhalten. Enge Absicherungen in der vorhandenen Quellenauswahl und Satzdarstellung, keine neue Gedächtnisengine, keine neuen Produktfunktionen oder Modelle.

**Technik:** bestehendes Python/SQLite-/React-/Mac-Paket, Qwen9B lokal, bge-m3 lokal. Ausgangscode f75ccad; installiert preview.6940953.

**Spec:** Drei vom Nutzer freigegebene Schritte; konkret reproduzierter Auswahlfehler im Bericht docs/runs/2026-10-12-hindsight-comparison/README.md.

## Grenzen und Abnahme

- Persönliche Originale, Korrekturen, Zugänge, Modelle, Kalenderauswahl und bestätigte Aufgaben bewahren; vor Installationswechsel kalte Sicherung mit Wiederherstellungsprüfung.
- Keine Cloud, keine neuen Funktionen, keine automatische Aktivierung des großen persönlichen Imports, keine pauschale Daten-/Imagebereinigung.
- Getrennte Nachweise: 10k mechanische Lebenszyklusprüfung mit deterministischem Testanbieter beweist keine LLM-Qualität; reale lokale Modellfälle beweisen keine Vollständigkeit eines persönlichen Gesamtarchivs.
- Keine Antwort darf in den festgelegten Prüffällen unbekannte Zeiten/Identitäten erfinden, einen relevanten Widerruf unterschlagen oder entzogene Belege weiterverwenden. Rückfrage oder Originalzitate sind zulässige sichere Rückfälle, keine als Erfolg kaschierte fehlende Antwort.
- Unbekannte Information, gleiche Namen, andere Vorgänge, historische statt heutige Quelle, abgebrochene Aufnahme, neue Fassung und alter Gesprächsverlauf sind feste Gegenfälle.

## Aufgabe 1: Aktuellen Stand absichern

Dateien: working_memory_answers.py, akten.py und zugehörige bestehende Module nur bei nachgewiesenem Fehler; satzantwort.py; neue/erweiterte Tests für aktuelle Auswahl und test_partial_answer_source_loss.py.

- [x] Reproduzierte rohe Auswahl s04+s05 ohne vorhandenes s06 festhalten; Akten-/Vorgangsanker im tatsächlichen Produktweg prüfen.
- [x] Rote Gegenfälle für verlorenen Widerruf und ausgelassene ausgewählte Originale in frischer sowie gespeicherter Satzantwort.
- [x] Minimal korrigieren: explizit verlinkte Änderungen nicht durch Modell-Auslassungen verlieren, keine Beziehungen aus bloßer Wortähnlichkeit behaupten; ansonsten nachvollziehbare Unsicherheit.
- [x] Gegenfälle für andere Menschen/Vorgänge und negierte Stornierung; betroffene Tests grün und unabhängiger Diffreview.

## Aufgabe 2: Aufnahme und fortlaufenden Bestand nachweisen

Dateien: scripts/probe_memory_core_lifecycle.py, scripts/test_probe_memory_core_lifecycle.py; Laufzeitdateien nur nach roter belegter Fehlerprobe.

- [x] Mindestens 10.000 künstliche Originale durch tatsächlichen Store/Worker verarbeiten, alle IDs und Originaltexte gegen Sollbestand prüfen.
- [x] Prozess-/Store-Neustart, Transportfehler, Warteschlangen-Backpressure, Wiederholung, gezielter Retry und lange Quelle prüfen.
- [x] Neue Quellen und neue Fassung einschließlich source-head und abgeleiteter Suche prüfen; keine doppelten Originale oder verwaisten Treffer.
- [x] Bestanden-/offen-/fehlerhaft-Zahlen müssen dem wirklichen Bestand entsprechen; Ergebnisse und Grenzen speichern.

## Aufgabe 3: Abruf und Auslieferung abnehmen

Dateien: vorhandene E2E-Probes plus enger Prüfläufer für echte Modellaufnahme und Original-/Status-Sollwerte; docs/runs/2026-10-12-memory-core-stable/.

- [ ] Festen künstlichen Quellen-/Fragenkatalog vor Lauf einfrieren; tatsächliche lokale Einordnung und Agent-/Gesprächsroute seriell prüfen.
- [ ] Quelle, Erfassungszeit, ausgewählte Belege, Status und Antwortinhalt getrennt bewerten. Keine reine Auswahlquote als semantische Richtigkeit verkaufen.
- [ ] Quellenentzug und spätere Änderung im gespeicherten Verlauf, fehlende Angaben und Rückfragen end-to-end prüfen.
- [ ] Vollständige bestehende Backend-Prüfung sowie UI-/Build-/Assetchecks; feste Codeversion unabhängig prüfen. Fehlgeschlagene Erstläufe nicht verschweigen.
- [ ] GitHub-Branch/PR und Paket auf denselben geprüften Commit binden. Keine unnötigen Actions-Neustarts bei bekanntem Minutenblock.
- [ ] Fresh backup/restore, Paket-/Signatur-/Hashprüfung, autorisierter persönlicher Wechsel; Daten und Konfiguration unverändert, frischer Appstart und echter Abruf mit Originalvergleich.
- [ ] Abschlussbericht unterscheidet lokale Tests, GitHub-Stand, installierte Version und tatsächliche Fensterabnahme. Kein Anspruch auf mathematische Fehlerfreiheit oder mehrtägigen Nutzerbeweis.

## Laufprotokoll

- 12.10.: Reproduzierte Auswahl s06 vorhanden aber nicht gewählt; unabhängige Darstellungprüfung reproduziert zusätzlich Verlust einer ausgewählten neueren Quelle bei null verworfenen Sätzen.
- 12.10.: Nutzerfreigabe deckt Umsetzung und geprüfte GitHub-/Mac-Auslieferung ab; keine erneute Planfreigabe erforderlich.

- 12.10.: Unabhängiger Review ergänzte historische Heute-Bezugsfrage, getrennte Aufgaben, Negation/Kontrast und allgemeine Kategorien. Konservative Gegenstandsprüfung und ausdrücklich vermutete Beziehungen mit Originalrückfall sind abgesichert; keine kategorischen Programminferenzen mehr. Letzte enge kombinierte Prüfungen: 221 und 122 bestanden, sechs unabhängige zusätzliche Gegenproben bestanden.

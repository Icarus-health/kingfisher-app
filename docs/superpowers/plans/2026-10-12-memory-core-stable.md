# Gedächtniskern: stabile Alltagsfassung

> Ausführung: Root setzt die Auswahlkorrektur um, abgegrenzte Agenten prüfen Aufnahme und Antwortdarstellung; unabhängiger Gesamt- und Paketreview vor der autorisierten GitHub-/Mac-Auslieferung. Der Nutzer hat diese drei Schritte samt Auslieferung ausdrücklich freigegeben.

**Ziel:** Der vorhandene Kern nimmt Originale dauerhaft und fortlaufend auf, findet ihre Belege und berücksichtigt Änderungen/Absagen, ohne daraus unbelegte Personen-, Zeit- oder Sachzuordnungen zu machen.

**Architektur:** Originale und bestehende abgeleitete Stores erhalten. Enge Absicherungen in der vorhandenen Quellenauswahl und Satzdarstellung, keine neue Gedächtnisengine, keine neuen Produktfunktionen oder Modelle.

**Technik:** bestehendes Python/SQLite-/React-/Mac-Paket, Qwen9B lokal, bge-m3 lokal. Ausgangscode f75ccad; abschließend geprüfte Runtime `3721bc2c470ffe570df50327f2c7126a7fe10ba3`; tatsächliche synthetische Modellbelege bleiben an ihren Laufstand e9a968f gebunden. 1.0.7 ist nach kanonischer Deployment-Reparatur lokal installiert und der konkrete native Ablauf einschließlich Quellenentzug und Neustart abgenommen; GitHub-Version 1.0.7 und öffentliche Auslieferungs-/Updatewege sind geprüft.

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

- [x] Festen künstlichen Quellen-/Fragenkatalog vor Lauf einfrieren; tatsächliche lokale Einordnung und Agent-/Gesprächsroute seriell prüfen.
- [x] Quelle, Erfassungszeit, ausgewählte Belege, Status und Antwortinhalt getrennt bewerten. Keine reine Auswahlquote als semantische Richtigkeit verkaufen. Bekannte Klinik-Rubrikabweichung bleibt ausgewiesen.
- [x] Quellenentzug und spätere Änderung im gespeicherten Verlauf, fehlende Angaben und Rückfragen end-to-end prüfen. Finaler inkrementeller Wiederholungslauf auf e9a968f bestanden; vorheriger Embedding-Aufwärmfehler dokumentiert.
- [x] Vollständige bestehende Backend-Prüfung sowie UI-/Build-/Assetchecks; feste Codeversion unabhängig prüfen. Fehlgeschlagene Erstläufe nicht verschweigen.
- [x] GitHub-Branch/PR und Paket auf dieselbe geprüfte Runtime binden. Keine unnötigen Actions-Neustarts bei bekanntem Minutenblock.
- [x] Kalte Sicherung und Wiederherstellbarkeits-/Paket-/Signatur-/Hashprüfung, autorisierter persönlicher Wechsel; maßgebliche Daten unverändert, Konfiguration nur Image-Selektor angepasst, frischer Appstart, echter Abruf mit Originalvergleich, Quellenentzug und Neustart geprüft.
- [x] Abschlussbericht unterscheidet lokale Tests, GitHub-Stand, installierte Version und tatsächliche Fensterabnahme. Kein Anspruch auf mathematische Fehlerfreiheit oder mehrtägigen Nutzerbeweis.

## Laufprotokoll

- 12.10.: Reproduzierte Auswahl s06 vorhanden aber nicht gewählt; unabhängige Darstellungprüfung reproduziert zusätzlich Verlust einer ausgewählten neueren Quelle bei null verworfenen Sätzen.
- 12.10.: Nutzerfreigabe deckt Umsetzung und geprüfte GitHub-/Mac-Auslieferung ab; keine erneute Planfreigabe erforderlich.

- 12.10.: Unabhängiger Review ergänzte historische Heute-Bezugsfrage, getrennte Aufgaben, Negation/Kontrast und allgemeine Kategorien. Konservative Gegenstandsprüfung und ausdrücklich vermutete Beziehungen mit Originalrückfall sind abgesichert; keine kategorischen Programminferenzen mehr. Letzte enge kombinierte Prüfungen: 221 und 122 bestanden, sechs unabhängige zusätzliche Gegenproben bestanden.
- 12.10.: Kandidat 5007716 wurde wegen der tatsächlichen unvollständigen Alex-Winter-Antwort nicht ausgeliefert; Rohantwort und negative Bewertung bleiben erhalten. Dokumenten-Namensguard einschließlich Negation, Adresswechsel, Kontextqualifizierung, Kleinschreibung und gespeicherter Altantwort ist abgesichert.
- 12.10.: Runtime e9a968f: 20 künstliche Originale tatsächlich lokal eingeordnet, alle 15 festen API-Antworten unabhängig inhaltlich geprüft, zusätzliche kleingeschriebene Namenfragen bestanden. Drei Satzantworten, acht Originalberichte, drei Klärungen und ein unbekannter Fakt; keine allgemeine Genauigkeitsgarantie. Klinikfall zeigt weiterhin zwei korrekte Originale ohne Rubrik-Rückfrage.
- 12.10.: Kanonischer finaler Backend-Lauf: 6414 bestanden, 1 übersprungen, 26 Subtests bestanden; weitere Testbereiche 575 bestanden, 1 übersprungen. Unveränderte UI: 573 Tests und Build bestanden. Log-Hashes sind im finalen Nachweis gespeichert.
- 12.10.: Quellenentzug/Wiederöffnung und Nachlieferung auf e9a968f bestanden. Erster Nachlieferungsversuch scheiterte beim Embedding-Aufwärmen mit 30-Sekunden-ReadTimeout; Wiederholung nach Bereitschaftsprüfung ohne Runtime-Änderung bestanden. Koordinator meldet lokale 1.0.7-Installation nach kalter Sicherung und unverändertem maßgeblichem Daten-/Konfigurationsbestand. Finale native Fensterabnahme und GitHub-Veröffentlichung bleiben offen.

- 12.10.: Tatsächliches Macfenster reproduzierte freien Chat trotz ausdrücklichem lokalem Gedächtnissuchauftrag. Enger Routingfix 3721bc2: 42 feste Fälle, 328 betroffene Prüfungen grün; ausgeschalteter Fix 13 erwartete Fehlschläge/29 grün. Unabhängiger Zwischenreview 188 grün, anschließend finite Sachfrage-Eingrenzung final geprüft. Keine neue Suchengine, Schreibaktion oder Cloudfreigabe.
- 12.10.: Erster finaler Volltest ohne lokale Socket-Rechte bei 53 Prozent abgebrochen; Diagnose zeigt lokale HTTP-PermissionError, nicht als bestanden verbucht. Unveränderte Runtime mit Socket-Rechten vollständig grün: 6456 bestanden, 1 übersprungen, 2 Warnungen, 26 Subtests, 992,47 Sekunden. Rohlogs/Hashes erhalten.
- 12.10.: Koordinator meldet erneut gesicherte 17 Datenbanken und 14 unveränderte maßgebliche Tabellen beim finalen Paketwechsel. Native Image-Tag-Vertragsprüfung verlangte kanonische Deployment-Reparatur bei unveränderter Runtime/Release.swift; finale Fensterabnahme und GitHub noch offen. Bereits berichtete persönliche Mail- und synthetische Datei-/Abrufprobe nur mit öffentlichen Booleschen Ergebnissen und Zeiten dokumentiert, keine privaten Rohdaten.

- 12.10.: Kanonische Deployment-Reparatur bestanden, Runtime3721bc2/natives Bundle unverändert; nur Image-Selektor geändert, 14 maßgebliche Tabellen gleich. Tatsächlicher kombinierter Fensterabruf korrekt (46 Sekunden kalt) und angeklickter Originalbeleg deckungsgleich. Quellenausschluss sperrt alte Antwort sofort, frischer Abruf ohne Farbe mit Hinweis auf zwei ausstehende Quellen; ignoriertes Original erhalten und Aufnahme weiter pausiert. Neustart-/Altverlaufsprüfung noch offen. Öffentlicher Nachweis enthält keine privaten IDs, Texte, Pfade oder Backuphashes.

- 12.10.: Finale native Fensterabnahme nach kanonischer Reparatur bestanden: kombinierter Abruf, geklicktes Original, Quellenausschluss und frischer Abruf sowie bestätigtes Prozessende/Neustart mit gesperrtem Altverlauf. Farbe und Quellenlink kommen nicht zurück; Original bleibt erhalten. Dokumentpicker menschlich unterstützt, nur eine Quelle gezielt lokal eingeordnet, Gesamtaufnahme weiter pausiert. Beobachtete kalte Abrufe ungefähr 45–54 Sekunden; keine Gesamtbewertung privater Daten. Router-Pfadprüfung der 15 e9-Katalogfragen bestätigt keine neue Ausnahme; Modelllauf bleibt e9 gebunden. GitHub-Veröffentlichung noch offen.

- 12.10.: PR55/56/54/46 übernommen; Veröffentlichungsstand f7dae379 und Tag v1.0.7 haben exakt den dokumentierten f679-Tree (späterer Docsnachtrag verändert den Tag nicht), gegenüber Runtime3721 nur 13 Docsdateien. Einmaliger Release38260423499 vollständig grün; öffentliches DMG byteweise geprüft, ARM64-Image 273 Python-/112 UI-Dateien bytegleich. Manifest HTTP200 und installierte API-Updateprüfung aktuell1.0.7, Gesamtaufnahme pausiert. Kein erneuter öffentlicher DMG-Fenstertest behauptet (DiskManagement/ScreenCaptureKit nicht verfügbar); frühere native Abnahme bleibt belegt. Publikationsnachweise bereinigt gespeichert, keine persönlichen Quellen oder Konfiguration hochgeladen.

# Abschlussregression: Ursachen getrennt, keine Produkt- oder Teständerung

Stand: 01.11.2026. Bezug: Root `c0e6265f6c20120974f445539fce6a8960b0745a`,
Log `/private/tmp/kf-memory-1.0.37-final-diagnostics-20261101.log`.
Eigener Branch bleibt unverändert auf `7165da562e763aac9533f788d2cf0c1c2f13a29b`.
Keine privaten Dateien, realen Modelle, Netzaufrufe, Rootmutationen oder komplette Suite.

## 1. Anzahl und Reichweite

Die 49 Logfehler zerfallen in 23 Socket-Aufbaufehler (9 Configure-Fälle und
14 Contract-Fälle einschließlich 9 Subtests), 3 Mail-Qualitätsfälle und
23 Messlatte-Fälle. Die Socket-PermissionErrors sind nicht Teil dieser Diagnose.
Die übrigen 26 Fehler haben mehrere Ursachen; sie dürfen nicht pauschal als
veraltete Erwartungen oder als ein gemeinsamer Produktdefekt behandelt werden.

Die wenigen Gegenproben nutzen ausschließlich synthetische Mini-Welt/Katalogdaten.
Die drei seit dem eigenen Stand abweichenden Produktmodule wurden unverändert
aus dem Root-Commit per `git show` in einen isolierten Pythonprozess geladen;
alle übrigen betroffenen Produkt-/Messlatten-/Qualitätsdateien sind identisch.
Kein Produktfile, Anbieter, Assertion, Welt, Frage oder Golden wurde bearbeitet.

## 2. Echter Nutzbarkeitsverlust: Header-only statt Originalbericht

Die eigene API-Gegenprobe wählt die richtige unveränderte Quelle `mainz-003`.
Ohne Satzregel meldet der Skriptanbieter `unklar`. Root rendert im Status
`working_reports` nur Unsicherheit, Titel und Quellenzeit; das vorhandene Datum
26. Oktober fehlt. Die unveränderte Qualitätsfrage wird korrekt als `falsch`
bewertet. Derselbe Sourcepfad mit einer vollständigen vorhandenen Originaleinheit
liefert das erwartete Datum und die Bewertung `richtig`; Source und Golden sind
identisch geblieben.

Damit ist keine Quellen-/Indexvernichtung belegt, aber ein wirklicher Verlust
nutzbarer Information in der gerenderten Rückfallantwort. Die alte Vollanzeige
und der aktuelle Header-only-Vertrag sind in diesem Punkt funktional verschieden.
Der unabhängige Gegenreview berichtet zusätzlich verlorene Vorbehalte/Negationen
und inkonsistentes Verhalten frischer gegenüber älteren gespeicherten Antworten
(`/private/tmp/kf_header_only_diagnostic_20261101.py` und `.log`; nicht hier erneut
mit zusätzlichen Proben ausgeführt).

**Priorität:** Root stellt vollständige, frisch erneut gebundene ORIGINAL-Berichte
im reports-Rückfall wieder her; progressive Anzeige gehört in die UI. Das ist
keine nachträgliche Freigabe einer verworfenen Formulierung. Satz-/Original-ID-/
JA-/Vorbehalts-/Frischegates bleiben unverändert. Bis Root diese Wiederherstellung
gezielt geprüft hat: keine Anpassung der betroffenen Assertions oder Anbieter.
Viele Vollzitat-Erwartungen können damit ohne Oracleänderung wieder sinnvoll sein.

## 3. Unabhängiger echter Anbieter-Vertragsbruch

`messlatte/skript.py`, `WeltSkript.complete_json`, greift im Satzzweig auf
`b['text']` zu. Ein Original-ID-Auftrag enthält `originalsaetze`; der Produktcode
entfernt `text` ausdrücklich. Der direkte Gegenversuch mit diesem tatsächlichen
Eingangsformat ergibt exakt `KeyError('text')`, bevor der Fake antwortet. Dies ist
weder ein Beweis fehlender Quelleninformation noch ein Satz-/Prüfmodellurteil.
Ein restaurierter Vollrückfall kann den Fehler lediglich erneut verdecken.

Getrennt davon gibt `messlatte/tests/skriptmodell.py` ohne passende Satzregel
absichtlich `unklar` aus. Solche Tests prüfen bisher häufig den Quellenrückfall,
auch wenn ihr Titel eine erfolgreiche Satzgenerierung suggeriert. Das alleinige
Antwortschema `saetze` ist nicht grundsätzlich verboten: Der Produktleser hat
weiter einen streng geprüften Legacy-Textpfad. Problematisch sind der fehlende
Eingangsleser für Originaleinheiten und unvollständige Textkandidaten.

Eine weitere isolierte Kontrolle reproduziert die als sorgfältig bezeichnete
Mainz-Absatzfixture: Sie erzeugt einen ganzen Absatz, der nicht aus vollständigen
globalen Originaleinheiten besteht. Das erste Tor verwirft ihn wegen fehlender
vollständiger sichtbarer Original-Personenbindung (genau 1 Verwerfung; keine
Original-IDs angeboten). Der alte Vollzitat-Rückfall ließ die erwarteten Fakten
anschließend trotzdem erscheinen. Dieser Test belegte deshalb bisher nicht
zuverlässig, dass seine Satzgenerierung akzeptiert wurde. Keine Guardlockerung
ist daraus abzuleiten; die eigene vollständige Literal-Gegenkontrolle besteht.

**Kleinster späterer Vorschlag, noch nicht umgesetzt:** WeltSkript muss den
angebotenen Datenvertrag lesen können (Originaleinheiten statt blindem `text`).
Positive Original-ID-Fälle sollen nur vorhandene vollständige IDs auswählen;
gezielt fehlerhafte freie Kandidaten müssen als negative Gatekontrollen erhalten
bleiben. Ein direkter Protokolltest und ein Nachweis tatsächlich akzeptierter
Satzstruktur verhindern, dass Vollrückfälle einen kaputten Fake erneut kaschieren.
Erst nach Roots reports-Wiederherstellung entscheiden, welche Fälle noch betroffen
sind. Keine Fragen/Goldens/erwarteten Fakten entfernen oder auf unknown ändern.

## 4. Mail-Qualität: Inhalt und technischer Erfolg getrennt

Die tatsächlichen Pipeline-Gegenproben für Embedding-Identitätsfehler und
Satzmodellfehler reproduzieren die Logbefunde: richtige Quelle `m05`, unveränderte
Originale, Status korrekt, aber `required_text=False`, `technical_status=failed`
und `pipeline_complete=False`. Bei der Identitätsprobe bleibt die beobachtete
semantische Abdeckung `unavailable`; beim Satzfehler bleibt der Modellfehler
explizit verzeichnet. Der Query-Fehlerfall hat im Log dieselbe fehlgeschlagene
required_text-Assertion; er wurde nicht redundant erneut ausgeführt.

Der Fake der beiden semantischen Tests liefert nach Klassifikation und Auswahl
keine gültige Satzantwort (`{"items":[]}`). Der dritte Test provoziert ausdrücklich
einen ProviderError genau im Satzschritt. Der heutige Header-only-Rückfall kann
unter diesen Voraussetzungen keinen hilfreichen Vollzitat-Erfolg begründen.
Diese beobachtete Qualitätslücke darf nicht durch Weglassen der Pflichttexte oder
Ändern der erwarteten Frage auf unknown verschwinden.

Nach Wiederherstellung eines vollständigen ORIGINAL-Berichts darf die inhaltliche
Fragebewertung wieder bestehen, wenn der tatsächliche Bericht die unveränderten
Pflichtinformationen samt Vorbehalten trägt. **Der provozierte technische Fehler
muss trotzdem failed und pipeline_complete weiterhin False bleiben.** Ein
hilfreicher Quellenbericht ist keine erfolgreiche verworfene Modellformulierung.
Dafür müssen die vorhandenen separaten technischen Prüfungen erhalten bleiben.

## Belege und nächste Grenze

- `/private/tmp/kf-final-harness-probes-20261101.py`: reproduzierbare reine
  Diagnose, keine Anbieterreparatur; JSON gleichen Namens enthält die Ergebnisse.
- `/private/tmp/kf-final-paragraph-probe-20261101.json`: exaktes primäres
  Verwerfungsurteil der Absatzfixture.
- Eigener Worktree und Root-Dateien bleiben unverändert. Kein Commit/Push.

Nächster sinnvoller Schritt ist allein Roots gezielte Original-Rückfallprüfung.
Danach lässt sich der gesonderte WeltSkript-Protokollfehler minimal beheben und
nur die verbleibenden Diagnosefälle nachprüfen. Keine pauschale Aktualisierung
von Vollzitatassertionen vor dieser Produktkorrektur.

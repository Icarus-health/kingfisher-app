# Messlatte-Testadapter an verlustfreie Modellprojektion angepasst

31.10.2026. Final eingefroren; ausschließlich `messlatte/tests/skriptmodell.py` und neue `messlatte/tests/test_skriptmodell_projection.py`. Keine Produktdatei, Originalquelle, Skriptregel oder Bewertungserwartung geändert. Keine Modelle, privaten Daten oder Netzaufrufe; echte synthetische Aufnahme/Konversations-TestClient-Probe.

**Finale gemeinsame Messlatte: 314 bestanden, 1 bestehende Warnung, 47,20s.** Getrennter Lauf von audit_procedural_integration einschließlich des elften neuen Protokollfalls: `/private/tmp/kf-messlatte-all-final-test-alignment-20261031.log`; Ergebnis hier gelesen. Eigene abschließende eng betroffene Gruppen: 29 bestanden, 2,42s, `/private/tmp/kf-messlatte-long-marker-green-20261031.txt`. Diffprüfung sauber.

## Ursache

Vollständige Diagnosebelege: `/private/tmp/kf-messlatte-missing-deadline-diagnosis-20261031.md` und `kf-messlatte-selection-transport-diagnosis-20261031.{py,json,log}`.

Miniweltaufnahme vollständig: 15/15 eingeordnet, keine übersprungene/offene Quelle. Tatsächliche Auswahlpayloads enthalten die vollständigen Texte zu Umsatzsteuervoranmeldung und Klinikum-Entscheidung. Ihr context besteht bei kurzen Quellen aus `[siehe text]`, der auf text derselben Zeile verweist. Das Test-Skriptmodell suchte ausschließlich im wörtlichen context und meldete fälschlich no_relevant_sources. Nur `$copy` auflösen half nicht. Den eigenen Kurzverweis korrekt interpretieren stellte working_reports mit Originalbelegen rechnung-004 bzw. mainz-008 wieder her. Keine empty-topic-/Beleg-Routingregression in diesen Fällen.

## Finaler enger Adaptervertrag

Der Auswahlzweig benutzt den vorhandenen strikten `absatzauswahl.modell_zeilen_entpacken`. Danach:

- Ein alleinstehender exakter `[siehe text]`- oder `[Fundstelle: siehe text]`-Feldwert wird auf text der **aktuellen** Zeile zurückgeführt.
- Ein eingebetteter exakter `[Fundstelle: siehe text]`-Marker in einem langen context wird nur an dieser Stelle durch text der aktuellen Zeile ersetzt. Der komplette übrige context bleibt erhalten.
- Ein eingebettetes `[siehe text]` wird nicht als Langkontextmarker ausgelegt; dieser eigene Kurzmarker gilt weiter ausschließlich als ganzer Feldwert.
- Beliebige unterschiedliche Kontexte werden nicht durch text ersetzt. Titel/Absender/Projektmetadaten werden nicht durchsuchbar.

Danach unverändert dieselbe bisherige Stichwortsuche, S-ID-Regel und Statusbildung. Kein globaler Textfallback, kein Produkt-/Oraclelockern. Strikter Decoder verhindert Auswahl aus Fremd-/Vorwärts-/Selbst-/Ketten-/feldfremden Verweisen. Lokale Kopien verhindern Eingangsänderung; Kennungen und Reihenfolge bleiben erhalten.

## Eingebetteter Langmarker: Korrektur einer zu engen Kontrollannahme

Root wies darauf hin, dass die erste neue Kontrollassertion einen eingebetteten Fundstellenmarker fälschlich als undurchsichtigen context behandelte. Diese Annahme wurde durch die tatsächliche Produktionsprojektion widerlegt und vor Finalfreeze korrigiert.

Neuer Gegenfall baut ein 2.636 Zeichen langes künstliches Original. `absatzauswahl.fenster` bestimmt die Fundstelle 524:961 mit dem einzigen Vorkommen von NICHT gesendet. `auszug(..., ref=...)` ersetzt diese Fundstelle im langen Kontext durch den Fundstellenmarker. `ergaenzen` fügt die separate Stelle Freigabe fehlt weiterhin hinzu. Die tatsächliche Zeile trägt Originalsnippet in text, langen Auszug in context und lokalen Volltext unverändert als Zeile.volltext.

Vor Fakekorrektur ist der gesuchte Originalinhalt nur im referenzierten Snippet; context enthält Marker, Kopf, zusätzliche negierte Bedingung, Trennstellen und Kürzungsvermerk. Der Fake übersieht den Inhalt. Genaues Markerersetzen stellt ihn wieder her; unabhängige Auswahl nach Freigabe fehlt weiterhin, Fachstelle, Trennmarker und gekürzt belegt zugleich, dass der übrige Kontext erhalten bleibt. Kein freies Zusammenführen unterschiedlicher Texte.

## Rot/Grün

1. Neue anfängliche Protokollgegenfälle zuerst **9 rot, 1 Kontrollfall grün**: `/private/tmp/kf-messlatte-projection-fake-red-20261031.txt`.
2. Nach erster Adapterkorrektur **65 Tests grün in 11,84s** (Protokoll, Antwort, Lokal, Fälle, Bericht/Holdout), `/private/tmp/kf-messlatte-projection-fake-green-20261031.txt`.
3. Root-Nachaudit des eingebetteten Markers: korrigierte Grenze plus tatsächliche auszug/ergaenzen-Zeile zuerst **2 rot, 9 grün**, `/private/tmp/kf-messlatte-long-marker-red-20261031.txt`.
4. Nach präziser Langmarkerauflösung **29 Tests grün in 2,42s**, `/private/tmp/kf-messlatte-long-marker-green-20261031.txt` (11 Protokollfälle, test_antwort, test_antwort_saetze).
5. Finaler gemeinsamer Messlatte-Stand **314 grün in 47,20s**, `/private/tmp/kf-messlatte-all-final-test-alignment-20261031.log`.

Ein vorheriger vollständiger Zwischenlauf nach Kurzmarkerfix hatte 306 grün / 7 fachlich andere Restassertionen (`/private/tmp/kf-messlatte-projection-fake-all-20261031.txt`): sechs Actor-Fixtureannahmen und ein Prosa-Präfix. Diese Dateien wurden getrennt von audit_procedural_integration nach eigener Freigabe abgeglichen, nicht durch den Fakepatch oder eine Produktlockerung. Sie sind im finalen 314er Lauf grün.

## Grenzen

Der Adapter bleibt ein deterministisches Testskript. Wortregeln belegen keine echte Modellrelevanz oder Sprachqualität. Für den reinen Fake-Protokollabgleich sind keine neuen I/J-Inferenzen nötig; Produktcode und Originale unverändert. Eigene zwei Dateien final eingefroren, keine Commits. Keine weiteren Produktions-/Actor-/Oracledateien bearbeitet.

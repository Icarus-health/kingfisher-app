# Native Originalauswahl: Hinweis, eine Nachprüfung und getrennte Quellen

Basis: `7789d7e9881f9a71fac1d5f910fd9b56ce3e17af`. Nur synthetische
MIME-/Storetests und feste Modellattrappen; keine privaten Quellen,
tatsächlichen Modelle, Netzprovider oder Root-Dateien verwendet.

## RED auf der Basis

Der vollständige Pfad liest synthetische DOCX-Anhänge über MIME und `remember`,
erhält ihre nativen Rawzeilen im normalen WMA-Commit als `uncertain`, ruft
`prepare` auf und erreicht den Original-ID-Selektor:

- Eine erste leere Auswahl übersprang die vorhandene einmalige Nachprüfung.
  Die erst im zweiten Versuch vorgeschlagene gültige ID erreichte kein Tor.
- Zwei aktuelle unterschiedliche DOCX enthalten dieselbe vollständige Row
  `Prüfdatum\n18.11.2026\tPrüfstelle`. Beide Quellen wurden ausgewählt;
  die Text-Deduplizierung ließ nur eine davon zum aktiven Prüfer und führte
  anschließend zum Vollständigkeitsrückfall.

Die Dokumente unterscheiden sich in einer eigenen Formularinformation;
sie sind keine vom MIME-Leser bereits entfernten identischen Binärdateien.
Die Raw-Row bleibt in beiden Quellen exakt gleich.

## Enger Schnitt

13 Produktzeilen ergänzt, fünf entfernt, ausschließlich `satzantwort.py`:

1. Nur bei tatsächlich angebotenen nativen Rows erhält der vorhandene
   Original-ID-Auftrag einen Zusatz: Ein vollständiger beschrifteter skalarer
   Felddatensatz ist auch ohne grammatischen Satz eine gültige Originaleinheit.
   Label und erfragte Datumsrolle müssen passen; er erscheint nur wörtlich als
   unbestätigter Quellenbericht. Fehlende/unpassende Angaben nicht auswählen.
2. Die schon vorhandene genau einmalige Nachprüfung benutzt denselben Auftrag
   einschließlich dieses Hinweises und dieselben IDs/Belege. Erst danach führt
   eine weiterhin leere native Auswahl zu Zitaten. Keine neue Schleife,
   Budgeterhöhung oder globale Abwesenheitsbehauptung.
3. Identischer Text bleibt bei verschiedenen Belegsets getrennt, wenn eine der
   betreffenden Einheiten nativ ist. Jede Einheit durchläuft einzeln das aktive
   Tor mit ihrem eigenen unveränderten vollen Rawbeleg. Gleicher Text mit
   gleichem Belegset wird weiter dedupliziert; normale Sätze behalten den
   vorherigen Deduplizierungsvertrag. Es gibt keinen Vertrauensmerge.

Alle bisherigen nativen Provenienz-, Sichtbarkeits-, 400-Zeichen-, Rawbudget-,
Frage-/Vorbehalts-, Quellenfrische- und Entzugsprüfungen bleiben bestehen.
Das allgemeine Originalprompt und dessen Nachprüfungsauftrag bleiben ohne
native Rows exakt gleich. Die Gegenprüfung normaler Sätze erhält weiter
ausschließlich `satz` und `belege`.

## Gezielte Kontrollen

Die elf neuen Fakekontrollen belegen leer→gültige ID→aktive Prüfung mit
Ja/Nein/Unklar; dauerhaft leere Auswahl und fehlendes/falsches Feld mit
höchstens zwei Selektoraufrufen und null Judgecalls; zwei Quellen mit
gleicher Row, zwei getrennte Judgecalls, beide Links und wiederhergestellte
Satzstruktur; Nein/Unklar bei nur einer Quelle führt weiterhin zum gesamten
Zitat-/Unsicherheitsrückfall. Gleiche Row plus gleiche Belege benötigt
weiter nur einen Judgecall. Keine Claims entstehen.

Ein vorhandener Native-Abwesenheitstest erwartet nun genau die genehmigten
zwei statt zuvor einen Selektoraufruf; das Ergebnis bleibt `zitate`.
Der Abschlusslauf umfasst außerdem Native-Index-/Provenienz-/Tabellenfälle,
Original-/Zitat-/Absatz-/Satzprüfungen und die sechs Pflichtkernmodule aus
`CONTRIBUTING.md`: **698 bestanden in 36,06 Sekunden**, eine vorhandene
Starlette/httpx-Deprecation-Warnung. Keine komplette Suite; Diffcheck sauber.
Mit dem vorhandenen Python-3.12-Testvenv und `PYTHONPATH=sidecar:.`:

```sh
python -m pytest -q sidecar/tests/test_docx_native_selection.py \
  sidecar/tests/test_docx_native_rows.py sidecar/tests/test_docx_native_index.py \
  sidecar/tests/test_docx_table_context.py sidecar/tests/test_answer_source_boundaries.py \
  sidecar/tests/test_original_quote_context.py sidecar/tests/test_original_sentence_selection.py \
  sidecar/tests/test_normative_paragraph_context.py sidecar/tests/test_normative_source_binding.py \
  sidecar/tests/test_conditional_report_binding.py sidecar/tests/test_absatzauswahl_saetze.py \
  sidecar/tests/test_satzantwort.py sidecar/tests/test_satzpruefung.py \
  sidecar/tests/test_satzpruefung_modell.py sidecar/tests/test_context.py \
  sidecar/tests/test_egress.py sidecar/tests/test_agent.py sidecar/tests/test_kingfisher.py \
  sidecar/tests/test_claims.py sidecar/tests/test_graph.py
```

Die kontrollierten Attrappen prüfen den tatsächlichen Auftrags- und Gatepfad,
keine reale Modellqualität. Die private Wiederholungsprobe und der unabhängige
Review bleiben Aufgabe des Root-Arbeitsgangs. Kein Push, PR oder Release.

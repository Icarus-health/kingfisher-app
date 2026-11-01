# Testverträge zur progressiven Originaldarstellung

Neuer eigener Worktree: `/private/tmp/kf-original-fallback-tests-20261101`.
Basis exakt `f03f6eb0683288ea79a2978bf4797ab920c6c4b4`;
Branch `fix/original-fallback-test-contracts-20261101`.
Der frühere Worktree auf `4fedcd18abe616e20ff78914c7b431e0a11d7d40` bleibt unverändert.

Nur drei Testdateien geändert: `test_partial_answer_source_loss.py`,
`test_satzantwort.py`, `test_zweites_tor.py`. Kein Produktionscode, keine
Fragen/Miniwelten/Goldens/required_text-Änderung und keine echten Modelle,
Netzaufrufe oder Root-Dateien. Dieser Bericht liegt außerhalb des Git-Patches.

## Nachweis

Die exakt elf Restfälle aus dem Triage-Log scheitern auf der unveränderten
Basis: **11 RED in 1,47 s**. Sie verlangen noch fehlende Originaltexte im API.
Nach der Testvertragskorrektur: **11 GREEN in 1,43 s**.
Abschließender enger Lauf einschließlich Personen-, Zeit-, Negations-, Frische-
und Satzfreigabe-Kontextkontrollen: **34 bestanden in 2,35 s**. Keine komplette Suite.

## Verstärkte Verträge

- Alle ausgewählten Originale erscheinen vollständig und unverändert im
  Quellenbericht; insbesondere bleiben Änderungen, ersetzte Termine und
  mehrfache entscheidende Negationen erhalten. Die frischen Link-IDs stimmen
  exakt mit den ausgewählten Ref-IDs überein.
- Falsche Modellsätze bleiben abwesend. Die bisherigen Gate-, Verworfen-,
  echte-Person-/Zeit-/Negations- und gespeicherten Frischeprüfungen bleiben
  bestehen. Keine freigegebene Satzstruktur entsteht aus dem Originalbericht.
- Die API benennt den Originalbericht ausdrücklich als keine geprüfte
  Zusammenfassung. `project_message` muss `original_fallback=True` frisch
  berechnen, gespeicherte gegenteilige UI-Marker überschreiben und alte
  Satzstruktur entfernen. Das ist die Metadatengrenze zur progressiven UI,
  keine neue Freigabe verworfener Prosa. Claims-Revision bleibt unverändert.
- Umgekehrt erhält wirklich akzeptierte Prosa weiterhin ihre strukturierte
  Satzantwort und keinen übernommenen falschen Original-Fallbackmarker.
  Quellenentzug entfernt Originaltext, Links, Satzstruktur und alten UI-Marker.

## Prompt-Injection und nächster Modellverlauf

Die vorhandene Satzmodell-Payload-Schwärzung bleibt unverändert geprüft.
Die fremde Anweisung steht vollständig nur im markierten Originalbericht,
nie als freigegebene Modellbehauptung oder ausgeführte Handlung.

Die verstärkte Gegenprobe speichert diesen tatsächlichen Bericht mit seiner
`working_answer`-Metadatenstruktur in einem echten ConversationStore. Der
persistierte Assistententext muss der programmatische neutrale Arbeitsstand
sein. `history()` enthält weder fremde Anweisung noch Empfängeradresse.
Ein echter Agent lädt diese History und führt den nächsten normalen Modellaufruf
mit einem adversarialen Fake aus: Bei erreichbarer Kontaktadresse würde er einen
synthetischen Sendetool-Aufruf verlangen. Der tatsächliche Modellinput enthält
weder Adresse noch Anweisung; `used_tools` und Ausführungssensor bleiben leer.
Keine bestätigten SelfModel-Fakten oder Knowledge-Claims entstehen.

Die Gegenprobe schützt deshalb mehr als das bloße Entfernen der früheren
Nicht-im-API-Assertion. Sie prüft Speicherung, Modellkontext und Ausführungsgrenze
separat von der vollständigen lesbaren Originaldarstellung.

## Prüfbereich und Freeze

Verwendet wurde das vorhandene Python-3.12-Testvenv mit `PYTHONPATH=sidecar:.`.
Der enge Lauf umfasst die ganze kleine Partial-Source-Datei, die drei benannten
Satzantwort-Restfälle, Personen-/Original-/Zeit-/Cloud-Gegenfälle und die zwei
benannten Zweites-Tor-Restfälle plus Fehler-/Reopenkontrollen. Kein Fullsuite-
oder echter Modelllauf. Diffcheck sauber; ausschließlich die drei Testdateien
werden committed. Unabhängiger Review und Sabotageprobe folgen beim Root.

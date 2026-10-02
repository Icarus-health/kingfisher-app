# Pilot: abgegrenzte Umsetzung mit günstigerem Modell

Erster Auftrag: GPT-5.6 Luna implementiert einen reinen Transkript-Parser.
Die Hauptinstanz definiert den Vertrag, ergänzt den lokalen Prüfaufruf und
prüft Code sowie Fehlerfälle. Keine persönlichen Daten werden dafür benötigt.

## Wiederverwendbarer Arbeitsauftrag

Implementiere ausschließlich `sidecar/icarus_memory/transcript_import.py` und
`sidecar/tests/test_transcript_import.py`. Keine Abhängigkeiten, Netzwerkzugriffe,
Git-Operationen, Datenbankzugriffe oder Änderungen an anderen Dateien.

API: `parse_transcript(text: str, format: str) -> list[dict]` für TXT, SRT und VTT.
Jedes Segment enthält `text`, `start_ms`, `end_ms`, `speaker`. Unbekannte Zeiten
und Sprecher bleiben `None`. Keine Identitäten aus Text oder Kalender erraten.
TXT ergibt einen Textblock; SRT/VTT erhalten Zeitstempel und mehrzeiligen Text.
Unterstütze BOM und CRLF. VTT-Stimmenmarkierungen dürfen den angegebenen
Sprechernamen liefern; andere Inhalte bleiben inerte Texte. Leere Eingabe
ergibt eine leere Liste. Verwirf ungültige Zeitstempel, umgekehrte Intervalle,
leere Cues, unbekannte Formate und Eingaben über zwei Millionen Zeichen mit
`ValueError`. Beschädigte Cues dürfen nicht stillschweigend verschwinden.
VTT-Metadatenblöcke NOTE/STYLE/REGION dürfen ignoriert werden.

Schreibe Tests für gültige mehrzeilige Exporte sowie beschädigte Eingaben,
Zeitgrenzen, Stimmenmarkierungen und Größenlimit. Berichte ausgeführte Tests
und verbleibende Grenzen. Behaupte keinen vollständigen MacWhisper-Import.

## Lokale Vorschau

Mit der Python-Umgebung des installierten Sidecars vom Repository aus:
`python3 scripts/preview_transcript.py /pfad/export.vtt`.
Der Aufruf liest ausschließlich die angegebene UTF-8-Datei und gibt JSON aus.
Er speichert keine Episoden, ruft kein Modell auf und versendet keine Daten.
Ausgabe kann persönliche Inhalte enthalten; nicht in öffentliche PRs kopieren.

## Abgrenzung und nächste Integration

Dies ist ein geprüfter Baustein, noch keine Funktion in der Oberfläche.
Ordnerüberwachung, MacWhisper-Steuerung, Quellenhistorie, Import-Deduplizierung,
Kalenderzuordnung und Bestätigung von Sprecheridentitäten folgen separat.
Ein tatsächlich exportiertes, freigegebenes Beispiel muss vor der vollständigen
MacWhisper-Abnahme geprüft werden. Proprietäre Whisper-/JSON-Formate werden
nicht aus Vermutungen implementiert.

## Bewertung der Ersparnis

Ergebnis des ersten Reviews: Korrekturen bei TXT-Zeitwerten, VTT-Kopfzeilen,
gemischten Sprecherabschnitten und fehlenden Cue-Trennzeilen. Die Hauptinstanz
ergänzte den CLI-Aufruf sowie Prozess- und Grenzfalltests. Abschließend bestanden
20 gezielte Tests mit Python 3.12. Es fand kein echter MacWhisper-Exportlauf
und kein vollständiger Anwendungstest statt; die laufende App wurde nicht verändert.

Dokumentiere Umsetzung, Review-Korrekturen und Prüfergebnisse. Für einen
belastbaren Kostenvergleich fehlen beim ersten Versuch ein gleichwertiger
Vergleichslauf und vollständig zugeordnete Verbrauchswerte. Daher noch keine
prozentuale Kostenersparnis behaupten. Kleine akzeptierte Änderungen zählen
mehr als erzeugte Codezeilen.

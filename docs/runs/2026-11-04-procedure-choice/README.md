# P2: bestätigte Abläufe einmalig auswählen

## Verhalten

Passen mehrere bestätigte persönliche Abläufe, fragen Gespräch und lokaler
Mailentwurf vor der Modellarbeit nach. Die Auswahl bietet alle passenden Titel,
eine ausdrückliche Grundverfahren-Option und Abbrechen. Sie gilt nur für den
ursprünglichen Auftrag; kein Ablauf wird dadurch dauerhaft bevorzugt.

Der Server verwahrt den Auftrag hinter einer zufälligen Einmalkennung für
höchstens zehn Minuten (höchstens 64 offene Kennungen). Er bindet die Auswahl an
Gespräch beziehungsweise Mail, Anbieter, Einstellungen, aktuelle Quellen und
Ablauffassungen. Ein anderer Auftrag, Anbieterwechsel, Freigabeentzug, veraltete
Quelle oder wiederholte Verwendung scheitert ohne Modellaufruf. Die Auswahl
selbst ist keine neue Wissensaussage. Der wartende Auftrag löst auch keine
Hintergrundeinordnung aus. Die ursprüngliche Quellenbindung bleibt bei einem
zwischenzeitlichen Wechsel der Gedächtnisrevision erhalten.

## Prüfung

- Store-, Agent- und HTTP-Tests für Konflikt, eindeutige Wahl, Grundverfahren,
  Abbruchgrenzen, Ablauf-/Quellenentzug, Anbieter-/Freigabewechsel, fremde
  Gespräche, Replay und Ablaufzeit; jeweils mit künstlichen Daten.
- 263 betroffene Backendtests bestanden. Bestehende Gesprächsaufnahme, Rücknahme, Aktionen, Gedächtnisrouten,
  Quellenverlauf und Mailkontext-/Empfängergrenzen einbezogen.
- 38 betroffene Oberflächentests bestanden; Typprüfung und Produktionsbuild
  bestanden. Bestehender Hinweis auf große JavaScript-Pakete unverändert.
- Unabhängiges Review fand zwei wichtige Lücken: Quellenbindung nach einem
  zurückgesetzten Modellverlauf und vorzeitige Hintergrundeinordnung. Beide
  Fehler wurden zunächst durch fehlschlagende Tests reproduziert, anschließend
  korrigiert und unabhängig gegengeprüft. Eine zusätzlich gefundene Änderung
  der lokalen Modellfreigabe wird ebenfalls vor Auswahl geprüft.

## Echte Mac-Bedienprüfung am 04.11.2026

Getrennte „Kingfisher Gedächtnistest.app“ auf Port 8893, ausschließlich künstliche
Daten und lokales Antwortdouble. Die bestehende Alltagsinstanz war unberührt.

1. Chatauftrag „Schreibe eine Mail für die Zunft.“: zwei passende Titel und
   Grundverfahren sichtbar; kein Antwortaufruf vor Auswahl.
2. Zusätzlichen, noch ungesendeten Text eingetragen, Details geöffnet,
   Abbrechen und „Auftrag erneut prüfen“ benutzt: Eingabe erhalten.
3. „Offizielle Zunftmail“ gewählt: genau ein Aufruf mit ursprünglichem Auftrag
   und nur dem ausgewählten Ablauf; keine dauerhafte Auswahl.
4. Künstliche Mail geöffnet, Antwortauftrag eingegeben: gleiche Auswahl,
   Abbrechen erhält den Auftrag. „Kurze Zunftmail“ erzeugt einen Vorschlag mit
   diesem Ablauf. Das Antwortfeld wird erst mit ausdrücklicher Übernahme gefüllt.
5. Während der Prüfung wurde zusätzlich ein künstlicher Mailentwurf ohne
   eingegebenen Auftrag angefordert. Dieser normale Pfad verwendet keinen
   persönlichen Ablauf. Insgesamt drei Aufrufe des Antwortdoubles, keine echten
   Modell- oder Cloudaufrufe und kein Versand.

Die zuvor geöffnete Test-App hatte noch eine alte JavaScript-Fassung im Speicher;
ein normaler Neustart der Test-App lud die neue Oberfläche. Diese Prüfung belegt
Bedienung und Übergaben, keine reale Qwen-Qualität, vollständige Barrierefreiheit
oder Nutzungswoche. Eine neue Fassung wird hiermit noch nicht als veröffentlicht
oder auf der Alltagsinstanz installiert behauptet. Großimport bleibt pausiert.

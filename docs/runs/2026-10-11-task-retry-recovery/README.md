# Aufgaben nach unterbrochener Speicherung wieder aufnehmen

Geprüfter Code: `b7cd321dd2c081b48c5fcb42fd3ae37184554326`, auf dem bisherigen manuellen Wiederholungsfix `cde97a7`.

Ein erfolgreicher Auftrag mit verlorener Antwort behält nach Formularschließen oder Seitenneuladen seine zufällige Kennung. Manuelle Aufgaben und Zielschritte haben getrennte Schlüssel; der Browserspeicher enthält keine Titel, Notizen oder Fristen. Wiederholung mit denselben Eingaben liefert die vorhandene Aufgabe samt späteren Änderungen. Andere Eingaben bleiben ein sichtbarer Konflikt. „Neuen Speicherauftrag vorbereiten“ setzt eine ausdrückliche Prüfung voraus und sendet selbst nichts. Nicht verfügbarer lokaler Speicher verhindert den Versand.

## Prüfungen

- 573 UI-Tests in 99 verfolgten Testdateien; abschließend 18 betroffene Tests sowie Typ-, Build-, Asset- und Anführungszeichenprüfung bestanden. Backend unverändert gegenüber dem zuvor mit 42 betroffenen Backendtests geprüften `cde97a7`.
- Vier tatsächliche vollständige Browserabläufe mit künstlichem SQLite-Bestand auf Quell-UI und zusätzlich auf dem eingefrorenen Build: verlorene Antwort/Neuladen, Schließen/geänderte Eingabe/bewusster neuer Auftrag, Zielschritt/Neuladen, lokaler Speicherfehler. Desktop 1200×850 und Mobil 390×844, keine Laufzeitfehler oder horizontale Überbreite. Erwartete künstliche Abbruch-/409-Konsolenmeldungen dokumentiert.
- Unabhängiger enger Quellreview fand einen Zurücksetzfehler nach Lesefehlern. Zwei neue Gegenfälle vorher rot, nach Bindung an den beobachteten Speicherstand grün; finaler Review ohne weiteren Blocker.
- Tatsächliches Dienstimage netzlos mit ausschließlich kurzlebigen künstlichen Daten ausgeführt: Exitcode 0 und abschließender manueller Wiederholungsmarker. Beide manuellen Routen, dauerhafter Aufgaben-/Ziel-Neustart, Erhalt nachbearbeiteter/erledigter Aufgaben, Konflikte und geschlossenes Ziel geprüft. Weitere vorhandene Paketabläufe eingeschlossen; keine Modell-Inferenz oder persönliche Qualitätsabnahme.

## Paket und Stand

`1.0.6-preview.b7cd321`, Image `sha256:44c6f9fa0c6d0a8852ac7dfdbdad221def3e237a61acd5bb1485ca8e8f04db27`.
Git-Archiv SHA-256 `54985d265894c0db73f2eea596421e803aa07478394cf8e48dbc087c7d7b2438`.
Alle 272 Python- und 112 UI-Dateien byteweise an das Archiv beziehungsweise den daraus gebauten Build gebunden. Die dokumentierten Staging-Ausnahmen betreffen VERSION und den isolierten Overlay-Bau; keine Quell-Versionsänderung. EpisodeStore bleibt v22, TaskStore v3.

ARM-App mit sechs Dateien streng/tief ad hoc signiert, nicht notarisiert. DMG nur lesend eingehängt, identische Bündeldateien nachgewiesen, wieder ausgehängt. DMG SHA-256 `dd82c485c719a760b7a06bbec786175a9b78f8a88ebda35bd15e407d37d4d2f3`. Separates Prüfpaket außerhalb Git; keine Registryveröffentlichung.

Das Paket ist inzwischen **als App-Dateien und gesundes Backend persönlich installiert**: `preview.b7cd321`. Persönlicher Import bleibt pausiert. Die bestehenden nativen Fensterprozesse wurden noch nicht neu gestartet; dies bestätigt keine neue WebKit-Sitzung. Native Fenster-/WebKit- und persönliche Kalenderabnahme offen: Computersteuerung meldet den Mac weiterhin gesperrt, obwohl der Nutzer den Kalenderdialog bestätigt hat. Keine Umgehung durch anderen UI-Zugriff.

## Grenzen und korrigierte Prüfaufbauten

Der persönliche Einfenster-Prototyp bietet keine globale Mehrfenster-Atomarität: separate localStorage-Operationen sind keine Transaktion. Ein Neuladen rekonstruiert keine Entwurfsfelder; die Oberfläche erklärt dies ausdrücklich. Weder perfekt fehlerfreies Gedächtnis noch persönliche Modellqualität wird damit behauptet.

Die erste Paketprobe las wegen fehlendem stdin-Schalter keinen Code ein und wurde nicht als Nachweis verwendet. Danach hielt die unveränderte Speicherreserve die zu kleine künstliche tmpfs-Partition korrekt an; der Prüflauf erhielt 1 GiB virtuelle Reserve bei weiter 1 GiB Arbeitsspeicherlimit. Der neue Neustart-Prüffall benötigte zudem einen dauerhaften synthetischen Selbstmodellspeicher statt eines neuen leeren MemoryBackend. Erst der abschließende vollständige Lauf mit dauerhaftem künstlichem Ziel, Exitcode 0 und letztem manuellen Marker gilt als grün. Produktcode wurde dafür nicht geändert.

## Tatsächliche Installation

Frische vollständige Sicherung: 167 Dateien, zehn Verzeichnisse, 333.347.678 Bytes; Wiederherstellung byteweise sowie Eigentümer, Rechte, Zeitstempel und erweiterte Attribute identisch. Alle 17 SQLite-Kopien bestehen die Integritätsprüfung. Archive, Konfiguration und Dateimanifeste verbleiben privat auf dem Mac; nur Inhaltsfingerabdrücke und technische Summen stehen im Repository.

Die neue Version öffnete anschließend eine getrennte netzlose Sicherungskopie; 17 Schemas/Versionen und sämtliche 47 Tabellen im Episoden-, Aufgaben- und Selbstmodellspeicher unverändert, Headerindex gegen Original-Tags geprüft. Im tatsächlichen Dienst dieselben Erhaltungsprüfungen und die sieben zusätzlichen Kerntabellen bestanden; unverändertes Volume und Anbieter-/Modellumgebung. Exakt nur der Image-Selektor der geschützten Konfiguration geändert. Native sechs Dateien signiert und identisch zum DMG; tatsächlich laufende 272 Python- und 112 UI-Dateien stimmen mit dem geprüften Paket überein. Dienst gesund, globale Aufnahme pausiert. Kein neuer Modelllauf, Cloudauftrag, Fenster- oder Kalender-API-Test.

Unabhängiger enger Installerreview samt eigenen AST-/SQLite-Gegenproben ohne konkreten Blocker. Root prüfte zusätzlich neun SQLite-Erhaltungsfälle, vier Staging- und drei Rückwegfälle und die echte Compose-Konfiguration mit künstlichen Werten. Der Rückweg überschreibt keine neuen Eingaben und startet nach fehlgeschlagenem Wechsel keinen alten Dienst auf ungeprüften Daten. Wartungssperre ist beratend; Mehrfenster-/globale OS-Exklusivität nicht behauptet.

Eine zusätzliche Nachprüfung erwartete zunächst fälschlich die kurze öffentliche Gesundheitsantwort bei angemeldeter Anfrage; sie wurde auf das richtige öffentliche Lebenszeichen korrigiert. Die abschließende tatsächliche Dateien-/Versions-/Gesundheits-/Pausenprüfung bestand mit Exitcode 0. Native neue Sitzung und persönliche Kalender-/Gedächtnisqualität bleiben offen.

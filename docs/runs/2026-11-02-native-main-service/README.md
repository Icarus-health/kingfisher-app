# Hauptdienst bei Start, Update und Rückkehr auswählen

Die optionale Modulausführung darf die bestehende Mac-App nicht verändern, bevor ihre Laufzeit gesondert freigegeben ist. Diese kleine Vorbereitung beschränkt deshalb nur vorhandene Vorgänge auf den Compose-Hauptdienst `kingfisher`:

- Die Suche nach dem App-Container verlangt Projekt **und** Dienst. Ein zusätzlicher Worker darf nicht als App für die Übernahme vorhandener Zugangsschlüssel gewählt werden.
- Start und Update laden ausdrücklich das Hauptbild und starten nur `kingfisher` mit `--no-deps`.
- Die Rückkehr zur vorherigen Fassung behält Offline-Wiederherstellung, Reihenfolge und Prüfung der genauen Bildkennung bei. Nur der abschließende Start wird eingeschränkt.

## Prüfung

Die neuen Tests übersetzen den tatsächlichen Swift-Code für Docker, Start, Update und die vorhandene Umgebungsdatei mit vollständig künstlichen Befehls- und HTTP-Grenzen. Sie starten kein Docker und lesen keine persönlichen Schlüssel oder App-Dateien.

- Unveränderter Ausgangsstand: **7 Fehler, 3 bestanden**. Mit der Korrektur: **10 bestanden**. Ein unabhängiger Prüfer wiederholte die zehn Tests erfolgreich und fand keinen bestätigten Blocker.
- Vollständige kopierte Mac-Testreihe: **102 bestanden, 1 übersprungen**, ein weiterer Test scheiterte an der lokalen Freigabe für seinen künstlichen HTTP-Port. Genau dieser unveränderte Test bestand beim erlaubten lokalen Wiederholungslauf. Die gesamte erste Reihe wird deshalb nicht als fehlerfrei ausgegeben.
- Vollständige ARM-App übersetzt, ohne Warnungen. Das lokale Intel-Linken scheitert an fehlenden x86_64-Kompatibilitätsbibliotheken; der unveränderte Ausgangsstand scheitert identisch. Der universelle Release-Build bleibt eine gesonderte Prüfung.
- Patch-Wiedergabe und Vorher-/Nachher-Prüfsummen aller fünf Dateien stimmen überein. Der Mac-Workflow führt die neuen Vertragstests künftig aus.
- Integration in der tatsächlichen Arbeitskopie: die zehn neuen nativen Tests bestehen. Der zusätzliche bestehende Mac-Vertragstestlauf bestand mit 32 Tests und einer Auslassung; sein Logik-Übersetzungstest scheiterte am nicht beschreibbaren Standardcache. Genau dieser Test bestand unverändert mit einem getrennten beschreibbaren Compiler-Cache. Es wurde keine Programmlogik für diese Umgebungsfehler geändert.

```sh
python -m pytest macos/test_main_service.py -q
```

## Grenzen

Noch sind keine zusätzlichen Dienste eingetragen, keine Laufzeit installiert und keine persönlichen Module aktiviert. Die Korrektur stoppt keinen bereits laufenden Worker und widerruft keine Arbeitsfreigaben. Diese Grenzen müssen die künftige Laufzeitsteuerung vor Sicherung, Update und Wiederherstellung ausdrücklich durchsetzen. Während einer Rückkehr zur alten Fassung muss der Worker angehalten bleiben; danach darf nur eine kompatible Laufzeit separat starten.

Die neue native Logik gehört zur neuen Mac-App-Hülle. Ein Backend-Update allein ersetzt eine bereits installierte ältere Hülle nicht. Installation, tatsächliche Fensterbedienung und bestehende macOS-Berechtigungen sind weiterhin getrennt zu prüfen.

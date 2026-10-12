# Personen-Validierung: geprüftes Paket und persönliche Installation

11. Oktober 2026. App-Dateien und laufendes Backend auf `1.0.6-preview.45cb1c8`, Code `45cb1c8272a1335a49b7a3adc1d59fa3c542e9c5`. Draft [#54](https://github.com/Icarus-health/kingfisher-app/pull/54); kein Main-Merge oder veröffentlichter Registry-Release. Der vorhandene native Prozess wurde nicht neu gestartet. Der Mac war bei der Computersteuerung erneut gesperrt; neuer Fenster-/Alltagsnachweis bleibt offen.

## Änderung und Paketbindung

Die [Pronomen-Korrektur](../2026-10-11-person-pronoun-hints/README.md) verhindert, dass einzelne deutsche Pronomen als Personenhinweise vorgeschlagen oder aus alten Spans angezeigt werden. Originale und alte Speicherzeilen bleiben erhalten. Die enge Ausnahme für aktuelle persönliche Mailkontakte löst keine allgemeine Identitätszuordnung. 32 neue Gegen-/Kontrollfälle und 242 betroffene Tests bestanden im vorangegangenen Code-Lauf; keine nachträgliche Aufwertung der früheren Modellqualität.

Backend gebaut auf dem exakt vorher installierten Image `sha256:6172ec0c0a63075d9a7481c9c934657f698a6f3d8764e063cdbccdf9a21daa63`, mit genau `memory_categories.py` und Versionsmetadaten als Laufzeitänderung. UI-/Native-Quellen gegenüber `3690733` unverändert. Die 112 UI-Dateien des vorher geprüften Pakets wurden byteweise geprüft und wiederverwendet; kein erneuter UI-Build oder neuer Rendernachweis behauptet. ARM-Native-Bundle frisch mit Versionsmetadaten gebaut.

- `package-freeze.json` bindet 270 Python- und 112 UI-Dateien sowie unveränderte Lizenzdateien.
- Isolierte echte Image-Probe ohne Netzwerk oder persönliches Volume: alle Datei-/Versionsprüfungen, vorhandene künstliche Paketabläufe, Antwortrollen-Verbindung und Speichergates bestanden. Zusätzlich echte Kategorie-Validierung mit künstlichem Provider: „Ihre“ entfernt, echter Name und anderes Thema erhalten; nach Wiederöffnung alte Pronomenzeile weiter in SQLite, nur abgeleitete Anzeige bereinigt. Keine echte Modellinferenz oder Cloud-Anfrage.
- DMG schreibgeschützt eingebunden: sechs native Dateien exakt passend, strenge tiefe Codesign-Prüfung bestanden. Ad-hoc signiert, nicht notarisiert.
- DMG-SHA256: `1900b2df4fceee1a53b12984f8e21c7b48a9829b992efa89de614b466f521c01`.
- Installiertes Backend-Image: `sha256:d65a5a4b205496e222ffab16b1137b9734718e46837a0b848c12819bc2a4de3f`.

## Unterbrechungsschutz vor dem Wechsel

Unabhängiges lesendes Review des konkreten Installers fand eine Lücke: Unterbrechung direkt nach dem Verschieben der alten App-Inhalte konnte vor dem Setzen eines Erfolgsflags den Rückweg überspringen. Gegenprobe am tatsächlichen obersten Ausnahmehandler zuerst rot; anschließend Rückweg anhand des vorhandenen verschobenen Verzeichnisses statt des Flags korrigiert.

Künstliche Unterbrechungen vor/nach Umbenennung und vorhandene Fehlerfälle bestanden danach. Der Rückweg erhält neu hinzugekommene Daten, stoppt den neuen Dienst und stellt App-Konfiguration/-Dateien wieder her; startet die alte Laufzeit nicht automatisch. Abschließendes enges unabhängiges Review ohne konkreten verbleibenden Blocker; Reviewer führte Skripte nicht aus. Keine Zusicherung gegen Stromausfall oder SIGKILL. `install.py`, `backup.py` und Hilfen sind Belege dieser einmaligen lokalen Ausführung, kein allgemeiner Updater.

## Tatsächlicher persönlicher Wechsel

Vor dem Wechsel frische vollständige kalte Sicherung und separate Wiederherstellung: 148 Dateien, neun Verzeichnisse, 281.322.188 Bytes. Byteweise Inhalte, Verzeichniseinträge, Besitzer/Rechte, Nanosekunden-Änderungszeiten und erweiterte Attribute übereinstimmend. Integritätsprüfungen aller 17 SQLite-Datenbanken bestanden. Private Sicherung und Konfiguration bleiben außerhalb Git.

Nach dem Wechsel: sieben vollständig geprüfte Kerntabellen unverändert; Schemas und `user_version` aller 17 Datenbanken unverändert. Gleiches Datenvolume, nur Image-Auswahl in der Host-Konfiguration geändert. Installierte native Dateien stimmen mit dem kanonischen DMG überein; Dienst gesund und Version frisch über die authentifizierte Produkt-API bestätigt.

Frischer Status: Kalenderfreigabe `granted`, drei ausgewählt, Helfer online, kein Kalenderfehler. `background_paused:true`, Kalenderübernahme ins Gedächtnis weiterhin aus. Rund 1,39 GiB Docker-Reserve ist keine Qualifikation für den vollständigen Mailbestand. Kein persönlicher Modellrollenwechsel, Modellstart, Cloudaufruf oder großer Import.

## Offen

Neustart und Bedienprüfung des neuen nativen Fensters, persönliche Einordnungs-/Abrufqualität und zusammenhängender Tagesablauf bleiben offen. Das konfigurierte Gemma12B-Antwortmodell fehlt weiterhin; vorhandenes Qwen9B wurde bislang nur getrennt mit künstlichen Quellen für den Frageweg geprüft. Große Mailaufnahme bleibt ausdrücklich pausiert. Dieses Paket verbessert einen belegten Personenfehler, macht das Gedächtnis nicht allgemein fehlerfrei.

`verification.json`, `preinstall-status.json` und `postinstall-status.json` enthalten bereinigte aktuelle Nachweise; komprimierte Logs bewahren Build, Paketprobe und rote/finale Unterbrechungsprüfung. Private Daten und Zugangswerte sind nicht Teil dieser Lieferung.

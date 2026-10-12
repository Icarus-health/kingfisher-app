# Bestätigte Kalenderfreigabe und begrenzte Anzeige

11. Oktober 2026. Code `bfe555e`. Im bestehenden Draft #54; **noch nicht als neues Paket gebaut oder persönlich installiert**. Installierter persönlicher Backendstand weiter `1.0.6-preview.45cb1c8`. Kein Main-Merge, Registry-Publish, CI-Neustart oder Modellwechsel.

## Freigabe und tatsächlicher Fehler

Nach Nutzerbestätigung frisch authentifiziert und lesend geprüft: Mac-Kalenderfreigabe `granted`, Helfer online, drei ausgewählt, keine Quellfehler, 490 Einträge im Mac-Snapshot. Hintergrund und großer Import bleiben pausiert; Kalender-Gedächtnisübernahme bleibt aus. Keine Termine geändert. Das native Fenster konnte die Computersteuerung weiterhin nicht erreichen, da sie den Mac als gesperrt meldete.

Der Sieben-Tage-Abruf lieferte 986 Einträge. Das bereits verbundene iCalendar-Abo liefert absichtlich seine ganze Datei für die Gedächtnisaufnahme; Anzeige und Dashboard vertrauten aber auf eine Filterung durch den Leser. Die lesende Zählprobe fand 978 Einträge außerhalb des Zeitfensters und zwei ohne Ende. Die frühe einfache Diagnose konnte diese zwei ohne Ende nicht als Intervalle prüfen; **fehlendes Ende bedeutet nicht automatisch ungültiger Beginn**. Der endgültige Filter behandelt solche zeitgebundenen Einträge als Punkte am bekannten Beginn.

Der vorgeschlagene reine Filter wurde zusätzlich im Arbeitsspeicher auf einen erneuten lesenden persönlichen Abruf angewendet: **986 Originaleinträge → sechs passende Anzeigeeinträge, null unbekannte Datumsangaben; Original-Liste unverändert 986**. Das ist ein Probevergleich mit echten Zeitdaten, keine Änderung der installierten API oder Beurteilung privater Termintexte. Das öffentlich dokumentierte Ergebnis enthält ausschließlich Zahlen; keine Termintexte, Kennungen oder Zugangswerte.

## Korrektur und unabhängiger Review

Gemeinsamer reiner Filter für Kalenderansicht (Standardfenster, ausdrücklicher Zeitraum, Jahr) und Dashboard. Überschneidungen bleiben sichtbar, obere Grenze ist exklusiv. Das Dashboard behält seinen Zeitraum von jetzt minus 48 Stunden bis jetzt plus `days`, damit Nachbereitung erhalten bleibt. Rohleser, ganze ICS-Datei, Gedächtnisaufnahme, Originalobjekte und `source_copies` werden nicht verändert.

Ganztags-DATE-Werte werden für den Vergleich als lokale Datumsintervalle in der ausdrücklich angefragten Zone behandelt, auch wenn der ICS-Leser UTC-Mitternacht speichert. Zeitgebundene Werte und Fenstergrenzen werden vor Reihenfolge/Gleichheit/Überschneidung in UTC verglichen. Dadurch bleibt ein gültiger Termin während der doppelten Stunde nach Sommerzeitende erhalten. Die Ausgabeform der Originaltermine ändert sich nicht.

Unklare Daten werden gezählt und als `warnings` angezeigt, getrennt von tatsächlichen Quellenfehlern in `errors`. Ein fehlender Termin bleibt deshalb 404 statt wegen fremder unklarer Daten als Quellenfehler 503 zu erscheinen. Dashboard-Warnungen bleiben ebenso von `calendar.error` getrennt; sie erzeugen keinen falschen Kalender-Teilfehler im Morgenbriefing. In der Kalenderansicht erscheint der Hinweis als Status und verschwindet nach einem aktualisierten erfolgreichen Abruf.

Enges unabhängiges statisches Review fand den DST-`fold`-Gegenfall und die anfängliche Dashboard-Status-Unstimmigkeit; beide vor Commit korrigiert und mit zuerst fehlschlagenden HTTP-Tests abgesichert. Final kein verbleibender Status-Blocker gemeldet. Reviewer führte die Tests nicht selbst aus.

## Ausgeführte Prüfung und Grenzen

- Neun neue HTTP-Testfälle. Zuerst fünf Fälle gegen die ungefilterte Anzeige fehlschlagend beobachtet; zusätzliche Ganztags-, zwei DST-Fold- und Warnungsgegenfälle vor ihrer jeweiligen Korrektur rot. Endgültiger gezielter Lauf: **150/150** Backendtests bestanden, einschließlich Vorbereitung, Spiegelkopien, Nachbereitung, Mehrkalender und Gedächtnisaufnahme.
- **551/551** UI-Tests, Typprüfung, Produktionsbuild und Assetvertrag bestanden. Bekannte Warnungen zur großen Bundle-Datei und Starlette-Testclient bleiben.
- Echte React-Kalenderkomponente mit künstlichen, vollständig abgefangenen HTTP-Antworten auf `127.0.0.1:18763`: Hinweis sichtbar, Ansichtwechsel und Aktualisieren geprüft, alter Hinweis nach neuem Ergebnis weg; null Schreibanfragen, keine Konsolen-/Seitenfehler oder Framework-Overlays. Screenshots Desktop 1100×850 und 390×844 geprüft; auf dem vollständigen App-CSS kein horizontaler Überlauf. Browser-Plugin nicht verfügbar, vorhandenes Playwright für diese getrennte künstliche Oberfläche verwendet. Kein Umgehen der gesperrten persönlichen Mac-Oberfläche.
- Treiberkorrekturen transparent: Testdokument anfangs ohne UTF-8-Metadaten; anfänglicher schmaler Screenshot ohne die beiden globalen Abschluss-CSS-Dateien zeigte Überlauf. Testdokument korrigiert, vollständige tatsächliche CSS-Reihenfolge importiert und endgültiger Check erfolgreich wiederholt. Keine entsprechende Produkt-CSS-Änderung behauptet.
- Ein breiter Lauf von insgesamt 424 Testdateien (versionierte Tests plus neue Regression) wurde gestartet und abgebrochen; er zeigte Fehler und **ist kein bestandener Gesamtlauf**. Unter anderem verweigert die Sandbox den kontrollierten Testservern Socket-Bindung. `test_eine_erkennung_fuer_google_microsoft_und_den_rest` in `test_anbieter_erkennen.py` wurde separat mit `PermissionError: Operation not permitted` an `127.0.0.1` reproduziert. Danach dieselben Diensttestdateien `test_anbieter_erkennen.py`, `test_device_profile.py`, `test_fassung.py` mit lokaler Testserverfreigabe: **104/104 bestanden**. Nicht pauschal alle Fehler des abgebrochenen breiten Laufs als identisch aufgeklärt behauptet; vollständige Prüfung des endgültigen Standes bleibt offen.

Der zusätzliche Testbrowser ist beendet, Vite-Testserver regulär gestoppt. Der breite Python-Testprozess ist nicht mehr vorhanden. Keine persönliche Inferenz, Rollenänderung, Modellgewichte oder Cloudanfrage. Das zuvor gebaute Paket `d092006` enthält diese spätere Kalenderkorrektur noch nicht; nächster Paketbau muss den neuen Code einbeziehen. Persönliche sichtbare End-to-End-Abnahme bleibt offen.

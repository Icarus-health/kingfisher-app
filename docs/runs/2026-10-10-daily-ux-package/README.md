# Kingfisher: Alltagspaket 1.0.6-preview.6979131

Dieser lokale Prüfkandidat enthält die Korrektur der Gedächtnis-Einordnung, die Projektübersicht, Health-Filter mit Verlaufskurve sowie den direkten Gesprächsimport und mehrzeiligen Gesprächsentwurf. Er ist nicht auf dem persönlichen Mac installiert und kein öffentliches Release.

## Gebaut und geprüft

- Unveränderlicher Code: `69791314c69c0092cd81e69952c2d0a1fdb21985`, direkt per Git-Archiv ohne ungetrackte Synchronisationskopien.
- UI erneut aus diesem Archiv gebaut: TypeScript/Vite bestanden, identische CSS-/JS-Dateinamen wie bei der Funktionsprüfung.
- Lokales Backend-Image: `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.6979131`, ID `sha256:066cf82ddc4a8217b9d8c4f660f84cdacf0ca9315da287cb9384710bfaccd458`.
- Beide Laufzeitschichten ersetzt: alle 269 Python-Dateien und 112 UI-Dateien im Image byteweise mit dem neuen Build verglichen. Die UI wurde ausdrücklich mit übernommen.
- Backend-Probe in einem flüchtigen, schreibgeschützten Container mit frischen tmpfs-Verzeichnissen, ohne Netzwerk, Host-Daten, Modelle oder Cloudaufrufe bestanden.
- Neue Paketabläufe geprüft: Transkriptvorschau speichert keine Quelle; ausdrücklicher Import erhält den Text und die Projektzuordnung. Themenkorrektur bleibt nach erneutem Öffnen erhalten, eine alte Revision wird abgelehnt, Original bleibt unverändert. Projektzahlen berücksichtigen 209 Aufgaben und unterscheiden eigene Arbeit, Warten, erledigt und verworfen; Lesen ändert keinen Verlauf. Ein Health-Filter findet ältere kg-Werte hinter 105 anderen Messungen, verwechselt mV/MV nicht und zeigt zurückgezogene Quellen nicht weiter an.
- Frühere künstliche Paketproben für Quellenbindung, Aufgaben, Kalender-Routen, Arbeitsgedächtnis, Learning, World Facts und v20→v21 bleiben im gebauten Image bestanden. Das sind keine echten Modell- oder Kalenderfreigabetests.
- Native ARM64-App übersetzt, ad hoc signiert. Dauerhaft kopiertes DMG schreibgeschützt eingebunden: strenge tiefe Signaturprüfung bestanden, alle sechs enthaltenen App-Dateien stimmen mit dem Buildmanifest überein. Version, Compose-Datei und Update-Speicherprüfung geprüft. Danach ausgehängt, App nicht gestartet.

Funktionsprüfung vor dem Paketbau: 187 betroffene Backendtests, alle 545 UI-Tests und Produktionsbuild bestanden. Zwei unabhängige Reviews hatten einen Fehler bei sehr nahen Health-Zeitpunkten sowie das Verlieren einer ungespeicherten Dateivorschau beim Schließen gefunden. Beide sind mit Regressionstests behoben. Kein erneuter kompletter Backendlauf und keine GitHub-CI-Wiederholung.

## Reproduzierbarer Build und Werkzeuge

Das Backend basiert auf dem bereits lokal vorhandenen Image `sha256:f9caa5537b33403f0d7beff828a20fecd4ee3458d9ac41068e40d1cf1b436a6e`. Docker-Build mit `--network none --pull=false`; neue Python- und UI-Bäume wurden vollständig ersetzt. `package-freeze.json` bindet Code-Archiv und alle Laufzeitdateien.

Der native Build lief mit `KINGFISHER_ARCHITEKTUR=arm64`, der passenden Fassung und getrennten Swift-/Clang-Modulcaches. `iconutil` lehnte dieselben korrekt dimensionierten PNG-Dateien nur in der Sandbox ab; der einzelne identische Aufruf außerhalb war erfolgreich. Der unveränderte Build wurde deshalb ab dem Icon-Schritt fortgesetzt, anschließend signiert und als DMG verpackt. `resume-dmg-build.sh` und Logs zeigen genau diese Fortsetzung. Kein Code-Fix oder Austausch der freigegebenen Grafik war nötig.

## Nutzung und noch offene Abnahme

Dauerhafter lokaler Ordner: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-10-daily-ux-6979131/`.

Das DMG ist der kanonische Installer; keine lose App-Kopie aus einem synchronisierten Ordner verwenden. SHA-256: `af3aab50703a7acafcf0d80b495749068bca433f86c2bf394965b0e13c9d9e1c`.

Das passende Backend-Image ist bisher nur lokal vorhanden, nicht in eine Registry hochgeladen. Das DMG allein ist daher kein allgemein übertragbares Release. ARM64, nicht Intel; ad hoc signiert, nicht notarisiert.

Vor dem persönlichen Update muss ein frisches Backup des bisherigen Datenbestands samt Wiederherstellungsprüfung entstehen. Die v21-Migration ist künstlich geprüft; der alte v20-Stand kann ein migriertes Datenvolume nicht als Rückfallweg lesen. Bestehende Daten und Zugänge werden nicht für einen Neustart gelöscht.

Die echten Mac-Fenster, Kalenderfreigabe, Datei-/Diktatbedienung, Energieverbrauch und persönliche Mail→Gedächtnis→Aufgabe-Abläufe sind noch offen. Die aktuelle Rückmeldung betrifft ausdrücklich die Einordnung einer einzelnen Quelle; sie trainiert kein Modell und erfindet keine allgemeinen Regeln. Keine medizinische Bewertung durch die Health-Kurve, keine automatische Audiodatei-Transkription und keine Behauptung fehlerfreier persönlicher Datenverarbeitung.

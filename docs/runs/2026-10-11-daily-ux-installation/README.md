# Persönliche Installation und native Teilabnahme, 11. Oktober 2026

Das gekoppelte Alltagspaket **1.0.6-preview.6979131** ist tatsächlich auf dem persönlichen Mac installiert und gestartet. Lokale Vorschau aus Draft #54 auf Basis von Draft #46; kein öffentliches Release und keine vollständige persönliche CoS-Abnahme.

## Frische Sicherung und tatsächlicher Wechsel

Nach dem Entsperren wurden alte App und Datenbestand kalt gesichert. Privater Sicherungsordner unter `Library/Application Support/Kingfisher/Sicherungen/`, Zeitkennung `20261011T091952Z`; Konfiguration und alte App-Dateien erhalten. Keine persönlichen Archive, Schlüssel oder Quellentexte im Repository.

- 129 Dateien, acht Verzeichnisse, 229.325.370 Bytes des Datenvolumes.
- Separate Wiederherstellung: Dateiinhalt, Verzeichnisse, UID/GID, Rechte, Nanosekunden-mtime und xattrs identisch. Tatsächlicher Bestand ohne xattrs; frühere künstliche Metadatenprobe ist ein eigener Beleg.
- Alle 17 wiederhergestellten SQLite-Datenbanken bestehen die Integritätsprüfung.
- Migration v20→v21 zuerst auf abgeschotteter Kopie, ohne Netz, als UID/GID 1000 geprüft. Sechs ausgewählte bestehende Tabellen erhalten Zeileninhalt, Spalten und DDL auch nach Wiederöffnung.

Datei-/Verzeichniswiederherstellung, kein Blockgeräteabbild. Rückfall zur alten App erfordert die gesicherte v20-Datenkopie; alte App nicht auf migriertem v21-Volume starten.

Das kanonische DMG aus dem [Paketnachweis](../2026-10-10-daily-ux-package/README.md) erneut per SHA-256 geprüft und schreibgeschützt eingebunden. Alle sechs App-Dateien und strenge tiefe Signaturprüfung stimmen mit dem Manifest überein. Separat bereitgestellt, dann `Contents` gegen die gesicherte alte Fassung ausgetauscht; bestehender App-Pfad und sein Wurzelverzeichnis erhalten.

Host-Konfiguration atomar geändert: ausschließlich Compose-Bildselektor, alle anderen Bytes unverändert, weiterhin 0600. Compose ohne Pull/Build umgestellt, ursprüngliches benanntes Datenvolume erhalten.

- Native App und authentifizierte Backend-Versionsantwort: **1.0.6-preview.6979131**.
- Health und native strenge Signaturprüfung bestanden.
- Laufende Image-ID: `sha256:066cf82ddc4a8217b9d8c4f660f84cdacf0ca9315da287cb9384710bfaccd458`.
- Datenvolume: `kingfisher_kingfisher-data:/data`, unverändert.
- Installationsabbild anschließend ausgeworfen; installierte App läuft unabhängig davon.

Sieben Kerntabellen unmittelbar vor/nach Wechsel und nach nativer Bedienprobe vollständig über sortierte Zeileninhalte verglichen; alle Prüfsummen unverändert:

| Bestand | Erhaltene Zeilen |
|---|---:|
| Originalepisoden | 344 |
| Quellenverweise | 333 |
| Gespräche | 3 |
| Gesprächsnachrichten | 14 |
| Aufgaben | 0 |
| Projekte | 0 |
| Notizen | 0 |

Leere Aufgaben-/Projektbestände beweisen keine bevölkerte persönliche PMO-Bedienkette. Der große Mailimport bleibt über die globale Hintergrundpause angehalten; keine kostenpflichtige Modellanfrage oder neue Cloudfreigabe.

## Im echten App-Fenster beobachtet

- Neues natives Fenster ohne Browseradress-/Favoritenleiste geöffnet; Uhr läuft auf Heute, Gedächtnis, Gesprächen, Aufgaben, Health und Einstellungen weiter.
- Direkte Quellenkorrektur geöffnet und unverändert abgebrochen. Kein persönlicher Kategorien-Speichervorgang behauptet.
- Drei erhaltene Gespräche sichtbar; Quellenzeit/Erfassungszeit getrennt, unbelegte Antworten ausdrücklich gekennzeichnet. Keine neue Nachricht gesendet.
- Health-Seite, Filter und Editor geöffnet und ohne Speicherung geschlossen. Keine eigenen Messangaben vorhanden; keine echte Kurven-/Speicherabnahme.
- Eigene Aufgaben und „Warte auf andere“ zeigen tatsächlichen leeren Bestand; Projektanlage geöffnet und abgebrochen. Keine Testaufgaben/-projekte im persönlichen Bestand.
- Bestehende Mail- und Google-Kalenderzugänge sichtbar erhalten.

## Offene native Nachweise

**Mac-Kalender:** Bereits autorisierte appbezogene Kalenderfreigabe erneuert, kein allgemeiner Datenschutz-Reset. Laufender Prozess aus installiertem App-Pfad. TCC-Logs bestätigen, dass die Anfrage macOS erreicht und in die Aufforderungsphase gelangt. Letzter lesender Status: `not_determined`, Helfer online, drei gespeicherte Auswahlen, `synced_at: null`, null gelieferte Termine, `memory_allowed: false`. Das beweist keine leere Agenda. Nutzer um Bestätigung des Systemdialogs bzw. Meldung eines fehlenden Dialogs gebeten; noch keine Antwort erhalten.

**Dateiaufnahme:** Importbereich und nativer Dateidialog geöffnet. Ausschließlich künstliche TXT-Datei im temporären Verzeichnis und eigenen Testpaketordner markiert; „Öffnen“ blieb deaktiviert. Regulär abgebrochen. Koordinatenversuch zusätzlich mit `noWindowsAvailable`, AX-Ansicht weiterhin erreichbar. Ursache noch nicht eindeutig zwischen App/Dialog und Computersteuerung getrennt; keine native Dateivorschau oder Speicherung behauptet. Breiter Dateilisten-Screenshot von Freigabeprüfung abgelehnt; anschließend nur Ordner mit künstlicher Testdatei verwendet.

**Weitere Grenzen:** Deutsche Diktatqualität, echte Mikrofonfreigabe, Akku-/RAM-Spitzen und persönlicher Mail→Gedächtnis→Aufgabe→Kalender-Arbeitstag offen. Briefing zeigte bei nicht verfügbarer Agenda eine Formulierung ohne vorzubereitenden Termin; daraus keine vollständige Terminlage ableiten. Keine Garantie fehlerfreier Einordnung oder automatischer Modell-Lerntransfer.

Frühere synthetische Prüfungen sind keine neue native Vollabnahme. Kein neuer kompletter Testlauf, kein CI-Neustart, kein Merge nach main. Separater Host-Sicherungsfix `24c5140` im Repository verfügbar, nicht Bestandteil des unveränderten DMG/Backend-Pakets.

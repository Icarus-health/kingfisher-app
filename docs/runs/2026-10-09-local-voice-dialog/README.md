# Lokaler Sprachdialog als vorbereitete Vorschau

Die bestehende Gesprächsoberfläche bekommt lokale Mac-Diktierung und ausdrücklich gestartetes Vorlesen. Diktierte Teiltexte bleiben getrennt vom vorhandenen Entwurf. Ende ergänzt einen prüfbaren Entwurf; Abbruch verwirft ausschließlich den gesprochenen Zusatz. Kein automatisches Senden. Nur ausdrücklich gesendeter Text nutzt den vorhandenen Gesprächsspeicher und dessen gewählte Modellverbindung.

Vorlesen lädt das Gespräch über die vorhandene lokale GET-Route erneut und verlangt dieselbe vollständige Nachrichten-/Quellenprojektion. Strukturierte Sätze werden mit ihren sichtbaren Unsicherheits-/Abdeckungshinweisen gesprochen; versteckter Rohmodelltext und geschlossene Originalzitate bleiben außerhalb der Sprechfassung. Zu lange Antworten werden nicht abgeschnitten. KI-Chat darf aus sein: Vorlesen benötigt kein Modell.

Native Aufnahme erfordert lokale deutsche Apple-Erkennung und erzwingt `requiresOnDeviceRecognition`. Kein Browsermikrofon, Cloudfallback oder Download. Aufnahme höchstens eine Minute, Finalisierung höchstens fünf Sekunden. Berechtigungen erst auf ausdrücklichem Start; Statusabfrage startet keine Aufnahme. Abbruch, Verbergen, Navigation und veraltete Freigaben/Ergebnisse werden abgefangen. Audio wird nicht als Datei oder Quelle gespeichert. Vorlesen nutzt eine installierte deutsche Systemstimme.

## Prüfung und Grenzen

Die unabhängige Prüfung fand und korrigierte Browser-Kompatibilität, Vorlesen ohne KI-Chat und veraltete Fähigkeitsanzeige; siehe `independent-review.md`. Ein zusätzlich reproduzierter Gesprächswechsel-Fehler wurde korrigiert: erst eintreffende Daten des neuen Gesprächs lösen seine eigene lokale Statusprobe aus.

Die nativen Vertragstests verwenden künstliche Recorder-/Freigabe-/Stimmenkomponenten; die Kalender-HTTP-Prüfung einen synthetischen lokalen Server, kein EventKit. Frontendtests prüfen echte Sitzungslogik und Komponenten-/Effekthandler mit deterministischer Hook-Steuerung, ohne native Geräte. Ein erster UI-Gesamtlauf hatte 503 bestandene Fälle und einen bestehenden Systemtext-Vertrag als Fehler; die feste Mac-Beschriftung wurde durch „Lokal diktieren“ ersetzt. Der folgende Gesamtlauf besteht mit 507 Fällen. Warnung zur Vite-Bündelgröße bleibt sichtbar.

Ein erster nativer Testlauf im normalen Checkout scheiterte in drei bestehenden Compiler-/HTTP-Grenzfällen an gesperrtem Compiler-Cache bzw. lokalem Testserver. Drei versehentlich bzw. noch ohne diese Umgebung gestartete Wiederholungen wurden abgebrochen. Der abschließende Lauf verwendet ein sauberes Archiv, expliziten temporären Compiler-Cache und die Freigabe ausschließlich für künstliche Tests. Keine Löschung der vorhandenen Synchronisationskopien.

Kein Zugriff auf Mikrofon, persönliche Kalender oder produktive Daten, keine Modell-/Cloudanfrage. Produktive App nicht ersetzt; Aufnahme, TCC-Dialog, Hörqualität, tatsächliche Darstellung und die drei Kalender bleiben bis zum ausdrücklich später gewünschten Fenstertest offen. Das ist eine vorbereitete Vorschau, kein fertig abgenommener Voice- oder CoS-Nachweis.

## Lieferstand

Code `6f53fd69f6fa0c5c1b569b05e51ea5e0565481d3`, Version **1.0.6-preview.6f53fd6**. Frische native Archivprüfung: **34 bestanden, 1 übersprungen** (Abbruchtest außerhalb macOS). ARM-App/DMG gebaut, tiefe strenge Ad-hoc-Signatur und DMG-Prüfsumme bestätigt; nicht notarisiert, keine Intel-Abnahme. Der saubere Test-Overlay ist bytegleich zum Codearchiv. Vollständige UI-Suite **507 bestanden**, davon 22 Voice-Fälle. Vier echte Controllermutationen werden von den Tests erkannt (alte/verborgene Rückmeldung, fehlende Quellenaktualität, entfernte Unsicherheit); native Mutationsnachweise stammen aus der unveränderten Koordinatorgrundlage.

Gepaartes Backend-/UI-Abbild `sha256:94d37a065ed08d015bb269c47764c99cdf65c110da9190e1e048b2e1605bad03`. Basis und ihre Schichten unverändert; kein Pull/Download. Kurzlebiger Testcontainer ohne Netzwerk, Ports oder Host-/Produktivmounts, mit leeren tmpfs-Daten: sämtliche 268 Python-/112 UI-Dateien stimmen exakt mit dem Manifest überein. Vorhandene synthetische Paketflüsse für Gesundheitsaufnahme/Korrektur/Entzug, Kalenderroute, RAM-Ablehnung und Quellen-/Pause-Metadaten bestehen. UI nur statisch ausgeliefert, nicht als App bedient. Backendlogik nicht geändert, kein neuer vollständiger Backend-Lauf behauptet.

Dauerhafte Ablage: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-local-voice-6f53fd6/` mit App, DMG, gepinntem Quellarchiv, Manifesten und tatsächlichem stdin-Paketprüfer. Die vorherige Vorschau und produktive Installation bleiben erhalten. Das Abbild liegt ausschließlich lokal, kein Container-/App-Release veröffentlicht. Nicht installieren oder öffnen, bis Fenstertest und sichere Übergabe wieder freigegeben sind. Erst dort tatsächliche deutsche Geräteerkennung, Systemdialog, Mikrofon/Abbruch, Entwurf/Sendeklick, Hörqualität, Akku/RAM und die drei Kalender prüfen.

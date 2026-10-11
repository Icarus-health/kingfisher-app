# Speicherschutz als gepaartes lokales Update installiert

11. Oktober 2026. Laufzeitcode `36907338bde9251b4f92081913327ac0d63e463c`, installierte App und Backend `1.0.6-preview.3690733`. Draft #54 bleibt offen; kein Main-Merge, keine Registry-Veröffentlichung oder CI-Wiederholung.

## Paketprüfung

Eingefrorenes Git-Archiv des geprüften Codes, vorhandene lokale Abhängigkeiten. Das zuvor installierte Image `sha256:a8c96f76d9c5c67de4aff2ffebcd1590f95d70547cfca5760c142cd42909c45a` ist die exakte Basis. Sieben Python-Module einschließlich des neuen `storage_capacity.py`, neu gebautes UI und Versionsmetadaten wurden ersetzt. Endimage `sha256:6172ec0c0a63075d9a7481c9c934657f698a6f3d8764e063cdbccdf9a21daa63`. Keine Abhängigkeiten, Modelle oder privaten Daten nachgeladen.

`package-freeze.json` bindet sämtliche 270 Python-Paketdateien und 112 UI-Dateien. Der finale isolierte Paketlauf ohne Netzwerk oder persönliche Volumes bestätigt alle Hashes, die zehn bestehenden künstlichen Ablaufblöcke und den bestehenden lokalen Antwortrollenwechsel. Zusätzlich wurden die tatsächlich ausgelieferten Speicherprüfung, Mailstatus-/Resume-/Pause-Routen und Scheduler geprüft: knappe bzw. nicht messbare Reserve sperrt weitere Arbeit, Resume liefert 507, Pause bleibt möglich, keine Mailverbindung und keine vollständige Laufzeitmarkierung. Bei erholter Reserve bleibt die eigene Pause erhalten. Der erste Zusatztest hatte kein verbundenes künstliches Konto eingerichtet und scheiterte am Kontozugang; Fixture ergänzt, finaler vollständiger Paketlauf bestanden. Kein Produktcode dafür geändert.

ARM64-App gebaut, ad-hoc signiert, nicht notarisiert. Alle sechs Dateien im schreibgeschützt eingebundenen DMG stimmen mit dem neuen nativen Manifest überein; strenge tiefe Signaturprüfung bestanden, DMG anschließend ausgeworfen. Kanonisches Paket lokal unter `Kingfisher-Pruefpakete/2026-10-11-intake-capacity-3690733/Kingfisher.dmg`, SHA-256 `d105c0ce1b90a96a7b7b492ac84904fa0c4da81e1ce79089076912768ec331d0`. Keine Binärpakete eingecheckt. Der getrennte [gerenderte UI-/Regressionstest](../2026-10-11-intake-storage-gate/README.md) bleibt sein eigener Nachweis; der Pakettest behauptet keine Browserbedienung oder echte Modellqualität.

## Persönliche Installation

Vor dem Umschalten frisch vollständig kalt gesichert: 148 Dateien, neun Verzeichnisse, 281.322.188 Bytes. Separate Wiederherstellung stimmt in Inhalten, Verzeichniseinträgen, Besitzern/Rechten, Nanosekunden-Zeiten und Extended Attributes überein; Integrität aller 17 Wurzel-SQLite-Datenbanken bestanden. Archive, Volume-Manifest und Zugangsdaten ausschließlich im privaten Sicherungsordner. Der vorherige Code bleibt als Rückweg erhalten.

Installer prüft jetzt vor Sicherung mindestens 512 MiB und 1.024 verfügbare Inodes sowohl für `/` als auch `/data`, zusätzlich Hostplatz für Datenvolumengröße plus 512 MiB. Das ist eine Momentaufnahme, keine reservierte Kapazität. Ein unabhängiger statischer Review der angepassten Sicherung/Installation fand keinen konkreten Blocker; Reviewer führte keine Skripte aus. Der künstliche Test führt die tatsächlichen extrahierten Rückfallfunktionen aus: Dienst zuerst stoppen, Code/Config zurückstellen, neue Daten behalten, alten Dienst nicht automatisch auf möglicherweise verändertem Bestand starten; Stopfehler propagiert vor Dateiveränderungen. Kein stromausfallsicherer Gesamtwechsel oder automatische Datenrücksicherung behauptet.

Tatsächlich installierter Appinhalt entspricht dem kanonischen DMG. Backend gesund und neue Version authentifiziert bestätigt; dasselbe persönliche Datenvolume. Alle sieben geprüften Kerntabellen sowie Schemas und `user_version` aller 17 Datenbanken vor/nach dem Wechsel identisch. In der geschützten Konfiguration ausschließlich Image-Zeile geändert, Modus 0600. Das behauptet keine unveränderten Live-Heartbeat-Dateien. Große Mailaufnahme weiterhin global pausiert; keine produktive Modellrolle geändert, Cloudanfrage, Modellnachladung oder Inferenz gestartet.

Frische Statusprüfung vor und nach dem Wechsel: Kalender `granted`, aktiviert, Helfer online, drei ausgewählt, kein Fehler, `memory_allowed:false`. Ausgelieferter Speicherwächter meldet keine Sperre; rund 1,39 GiB verfügbar. Das ist keine Kapazitätsfreigabe für den gesamten historischen Mailbestand. Die native Appdatei wurde aktualisiert, der bisherige native Prozess nicht neu gestartet; neuer nativer Fensterstand und persönliche Tagesabläufe bleiben ungeprüft. Die letzte Computersteuerung traf auf den gesperrten Mac, keine wiederholte Entsperrungsaufforderung.

## Grenzen und nächster Nachweis

Reserveprüfung ist keine harte Schreibquote: einzelne bereits laufende Jobs, Anhänge, Journale oder andere Prozesse können zwischen Messungen wachsen. Nicht alle manuellen API-Schreibwege sind gesperrt. Große Aufnahme erst nach persönlicher Quellen-/Fragenabnahme und weiterer Kapazitätsprüfung fortsetzen. Fehlendes ausgewähltes Antwortmodell bleibt offen, nicht automatisch ersetzt. Keine Perfektions- oder fertige Alltags-CoS-Zusage aus grünen technischen Tests ableiten.

Die beigefügten Hilfen dokumentieren diesen konkreten Wechsel mit festen Ausgangs-IDs und sind nicht blind wiederholbare allgemeine Updater. `verification.json`, Statusdateien und komprimierte Logs enthalten nur technische Nachweise; private Sicherungsarchive und Konfigurationswerte sind nicht enthalten.

# Mac-Korrekturen und frische lokale Installation

Stand: 6. Oktober 2026. Basis: öffentlicher `main`,
`d5d9a5506dda459859f1c2f8718e70bab060db6d`.

## Korrekturen

- Acht `.ts`/`.tsx`-Paare hatten denselben Modulnamen nach Kleinschreibung.
  Auf Macs löste TypeScript dadurch teils den Helfer statt der Komponente auf.
  Die Komponenten tragen jetzt eindeutige Namen; Importe, betroffene Tests und
  die Codekarte sind angepasst. Ein Dateinamentest verhindert weitere Kollisionen.
- Eine gespeicherte Personenantwort konnte nach einer neuen Mail veraltet bleiben,
  wenn die Mail nur die bereits bekannte Adresse und nicht den Namen enthielt.
  Die Antwort speichert jetzt zusätzlich die damalige Personensuche; eine neue
  Auswahl macht sie ungültig. Eine während des Modellaufrufs eintreffende Mail
  wird ebenfalls durch einen Regressionstest abgedeckt.
- App und CLI prüfen beim Update das laufende Bild. Der Rückweg hält dessen
  unveränderliche ID fest, stoppt den Dienst, spielt mit dem neuen Bild die
  Sicherung zurück und startet erst dann das alte Bild. Der historische
  Prüfmodus bleibt aktiv. Stop-/Restore-Fehler starten keinen alten Code auf
  möglicherweise migrierten Daten. Die App stellt Bestände aus Arbeitskopien
  und zusätzliche Ordnerfreigaben nicht mehr stillschweigend um.
- Unter der macOS-Bash wurde das schließende deutsche Anführungszeichen in
  `$FASSUNG“` als Teil des Variablennamens gelesen. `${FASSUNG}“` liefert jetzt
  die vorgesehene lesbare Ablehnung ungültiger Fassungen.
- Ein Timeline-Test verwendete September-Daten in einem gleitenden
  30-Tage-Fenster. Seine Uhr ist jetzt auf die synthetische Testwelt festgelegt;
  Produktzeit und Produktverhalten sind unverändert.

## Lokale Nachweise

| Prüfung | Ergebnis |
|---|---|
| Vollständige `sidecar/tests` unter Python 3.12 | 4706 bestanden, 1 übersprungen |
| Frontend `npm test` | 275 bestanden |
| Frontend `npm run build` | bestanden; bestehender Hinweis zur Chunk-Größe |
| Asset-Vertrag | bestanden: 16 Dateien, 15 Icons |
| `macos/test_mac_app.py` mit macOS-26.5-SDK und isolierten Modul-Caches | 26 bestanden, 1 übersprungen |
| Vollständige Swift-App für arm64 bauen, DMG erzeugen, Signatur der installierten App prüfen | bestanden |
| Echter Docker-Rückweg, synthetisches getrenntes Volume, ohne Netzwerk | vorheriges Schema und Wert wiederhergestellt; Release 1.0.0 startet im authentifizierten Prüfmodus |
| Neue lokale Installation | authentifizierte Fassung 1.0.1; 0 Episoden, 0 Claims; Einrichtung offen, keine alten Konten übernommen |

Der erste Backend-Volltest zeigte den oben beschriebenen kalenderabhängigen
Testfehler. Nach dessen Korrektur und der zusätzlichen CLI-Prüfung wurde der
Volltest erneut ausgeführt. Die neuen gezielten Personentests und die Probe mit
einem während des Ladens veränderten alten Image-Tag wurden ebenfalls geprüft.

## Installation und Grenzen

Die alten lokalen Kingfisher-Instanzen wurden angehalten und vollständig
gesichert: konsistente SQLite-Snapshots, vollständige Datenordner und private
Konfigurationen. Der alte Standardbestand liegt zusätzlich in einem separaten,
inhaltlich geprüften Archivvolume. Die Neuinstallation verwendet den leeren
Standardbestand und neue Schlüssel. Private Sicherungen und ihre Pfade stehen
nicht im Repository.

Die installierte **lokale Testfassung 1.0.1** enthält diese Korrekturen. Sie ist
kein veröffentlichter Release; `VERSION`, öffentliche Images und Download-Seite
wurden nicht verändert. Die Intel-Kompilierung scheiterte an fehlenden
x86_64-Kompatibilitätsbibliotheken der lokalen Apple-Werkzeugkette. Der lokale
App-Bau beschränkt sich deshalb auf arm64; der universelle Release-Bau bleibt
unverändert und ist hier nicht als erfolgreich belegt.

Der Mac war beim Computersteuerungsversuch gesperrt. Der Nutzer hat den
Fenstertest ausdrücklich auf später verschoben. Einrichtung, Kontenanmeldung
und Bedienung im neuen App-Fenster sind deshalb noch nicht visuell abgenommen.
Die Prüfung belegt keine fehlerfreie Antwortqualität mit echten Mails.

Nachtrag nach dem Entsperren, ebenfalls am 6. Oktober: Das installierte native
Fenster öffnet `/willkommen` ohne Browserleisten. Alle sechs Seiten lassen sich
über die Schrittnavigation öffnen und wieder zur Namenseingabe zurückstellen.
Mail und Kalender sind unverbunden, die optionalen Freigaben ausgeschaltet;
Einrichtung abschließen, Kontenanmeldung, Modelldownload, Import und
Sicherungsdownload wurden dabei nicht ausgeführt.

Der Modellschritt verwendete zunächst die Container-Untergrenze statt der
Mac-Ausstattung. Über den vorhandenen `scripts/report_device.py` wurde die
echte Hardware ausschließlich dem lokalen Sidecar gemeldet. Die Oberfläche
zeigt danach die Host-Ausstattung und passt die Modellempfehlung an. Die
automatische Hardwaremeldung beim Start der ladbaren Mac-App bleibt offen;
dieser Nachtrag belegt eine lokale Einrichtungskorrektur, keinen neuen
automatischen App-Startpfad.

GitHub Actions wurden für diese Lieferung nicht gestartet. Die Commits tragen
`[skip ci]`; keine Workflow-Datei wurde deaktiviert oder verändert.

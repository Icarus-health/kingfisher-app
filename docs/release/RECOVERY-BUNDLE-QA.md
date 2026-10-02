# Vollständiges Wiederherstellungspaket — 7. September 2026

## Inhalt und Bedienung

`python -m icarus_memory.recovery_bundle export --data DATENORDNER --env-file DOCKER_ENV --output SICHERUNG.recovery` erzeugt ein verschlüsseltes Paket. Die Passphrase wird verdeckt abgefragt und muss bestätigt werden. Vorher die Anwendung und alle anderen Schreiber auf diesen Datenordner stoppen. Der Datenordner muss für SQLite zugänglich sein; bei schreibgeschütztem Docker-Volume zuerst die angehaltenen Dateien einschließlich vorhandener WAL-Dateien in einen temporären Arbeitsordner kopieren.

`python -m icarus_memory.recovery_bundle restore --bundle SICHERUNG.recovery --target NEUES_VERZEICHNIS` prüft Entschlüsselung, Manifest, Dateinamen und SQLite-Integrität. Das Ziel darf noch nicht existieren. Dort entstehen `data/` und `settings.env`; diese Konfiguration gehört beim Start zum wiederhergestellten Datenordner. Bestehende Daten werden nicht überschrieben. Danach die ursprüngliche Anwendung wieder starten, auch wenn die Sicherung scheitert.

Die Verschlüsselung verwendet das bereits vorhandene authentifizierte Icarus-Format in `crypto.py`. Das Paket enthält auch die ausdrücklich angegebene Docker-Umgebung, einschließlich darin hinterlegter Schlüssel und gegebenenfalls der Passphrase für die verschlüsselte Schlüsseldatei. Die Paket-Passphrase separat aufbewahren. Externe macOS-Schlüsselbunde, Modelle, Quelldateien außerhalb des Datenordners und das Docker-Image sind nicht enthalten. Mac-Systemfreigaben müssen auf einem anderen Rechner erneut erteilt werden.

## Behobene Lücke

Die vollständige SQLite-Sicherung enthielt bisher `mac-calendar.sqlite3` nicht. Sie gehört jetzt zur Sicherungs- und Wiederherstellungs-Allowlist. Die laufende Kalenderkonfiguration und der Snapshot gehen damit nicht mehr bei der Datensicherung verloren.

## Nachweise

- 20 Tests zu Backup und Wiederherstellungspaket bestanden. Geprüft: Aufgaben, Mac-Kalender, Schlüsseldatei, Docker-Konfiguration, falsche Passphrase, Manipulation, unerlaubte Dateipfade und Schutz eines vorhandenen Zielverzeichnisses.
- Echte Instanz für konsistente Aufnahme gestoppt; Quelle nur lesend in Hilfscontainer eingebunden. SQLite benötigt für manche WAL-Datenbanken Schreibzugriff auf Hilfsdateien; deshalb wurde nach dem ersten abgewiesenen Leseversuch eine temporäre Kopie der gestoppten Dateien samt WAL verwendet. Keine Änderung am Originalbestand.
- Echtes verschlüsseltes Paket erstellt und in ein neues Ziel wiederhergestellt: elf Datendateien und Konfiguration geprüft.
- Wiederhergestellte App in einem Container ohne Netzwerk mit HTTP-Testclient geöffnet: Aufgaben, Projekte, letztes Gespräch, Wissensgraph und Mac-Kalenderstatus erfolgreich lesbar.
- Produktive Instanz anschließend wieder gestartet. Paket lokal im Aufgabenordner unter `backups/kingfisher-20260907.recovery`; Paketpassphrase separat in der privaten Arbeitsablage `work/recovery.passphrase`, Dateirechte 0600. Keine Passphrase in Ausgabe oder Repository.

## Frühere Abnahmegrenze

Der Alltagsweg braucht eine einfachere Bedienung in der Oberfläche und einen vollständigen Browserdurchgang nach Restore. Der Test bestätigt den Docker-Datenbestand dieses Macs; er belegt keine Neuinstallation auf einem anderen Mac, keine Übernahme externer Dateien/Modelle und keine automatische Wiederherstellung von macOS-Freigaben. Dies war die damalige offene Grenze; der Abschluss ist unten dokumentiert.

## Mac-Starter

Der lokale Aufgabenordner enthält `Kingfisher-sichern.command`. Ein Doppelklick fragt das Sicherungspasswort verdeckt zweimal ab, stoppt die konfigurierte Instanz, kopiert den angehaltenen Bestand einschließlich WAL in einen temporären Containerbereich, erstellt das verschlüsselte Paket und probiert dessen Wiederherstellung aus. Die Datei landet standardmäßig unter `~/Documents/Kingfisher-Sicherungen`; Finder zeigt sie anschließend an. Der Starter speichert das eingegebene Passwort nicht.

Die wiederverwendbare Implementierung liegt in `scripts/create_recovery_bundle.py`. Sie ermittelt Image-ID und Datenmount aus Docker, prüft die benötigte Funktion vor dem Anhalten, nutzt einen Hilfscontainer ohne Netzwerk und übergibt das Passwort ausschließlich über stdin. Eine Dateisperre verhindert parallele Sicherungen mit derselben Konfiguration. Eine zuvor laufende Instanz wird auch im Fehlerfall wieder gestartet; der Starter wartet anschließend auf den Gesundheitsendpunkt. Eine zuvor gestoppte Instanz bleibt gestoppt.

Fünf Starter-Tests prüfen erfolgreichen und fehlgeschlagenen Export, laufende/gestoppte Ausgangslage, keine Passphrase in Prozessargumenten und Doppelstarts. Der echte Ablauf wurde auf dieser Instanz geprüft. Beim ersten anschließenden Browseraufruf zeigte sich eine Start-Rennbedingung; die ergänzte Erreichbarkeitsprüfung schließt diese Lücke. Die `.command`-Datei wurde auf Bash-Syntax geprüft; die Finder-/Terminalinteraktion mit manueller Passworteingabe bleibt von der automatisierten Funktionsprüfung getrennt.

## Wiederherstellung per Mac-Startdatei

`Kingfisher-wiederherstellen.command` im lokalen Aufgabenordner öffnet eine Dateiauswahl und fragt das Sicherungspasswort verdeckt ab. `scripts/restore_recovery_bundle.py` entschlüsselt das Paket mit dem Image der vorhandenen Instanz in einen neuen Ordner unter `~/Documents/Kingfisher-Wiederhergestellt-…`. Der Hilfscontainer hat kein Netzwerk; die bestehende App wird nicht angehalten oder ersetzt. Finder öffnet danach den wiederhergestellten Datenordner samt Konfiguration. Der Wechsel der laufenden Instanz auf diesen Bestand ist ausdrücklich ein weiterer Schritt.

Der Backend-CLI meldet falsche Passwörter und beschädigte Pakete jetzt ohne Traceback. Neue Prüfungen bestätigen, dass fehlerhafte Manifestinhalte keinen halben Wiederherstellungsordner hinterlassen. Zusammen mit Backup- und Startertests sind 27 Tests grün. Der neue Wiederherstellungsstarter wurde mit einem echten zuvor erstellten Paket ausgeführt; die wiederhergestellte Konfiguration wurde bytegenau verglichen und der Kalenderbestand geprüft. Die temporäre Prüfkopie wurde anschließend entfernt. Die manuelle Finder-Auswahl selbst wurde nicht automatisiert bedient.


## Einstellungen und Mac-Helfer

Der aufklappbare Bereich „Vollständige Sicherung“ startet einen expliziten
Auftrag. Der ausgehend verbundene `scripts/mac_backup_worker.py` verarbeitet
jeweils eine Sicherung. Nur sein Token, kein Browser-Sitzungscookie, erlaubt
das einmalige Abholen des Passworts. Das Passwort bleibt im Arbeitsspeicher;
der Ergebnisstatus liegt getrennt in einer operativen Statusdatenbank und
übersteht den App-Neustart. Diese Auftragsdatenbank gehört nicht zum gesicherten
persönlichen Bestand. Nach einem Neustart werden wartende Aufträge verworfen,
wenn ihr Passwort nicht mehr verfügbar ist.

Der lokale Mac-Starter startet den Helfer mit. Die Alltagsinstanz verwendet
`kingfisher:settings-backup` (b37dfef2aa94); vor dem Wechsel wurde der Snapshot
`/data/sicherungen/kingfisher-20260907T202912Z` erstellt. Geschützter Browserstatus
bestätigt den verbundenen Helfer, der echte Kalenderablauf blieb erfolgreich.

Im getrennten Bestand auf Port 8892 wurden ungleiche Passwörter abgewiesen,
eine echte verschlüsselte Sicherung erstellt und geprüft, die Eingabefelder
geleert und das Ergebnis nach Neuladen erhalten. Das Paket hat Dateirechte
0600. 15 gezielte Tests, UI-Build, Assetprüfung und die vollständige Suite mit
910 Tests bestanden. Desktop bei 1440 × 1000 geprüft; bei 390 Pixeln überlagert
die bestehende Navigation die Bedienung. Mobile bleibt nicht abgenommen.

Das aus der Oberfläche erzeugte Paket wurde zusätzlich mit dem vorhandenen
Wiederherstellungshelfer in einen neuen Testordner entschlüsselt und als eigene
App auf Port 8893 geöffnet. Im geschützten Browser waren das gespeicherte
Ollama-Modell, die ursprünglichen Gesprächsantworten 42 und 17 sowie die Ziele
vor/nach der früheren Updateprüfung vorhanden, auch nach Neuladen und ohne
Browserfehler. Der bequeme Start bzw. Wechsel auf den wiederhergestellten
Bestand ist noch nicht Teil des Mac-Wiederherstellungsstarters.


Ein neuer echter Ollama-Auftrag in der wiederhergestellten Unterhaltung
lieferte 16 für 8 + 8; die Antwort blieb nach Neuladen erhalten. Ein erster
Prüfversuch zählte die Antworten vor dem Laden der Unterhaltung und wartete
auf den falschen Eintrag. Nach dem Warten auf beide ursprünglichen Antworten
bestand der korrigierte Browserablauf. Auch die erste tatsächlich erzeugte
Antwort (13 für 6 + 7) wurde unabhängig nach Neuladen bestätigt.


## Abschluss: Wiederhergestellte App direkt öffnen

Der Mac-Starter verwendet jetzt `--open-app`. Nach Dateiauswahl und Passwort
entschlüsselt er in einen neuen Ordner und öffnet dessen eigene App im Browser.
Im Ordner bleibt `Kingfisher-öffnen.command` zum späteren erneuten Öffnen. Der
Starter kopiert den geprüften Bestand einmalig in ein eigenes Docker-Volume;
die ursprüngliche App und der entschlüsselte Ausgangsordner werden nicht
überschrieben. Ein zufällig freier, ausschließlich lokal gebundener Port wird
gespeichert. Wiederöffnen verwendet dieselbe Instanz. Eine Sperre verhindert
Doppelstarts; eine Docker-Kennzeichnung schützt fremde Instanzen. Die App läuft
als Benutzer `kingfisher`, nur das einmalige Kopieren richtet die Dateirechte ein.

Vier neue Tests prüfen Schutz einer fremden Instanz, Wiederöffnen mit gleichem
Bestand/Port, bereinigten Kopierfehler ohne Veränderung der Quelle und den
abgewiesenen Doppelstart. Zusammen mit Paket- und Sicherungsstartertests:
19 Tests bestanden. Der echte Docker-Lauf bestätigt Benutzerrechte und
Wiederöffnen. Der vollständige Wiederherstellungsstarter wurde mit einem über
die Einstellungen erzeugten Paket ausgeführt; nur der macOS-Aufruf `open`
wurde im Test abgefangen. Die ausgegebene App-Adresse wurde anschließend im
geschützten Browser geöffnet: Modellwahl, ursprüngliche Antworten, Ziele,
Neuladen und eine neue echte Ollama-Antwort mit erhaltenem Verlauf bestanden.
Die manuelle Finder-Dateiauswahl bleibt separat von diesem automatisierten
Ablauf; sie verwendet den vorhandenen macOS-Dateidialog.

Damit ist Roadmap-Punkt 18 erfüllt. Der Umfang ist der vollständige lokale
App-Datenbestand einschließlich Schlüsseldatei und zugehöriger Konfiguration.
Modelldownloads, externe Dateien und macOS-Zugriffsfreigaben bleiben außerhalb
dieses Pakets; Neuinstallation, Update/Rückkehr und der gesamte Alltagstest
sind weiterhin die eigenen offenen Punkte 17, 19 und 20.

## Vollständig befüllter Datenbestand

`test_complete_recovery.py` legt echte fachliche Einträge in sämtlichen zehn
gesicherten SQLite-Stores an: Selbstmodell, Audit, Aufgaben, Arbeitsbereiche,
Episoden, Vorschläge, Gespräche, Wissensgraph, Regeln und Mac-Kalender.
Zusätzlich enthält der Bestand Einstellungen und einen mit der echten
Dateiverschlüsselung gesicherten Testzugang.

Nach Export und separater Wiederherstellung stimmen vollständige SQL-Dumps
und Schema-Versionen aller zehn Datenbanken überein. Einstellungen und
Schlüsseldatei sind bytegleich; das Testpasswort lässt sich mit der mitgesicherten
Konfiguration entschlüsseln. Projektzuordnung der Aufgabe, Beziehungsziel und
Quellenverweis des bestätigten Wissens sind über die Store-APIs wieder lesbar.
Eine nach der Sicherung erfasste Aufgabe bleibt im ursprünglichen Bestand
erhalten und wird nicht in die ältere Sicherung hineingedeutet.

Der Test bestand lokal sowie mit abgeschaltetem Netzwerk im tatsächlich
ausgelieferten Image `kingfisher:versioned-recovery`. Ausschließlich temporäre
synthetische Daten; kein Zugriff auf den Nutzerbestand. Dies ergänzt die
vorhandenen echten Browser-/Ollama-Restoreprüfungen. Es ersetzt keinen
vollständigen Versionswechseltest für alle Stores und keine UI-Abnahme.

# Nach einem Restore wieder lokal weiterarbeiten

Anschluss an die lesende Sicherungsprüfung auf Basis `8b6393e`. Die normale
Kingfisher-App kann jetzt aus einem ausdrücklich gewählten historischen Stand
eine **separate Arbeitskopie** erhalten. Die Originale und andere Vergleichsstände
werden weder verändert noch automatisch zusammengeführt.

Die Auswahl bindet sich an den aktuellen Prüfbericht. Vorhandene ungeklärte
Dateien, eine inzwischen veränderte Quelle, Symlinks oder ein bereits vorhandenes
Ziel brechen die Vorbereitung ab. Fehlende Bereiche älterer Sicherungen werden
ausgewiesen; mindestens eine lesbare Datenbank ist erforderlich. Ein Zeitstempel
beweist keine Vollständigkeit oder Aktualität. Unbekannte spätere Änderungen
müssen ausdrücklich als ungelöst akzeptiert werden.

## Was übernommen wird

Gespeicherte Quellen, Aufgaben, Projekte, Verbindungen, Korrekturen, Skilltexte
und Historie stammen ausschließlich aus dem ausgewählten Stand. Eigene
Mailadressen bleiben zur Identitätserkennung erhalten. Ein Quellenentzug im
gewählten Stand bleibt wirksam. Ein Entzug, der nur in einem anderen oder
unbekannten Stand existiert, wird **nicht automatisch rekonstruiert**.

Modelle, Hintergrundverarbeitung, externe Dienste, Kalenderzugriff und
automatische Aktionen starten ausgeschaltet. Aktive Dauerregeln werden in der
Kopie widerrufen, aktive persönliche Skills erneut zur Prüfung vorgemerkt.
Bereits widerrufene oder abgelehnte Skills behalten ihren Zustand. Gespeicherte
Kalenderdaten, Ordner und lokale Zuordnungen bleiben erhalten.

Die Kopie bekommt neue private Startwerte und einen eigenen verschlüsselten
Schlüsselspeicher. Historische Schlüssel und geerbte Anbieter-, Proxy-, Harness-
oder Telemetrievariablen werden nicht aktiviert. Der normale und jeder
Fallback-Keychain-Konstruktor nutzen für diese Instanz ausschließlich ihren
Dateispeicher. Neue Verbindungen werden anschließend über die vorhandene
Einrichtung freigegeben.

## Nachweis

- 37 direkte neue Tests bestanden: 29 Kopier-/Vertragsfälle, sechs normale
  App-/Schlüsseltests und zwei Launcherfälle.
- Gefüllter künstlicher Bestand: Originalquelle und Projekt samt Aufgabe über
  die normalen API-Routen gelesen, neue Aufgabe demselben Projekt zugeordnet,
  Stores neu verdrahtet, App erneut aufgebaut und Aufgabe wiedergefunden.
  Quellenentzug und deaktivierte Automatik blieben erhalten. Netzwerk,
  Subprozesse, OS-Schlüsselbund und Schedulerstart waren dabei Testfallen.
- Breiter betroffener Lauf: 271 bestanden; ein unveränderter Launcherfall
  scheiterte ausschließlich an der Sandbox-Sperre beim Reservieren eines
  lokalen Ports. Die gezielte, freigegebene Wiederholung der ganzen
  Launcherdatei bestand mit fünf Tests. Docker-Aufrufe blieben simuliert.
- Separater früherer Helferlauf: 103 betroffene Tests einschließlich
  Procedures, Regeln, Mac-Kalender und WorkspaceViews bestanden. Die Läufe
  überschneiden sich und werden nicht addiert.
- Unabhängiger Review: 36 Tests am damaligen Stand bestanden, keine offenen
  wesentlichen Befunde. Danach kam ausschließlich die zusätzliche Ablehnung
  extrem verschachtelter JSON-Marker hinzu; der finale direkte Lauf umfasst 37.
  Geprüft wurden auch Cloud-/Kalenderbindungen bei erneuter Anmeldung:
  neue Credential-Salts beziehungsweise Grant-IDs reaktivieren die alten
  Aufträge nicht allein durch denselben API-Schlüssel oder Account.
- Vor Implementierung scheiterten 25 Helferfälle am fehlenden Modul; normale
  App-Nutzung und isolierter Keychainzugang scheiterten in zwei Runtimefällen.
  Die Launcherfälle scheiterten ebenfalls vor Implementierung. Fehler bei der
  Kopie, veränderte Quellen und ein konkurrierend angelegtes Ziel sind geprüft.

Cloud-/OAuth-Neuanmeldung wurde anhand ihrer konkreten Bindungslogik geprüft,
nicht live ausgeführt. Die bekannte Starlette/httpx-Abkündigungswarnung bleibt.
Keine persönlichen Quellen, bezahlten Aufrufe, Modellstarts oder Installationen.

## Technischer Einstieg

Das Modul `icarus_memory.recovery_workspace_cli` bietet drei getrennte Befehle:

1. `check --source <historischer Datenordner>` erzeugt nur den Prüfbericht.
2. `prepare --source <Ordner> --target <neuer Ordner> --fingerprint <Prüfwert>
   --selection <restored oder Gruppenkennung> --acknowledge-unknown-history`
   erstellt die private Kopie, startet sie aber nicht.
3. `serve --folder <Arbeitskopie> --port <freier lokaler Port>` startet den
   vorhandenen App-Server in einem sauberen Kindprozess, nur auf Loopback.

Aufruf jeweils mit `python -m icarus_memory.recovery_workspace_cli`. Die private
`settings.env` wird strukturiert gelesen und niemals als Shellcode ausgeführt.
`serve` öffnet keinen Browser. Für die normale Oberfläche muss wie bisher
`app/dist` gebaut sein. Aufbewahrung und Bereinigung der historischen Kopien sind
separate Entscheidungen; dieser Weg löscht sie nicht.

## Weiter offen

Dies ist der technisch geprüfte Rückweg in eine schreibbare normale App,
**noch nicht der fertig bedienbare native Wiederherstellungsablauf**. Auswahl,
Erklärung unbekannter späterer Änderungen, sichere Neueinrichtung und echte
Mac-Bedienung müssen noch im Produktweg zusammengeführt und abgenommen werden.
Stromausfall-/Crash-Durabilität wurde hier nicht geprüft. P5, persönliche
Installation und Nutzungswoche sind nicht abgeschlossen; Großimport bleibt
pausiert.

# Kingfisher täglich lokal nutzen

Stand: 6. September 2026.

Kingfisher läuft als lokale Docker-App. Das Morning Briefing, Gespräche,
Aufgaben und Quellen liegen in einem persistenten SQLite-Volume auf diesem Mac.
Es gibt kein Serverkonto, keinen Cloud-Speicher und kein Supabase.

## Starten

**Der erste Weg ist die Download-Seite** (`https://icarus-health.github.io/kingfisher-app/`):
„Für Mac laden“, Docker Desktop installieren und einmal öffnen, die App aus
`Kingfisher.dmg` in „Programme“ ziehen, Ollama installieren. Neue Fassungen
bietet Kingfisher danach selbst an ([Download und Updates](53-download-und-updates.md)).

Für Entwickler bleibt der Weg aus dem Quelltext: die Starter-Datei
`Kingfisher starten.command` oder `make start`. Docker Desktop muss laufen. Dann
im Projektordner:

```sh
make start
```

Kingfisher ist anschließend ausschließlich hier erreichbar:

```text
http://127.0.0.1:8890/today
```

`make url` zeigt die Adresse erneut. Die lokale Browser-Sitzung wird beim
Öffnen der Oberfläche gesetzt; der Zugriffsschlüssel steht weder in der URL
noch im Browser-Speicher oder Container-Log.

## Eigene Notizen verbinden

Ein Notizordner wird nur nach einer eindeutigen Freigabe eingebunden und immer
nur lesend. Die Freigabe wird lokal in `.kingfisher.sources` gespeichert, ist
nicht versioniert und bleibt beim nächsten `make start` erhalten.

```sh
make quelle-freigeben NOTIZEN=~/Documents/Obsidian
make start
```

Die aktuelle Freigabe prüfen:

```sh
make quellen
```

Den Zugriff wieder entziehen:

```sh
make quelle-entziehen
make start
```

Nach einer neuen Freigabe muss Kingfisher einmal neu gestartet werden, damit
Docker den Ordner als `/notizen` einbindet.

## Notizen aufnehmen

Die Aufnahme ist bewusst manuell. Sie kopiert weder Dateien noch verändert sie
sie. Kingfisher liest nur Textformate, hält zu jeder aufgenommenen Notiz
Herkunft und Digest fest und nimmt dieselbe unveränderte Datei nicht doppelt
auf.

Für einen normalen Markdown-Ordner:

```sh
make notizen-importieren
```

Für einen Obsidian-Vault oder Notion-Export:

```sh
make notizen-importieren ADAPTER=obsidian
make notizen-importieren ADAPTER=notion
```

Der Befehl zeigt ehrlich, wie viele Dateien neu aufgenommen, bereits bekannt
oder übersprungen wurden. Danach erscheint im Morning Briefing ein neutraler
Hinweis auf neue Quellen. Der Inhalt der Notiz wird nicht als Tatsache
behauptet, nicht automatisch in das Gedächtnis übernommen und nicht an ein
Modell versendet.

## Gedächtnis und Widersprüche

Eine Quelle ist noch kein Wissen. Erst ein später ausdrücklich angenommener,
mit Zitat und Digest belegter Kandidat kann zu einer Wissensaussage werden.
Wenn zwei belegte Angaben nicht zusammenpassen, erscheint im Morning Briefing
eine neutrale Aufforderung „Gedächtnis klären“. Bis zu einer bewussten
Entscheidung wird keine der Angaben als Wahrheit verwendet oder in einem
Gesprächskontext an ein Modell weitergegeben.

Die grafische Gedächtnisansicht und die read-only Personen-/Projektprofile
zeigen nur belegte Projektionen. Kandidaten werden weiterhin im Gespräch mit
Quellzitat bestätigt, abgelehnt oder als Widerspruch offen gehalten.

## Lokales Modell verbinden

Das Morning Briefing und die Quellenaufnahme funktionieren ohne Modell. Für
echte Gespräche kann ein bereits lokal installiertes Ollama-Modell verbunden
werden:

```sh
ollama pull qwen3.5:4b
make modell-lokal MODELL=qwen3.5:4b
```

Der Befehl speichert die Modellwahl und testet die Verbindung aus dem laufenden
Container. Erst nach einer erfolgreichen Modellantwort meldet der Befehl
„verbunden“. Ein nicht erreichbares Modell führt zu einem Fehlerstatus; die
gespeicherte Auswahl bleibt für einen erneuten Versuch erhalten. Eine bereits
angezeigte Gesprächsseite nach erfolgreicher Einrichtung neu laden.

Der Container erreicht Ollama unter `host.docker.internal:11434`, also über
den ausdrücklich freigegebenen lokalen Bridge-Host. Der Test überträgt nur eine
kurze Bereitschaftsfrage, keinen persönlichen Gedächtniskontext. Ein Test direkt
vom Mac aus ersetzt diesen Container-Test nicht. Bei einem Verbindungsfehler
Ollama und das installierte Modell prüfen und denselben Befehl erneut ausführen.

Explizit beim Containerstart gesetzte Modellvariablen haben Vorrang vor der
gespeicherten Einrichtung. Meldet der Befehl deshalb eine abweichende aktive
Konfiguration, diese Vorgaben in der lokalen Startkonfiguration anpassen und
`make start` erneut ausführen. Das Volume und die lokale Schlüsseldatei erhalten.
Alternativ unter Einstellungen → Integrationen das lokale Ollama-Modell auswählen
und „Speichern und verbinden“ anklicken. Erst eine erfolgreiche Modellantwort
wird als verbunden angezeigt. Danach führt „Zum Gespräch“ zurück zur Startseite.

## Mail und Kalender

Mehrere Mailkonten sowie CalDAV- und HTTPS-iCalendar-Quellen können in
`/settings` ausdrücklich lokal hinterlegt und wieder entfernt werden. Ohne
deine Eingabe greift Kingfisher auf kein Postfach und keinen Kalender zu. Die
Quellen werden nur lesend in das Morning Briefing und die jeweiligen lokalen
Übersichten einbezogen; Teilfehler bleiben sichtbar.

Eine eigenständige Kalenderoberfläche ist noch nicht freigegeben, weil dafür
kein kanonischer Referenzscreen vorliegt.

Die vollständige Hintergrundsynchronisation und Nutzung in allen
Chief-of-Staff-Abläufen bleiben Arbeitspakete der Roadmap.

Auch ein Mikrofon wird erst angezeigt, wenn lokale Spracheingabe tatsächlich
eingerichtet und überprüft ist.

## Anhalten und sichern

```sh
make backup  # vollständiger lokaler Snapshot nach Integritätsprüfung
make stop    # Anwendung anhalten; Daten und Schlüssel bleiben erhalten
make start   # mit demselben lokalen Bestand fortsetzen
```

Ein Snapshot im Docker-Volume schützt nicht gegen einen Verlust des gesamten
Volumes oder dieses Macs. Für eine zusätzliche, bewusst gewählte lokale Kopie:

```sh
make backup-auslagern ZIEL=~/Documents/Kingfisher-Backups
```

Der Zielordner wird ausschließlich von dir bestimmt. Die Kopie enthält den
vollständigen, bereits geprüften Snapshot; `.kingfisher.env` bleibt getrennt,
denn nur ihre Passphrase kann die darin gesicherten lokalen Geheimnisse später
entschlüsseln. Vorhandene Snapshots zeigt `make backups`.

`.kingfisher.env` nicht löschen oder weitergeben. Darin stehen der lokale
Sitzungsschlüssel und die Passphrase für verschlüsselt gespeicherte Geheimnisse.
Die Datei gehört nicht in eine Sicherung auf GitHub und muss getrennt sicher
aufbewahrt werden.

## Wenn etwas klemmt

- Docker startet nicht: Docker Desktop öffnen und danach `make start` erneut
  ausführen.
- Die Seite lädt nicht: `make url` ausführen und die Adresse frisch öffnen;
  bei Bedarf `make logs` verwenden.
- Der Notizordner fehlt: `make quellen` prüfen, dann nach einer Änderung
  `make start` ausführen. Docker Desktop muss Zugriff auf den ausgewählten
  Ordner haben.
- Der Import meldet keinen Zugriff: Erst den Ordner freigeben, danach neu
  starten und anschließend `make notizen-importieren` wiederholen.

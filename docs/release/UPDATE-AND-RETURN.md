# Update und Rückweg auf dem Mac

## Vor einem Update

In Kingfisher unter Einstellungen die vollständige Sicherung öffnen, ein
Sicherungspasswort vergeben und „Verschlüsselt sichern“ ausführen. Erst nach
der Erfolgsmeldung fortfahren. Das Paket und sein Passwort werden für einen
Rückweg benötigt. Änderungen nach dieser Sicherung sind darin nicht enthalten.

Neue Sicherungen führen die genaue App-Version verschlüsselt mit. Das lokale
Image während der Erprobung behalten: Die Sicherung enthält die Versionskennung,
nicht das vollständige Docker-Image. Für ältere Pakete ohne Versionsangabe
die bisherige Image-ID im technischen Updateablauf festhalten
(`docker inspect --format '{{.Image}}' CONTAINER`). Ein veränderlicher
Image-Name allein ist kein verlässlicher Versionsnachweis.

## Bei einem Problem

Der normale Wiederherstellungsstarter öffnet eine separate App aus der
Sicherung und verwendet ihre gespeicherte lokale App-Version. Bei älteren
Paketen ohne Versionsangabe bleibt die Version des angegebenen Containers
der Ausgangspunkt. Die bisherige Instanz und ihr Datenbestand werden nicht ersetzt.
Danach Modellwahl, vorhandene Gespräche, Aufgaben, Ziele und Quellen prüfen
und eine neue Antwort testen, bevor mit der wiederhergestellten App weiter
gearbeitet wird.

Wenn ausdrücklich eine frühere App-Version gebraucht wird, unterstützt der
technische Starter jetzt eine lokale Image-ID:

```sh
python3 scripts/restore_recovery_bundle.py --image IMAGE_ID --open-app
```

Der Dateidialog fragt nach dem Sicherungspaket, anschließend wird das Passwort
verdeckt eingegeben. Ohne `--image` bleibt der bisherige Aufruf mit
`--container CONTAINER` gültig. Bei beiden Angaben hat `--image` Vorrang.
Ein fehlendes lokales Image führt zu einem Fehler; es wird nicht automatisch
heruntergeladen. Die ausgewählte Version wird vor dem Wiederherstellen auf
eine unveränderliche ID aufgelöst und auch für die separate App verwendet.

## Grenzen des aktuellen Nachweises

Dies stellt einen gespeicherten früheren Bestand wieder her. Es migriert keine
nach dem Update hinzugekommenen Daten zurück. Eine beliebige alte Version kann
neuere Datenformate möglicherweise nicht lesen; daher eine zur Sicherung
passende Version verwenden. Fehlt die gespeicherte Version auf dem Mac, bleibt der entschlüsselte
Ordner erhalten und die App wird nicht mit einer anderen Version gestartet.
Ein automatischer Image-Download findet nicht statt. Der konkrete Aufgaben-Schema-Rückweg und der vollständige Update-/Rückkehrablauf sind inzwischen geprüft (ACCEPTANCE-50-PERCENT.md, Roadmap 19 erfüllt). Ein automatischer Updater und beliebige andere Schemawechsel sind damit nicht zugesagt.

## Geprüfter Schema-Rückweg

Ein Integrationstest sichert ein echtes altes Aufgabenschema ohne project_id
zusammen mit einem Gespräch und der Schlüsselkonfiguration. Der aktuelle
TaskStore migriert es, anschließend wird eine neue Aufgabe erfasst. Die
verschlüsselte Sicherung stellt in einem neuen Ordner das ursprüngliche
Schema und seine Daten wieder her. Das erneute Öffnen kann regulär migrieren;
der neuere Ausgangsbestand einschließlich neuer Aufgabe bleibt erhalten.
69 gezielte Migrations-/Paket-/Versionsauswahltests bestanden. Dieser Nachweis
deckt den konkreten Aufgaben-Schemawechsel ab, nicht jede denkbare Migration
aller übrigen Stores.

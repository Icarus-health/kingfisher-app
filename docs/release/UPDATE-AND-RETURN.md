# Update und Rückweg auf dem Mac

Aktualisiert am 7. Oktober 2026: Ein wiederhergestellter Bestand startet nur zur historischen Einsicht. Die Sicherung erhält Daten und verschlüsselte Konfiguration, übernimmt aber keine heutige Aktionsfreigabe.

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
Danach vorhandene Gespräche, Aufgaben und Quellen in der historischen Einsicht prüfen. Modelle, Verbindungen, Zeitpläne und Schreibaktionen bleiben ausgeschaltet; eine neue Modellantwort lässt sich in diesem Zustand nicht anfordern. Spätere Korrekturen oder Quellenentzüge können im älteren Sicherungsstand fehlen. Einzelne Originale lassen sich nach ausdrücklicher Prüfung über die normale Aufnahme einer aktuellen Instanz erneut einbringen. Es gibt keine pauschale Reaktivierung alter Freigaben.

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
Ein automatischer Image-Download findet nicht statt. Der konkrete Aufgaben-Schema-Rückweg und der vollständige Update-/Rückkehrablauf sind inzwischen geprüft (ACCEPTANCE-50-PERCENT.md, Roadmap 19 erfüllt). Diese früheren Prüfungen allein belegen weder beliebige andere Schemawechsel noch die native Bedienung des heutigen Updaters.

## Geprüfter Schema-Rückweg

Ein Integrationstest sichert ein echtes altes Aufgabenschema ohne project_id
zusammen mit einem Gespräch und der Schlüsselkonfiguration. Der aktuelle
TaskStore migriert es, anschließend wird eine neue Aufgabe erfasst. Die
verschlüsselte Sicherung stellt in einem neuen Ordner das ursprüngliche
Schema und seine Daten wieder her. Der direkte TaskStore-Test kann die alte Datenbank erneut regulär migrieren. Das ist keine operative Freigabe der wiederhergestellten App: Dort bleibt die historische Einsicht aktiv. Der neuere Ausgangsbestand einschließlich neuer Aufgabe bleibt erhalten.
69 gezielte Migrations-/Paket-/Versionsauswahltests bestanden. Dieser Nachweis
deckt den konkreten Aufgaben-Schemawechsel ab, nicht jede denkbare Migration
aller übrigen Stores.

## Anschlussprüfung für 1.0.6

Bestätigte/ersetzte Wissensaussagen, offene konkurrierende Rückfragen, Quellenentzug, Aufgabenfrist, Wartestatus und genaue Wiedervorlagezeit wurden gemeinsam über Neustart und verschlüsselten Export in ein neues Wiederherstellungsziel geprüft. Der künstliche verschlüsselte Anbieterzugang bleibt mit seiner Konfiguration erhalten, wird beim Start der historischen Einsicht aber nicht geladen. Alte Aufgaben- und Wissensaktionen werden mit 423 abgewiesen. Der persönliche Pilot wurde dafür nicht verändert. Nachweise und offene Mac-Bedienprüfung: [Kernablauf](../runs/2026-10-07-core-workflow/README.md).

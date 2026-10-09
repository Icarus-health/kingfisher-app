# Große Gedächtnisbereiche: synthetischer Kapazitätsnachweis

9. Oktober 2026, Basis `e7033f55635bddc7439c127decc092ae4d8bb789`. Messkern und ausgeführter Treiber: `76273e0`. Danach ausschließlich die CLI-Dateigrenzenbehandlung explizit gehärtet, keine Änderung am Messkern, Korpus oder Ergebnis. Keine Produktmodule verändert und keine persönliche App installiert.

## Was tatsächlich ausgeführt wurde

Die echten `EpisodeStore.record`, Kategorien-Persistenz und `MemoryAreas.page` werden auf einer temporären Datenbank ausgeführt. 100.000 künstliche Quellen mit je 2.048 Zeichen, fester Quellzeit 2020 und kontrollierten Arbeitskategorien; die ältesten 31 Quellen haben eine explizite Gesundheitskorrektur. Keine privaten Texte, Provider, Modelle oder Netzwerkaufrufe. Die Kategorien sind feste Testvorgaben, keine gemessene KI-Einordnung.

Gemessen werden die Bereichsprojektionen direkt; der HTTP-/Browser-/Containertransport ist nicht enthalten. Je Ansicht drei Wiederholungen, Median in der Tabelle. Die ältesten Gesundheitsquellen und ihre zweite Seite stimmen exakt mit der Sollreihenfolge überein. Nach Quellenentzug fehlt genau die entzogene Quelle. Alle Seitenabrufe lassen die Anzahl der SQLite-Schreibänderungen unverändert.

| Quellen | Alle, 25 Zeilen | Arbeit, 25 Zeilen | Gesundheit, ältere Quellen | Finanzen, tatsächlich leer | Weitere, begrenzt leer |
|---:|---:|---:|---:|---:|---:|
| 10.000 | 0,012 s | 0,015 s | 0,066 s | 0,055 s | 0,205 s |
| 100.000 | 0,012 s | 0,015 s | 0,637 s | 0,665 s | 0,211 s |

„Weitere“ prüft 500 Kandidaten und liefert eine leere Seite **mit Fortsetzung**. Es behauptet keinen leeren Gesamtbestand. Der Finanzkandidatenscan findet dagegen keine passenden Quellen. Die Abfrage kann alle Quellen strukturell durchlaufen; das Projektionsbudget begrenzt nicht die gesamte SQL-Arbeit.

Prozess-RSS-Spitze 45.056.000 Bytes (etwa 43 MiB), über Aufbau und Abfragen insgesamt. Kein Gesamt-RAM-/GPU-/Mac-Cache-Messwert. Datenbank samt Journalen bei 100.000 Quellen 1.257.668.608 Bytes, etwa 1,26 GB; zusätzliche Vektorcaches und Originalanhänge sind nicht enthalten. Die kumulierten 114,09 Sekunden enthalten kontrollierten Aufbau und frühere Abfragen. Transaktionen bündeln bis zu 250 Quellen; dieser Aufbau ist kein normaler Postfach-/Modell-Importdurchsatz. Betriebssystemcache wurde nicht geleert.

## Fehler und daraus verbesserter Treiber

Der erste vollständig kategorisierte Großlauf scheiterte am künstlichen 1-GiB-Dateilimit mit SQLite `OperationalError: disk I/O error`; er ist kein Kapazitäts-Green. 23,9 GB freie Hostbytes und ein kleiner synthetischer Gegenlauf mit empfangenem `SIGXFSZ` reproduzieren den Dateilimitmechanismus. Der erfolgreiche Lauf misst eine größere Datei als dieses alte Limit. Der begrenzte Treiber verwendet jetzt 2 GiB pro Datei und 180 CPU-Sekunden ausschließlich für den eigenen Testprozess.

Ein früher Prototyp erwartete fälschlich, dass die leere „Weitere“-Seite schon einen leeren Bestand beweist. Die Erwartung wurde an den bestehenden 500-Kandidaten-Vertrag angepasst; kein Produktverhalten gelockert. Vollständige Rohprotokolle bleiben lokal erhalten.

Der finale CLI-Treiber erstellt Berichte exklusiv, überschreibt keine vorhandenen Dateien und sichert abgeschlossene Messpunkte. Catchbare Fehler erzeugen `failed` mit Fehlerklasse ohne interne Ausnahmetexte. `SIGXFSZ` wird ausdrücklich ignoriert, sodass Dateigrenzen als I/O-Fehler behandelbar bleiben; der gemessene Python-Interpreter tat dies bereits standardmäßig. Eine harte Prozessbeendigung, etwa CPU-Kill, kann einen `running`-Bericht zurücklassen: dieser ist niemals ein bestandener Lauf. Ungewöhnlich große erlaubte Kombinationen können an der Testgrenze scheitern; die Eingabegrenzen versprechen keinen erfolgreichen Durchlauf.

## Reproduktion und Prüfungen

```sh
PYTHONPATH=sidecar python scripts/probe_memory_area_scale.py --sizes 10000,100000 --body-chars 2048 --output /tmp/new-memory-area-report.json
```

Nur auf einem Rechner mit ausreichendem temporärem Speicher ausführen; eigene temporäre Datenbank, keine vorhandenen Datenpfade. CLI nutzt Unix-Prozessgrenzen. Keine Modellausgaben oder kostenpflichtigen Zugänge erforderlich. `measurements.json` enthält den unveränderten erfolgreichen Lauf.

21 betroffene Tests bestanden, davon 10 Treibertests: seltene alte Quelle, Fortsetzung, Rücknahme, Eingabegrenzen, Überschreibschutz und Fehlercheckpoint; vorhandene Bereichsregressionen unverändert. Unabhängige begrenzte Prüfung des Treibers; korrigierte Zeitfeldbezeichnung und Dateigrenzenbehandlung. Kein Gesamtbackend- oder UI-Neubau nötig: Produktcode unverändert.

## Produktgrenze

Dieser Nachweis erweitert die bisherige Vektor-Eignungsmessung um einen echten Bereichs-/Kategorien-Leseweg. Er belegt weder vollständige Mailaufnahme, richtige Personenextraktion, semantische Antworten, ausreichende Docker-Kapazität noch einen flüssigen ganzen Arbeitstag. Persönlicher Import bleibt pausiert und produktive Modelle aus. Der aktuelle vollständige Ziel-/Abnahmestand steht in [64 · CoS-Abnahme](../../64-cos-abnahme-status-2026-10-09.md). Kalenderfreigabe und Fenstertest bleiben ausdrücklich offen.

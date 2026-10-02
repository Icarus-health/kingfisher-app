# Testplan für den Mac

Stand: 27. September 2026. Für den ersten Test des integrierten Stands
**#71–#109 einschließlich der unabhängigen Dokumentation aus #103** auf dem
Mac am 28. September mit echtem Postfach, lokalem Modell (`qwen3.5:4b`) und
optional `bge-m3`.

Die Containerprüfung verwendet synthetische Quellen und Modellattrappen.
Sie ersetzt weder die Qualität und Geschwindigkeit des echten Modells noch
Mac-Kalenderberechtigungen, Keychain oder den nativen Desktop-Build.

## 1. Geprüften Gesamtstand verwenden

Nicht mehr #102 allein zusammenführen: Seitdem sind #103–#109 hinzugekommen.
Der Integrationsstand enthält die vollständige Kette bis #109, die separate
Dokumentation aus #103 und die Korrekturen aus der Gegenprüfung vom
27. September. Die ursprüngliche Reihenfolge bleibt in der Git-Abstammung
erhalten. Nach dem Integrations-Merge genügt ein Update von `main`.

| enthalten | Inhalt |
| --- | --- |
| #71–#102 | Gedächtnis, Berichtigung, Rückfragen, optionale Bedeutungssuche, Projektzuordnung, Sicherung, Aufgabenhinweise, Einrichtungs- und Anzeigeverbesserungen |
| #103 | Produktweg zum Stabschef und Konzeptprüfung des Gedächtnisses |
| #104–#105 | vollständige Bestandsansichten und Klärung mehrdeutiger Suchbegriffe |
| #106–#107 | Projektmappen und quellengestützte Gespräche darüber |
| #108–#109 | Terminvorbereitung und Nachbereitung mit Quellen und Vorschlägen |
| Integrationskorrekturen | Quellenentzug, Antwortaktualität, Berichtigung, getrennte Terminidentitäten, Bedienung ohne Modell, Formularschutz und Kontrast |

Details und nächste Schritte: [Integrationsprüfung](INTEGRATION-2026-09-27.md).

## 2. Update starten

```sh
git pull
make start
```

Beim ersten Start nach dem Update baut Kingfisher die Gedächtnis-Datenbank um
(von Version 8 auf 10). **Vorher legt es selbst eine vollständige Sicherung
an**, `sicherungen/vor-update-…` im Datenvolume. `make backups` zeigt sie. Nichts
muss neu eingeordnet werden; Suche, Projektzuordnung und Aufgaben bleiben.

Wer zusätzlich eine verschlüsselte Sicherung außerhalb des Volumes möchte:
`docs/release/UPDATE-AND-RETURN.md`, Abschnitt „Vor einem Update“.

## 3. Modell verbinden und Einordnung starten

1. Einstellungen → Verbindungen → Lokale KI. `qwen3.5:4b` ist vorausgewählt,
   wenn es installiert ist. „Speichern und verbinden“.
2. Direkt darunter fragt Kingfisher, ob es die Quellen jetzt einordnen soll.
   „Einordnung starten“.
3. Gedächtnis → Verarbeitung & Verlauf zeigt, wie viele Quellen eingeordnet
   sind, und nach zwei Durchgängen eine Restzeit.

**Notieren:** Wie viele Quellen, wie lange bis fertig. Daraus ergibt sich die
Sekundenzahl je Quelle für Schritt 5.

## 4. Durchklicken

Jede Zeile ist ein Klickweg mit dem, was zu sehen sein sollte. Was davon
abweicht, bitte mit Bildschirmfoto festhalten.

| Wo | Was tun | Erwartung |
| --- | --- | --- |
| Gespräche | ohne Gespräche öffnen | Hinweis und Knopf „Neues Gespräch beginnen“ |
| Gespräch | nach etwas fragen, das in einer Mail steht | Antwort mit Quelle, Absender und lesbarer Zeit; neueste Quelle zuerst |
| Gespräch | Frage mit mehreren passenden Personen | Rückfrage mit Knöpfen, ein Klick beantwortet |
| Gespräch | „Was kam letzte Woche zu …?“ | „Zuerst berücksichtigt: Quellen …“ |
| Quelle ansehen | Projekt zuordnen | sofort gespeichert, mit Bestätigung; bei weiteren Mails desselben Absenders ein Angebot, sie mitzunehmen, mit „Rückgängig“ |
| Gespräch | „Was gibt es Neues zu ‹Projekt›?“ | findet zugeordnete Quellen auch ohne das Wort; „Zugeordnet: Projekt …“ |
| Gespräch | nach einer Antwort eine neue passende Mail aufnehmen | alte Antwort gilt als veraltet, „Mit aktuellem Stand neu beantworten“ |
| Heute → Braucht dich | nach der ersten Zusagenerkennung | „Vorschlag aus einer Mail von …“ mit „Als Aufgabe übernehmen“ und „Prüfen“ |
| Nachrichten → Antwort vorschlagen | bei einer Mail | Quellen nur von diesem Absender |
| System auf dunkel | alle Seiten | lesbar, nichts Weißes |

### Zusätzliche Abnahme des integrierten Stands

Für diese Schritte ein kleines **Testprojekt mit Testquellen** verwenden.

| Fall | Erwartung |
| --- | --- |
| Ohne verbundenes Modell „Erzähl mir was zu ‹Projekt›“ fragen | vorhandene Projektmappe erreichbar; Mehrdeutigkeit per Auswahl klärbar; freie Modellfragen benennen das fehlende Modell |
| Zusage zu „Diese Zusage gilt nicht mehr: …“ berichtigen | alte Zusage nicht mehr als unverändert aktiv; gesamter geänderter Kontext bleibt erkennbar |
| Nach gespeicherter Antwort eine passende, anders formulierte Quelle aufnehmen | alte semantische Auswahl wird als überholt erkannt; neue Antwort kann neu berechnet werden |
| Kalender in der Suche verwenden, dann abwählen | auch zwischengespeicherte Treffer und Ergebnisse eines alten Abrufs verschwinden |
| Zwei Termine mit gleichem Titel und Beginn, aber unterschiedlichen Kennungen nachbereiten | getrennte Quellen mit eigenen Teilnehmern/Projekten; Wiederholung derselben Notiz erzeugt keine Dublette |
| Nachbereitung öffnen, sofort Projekt ändern | verspäteter Vorschlag überschreibt die Wahl nicht |
| Nachbereitung speichern | Text, Projekt und Dateiauswahl während des Speicherns gesperrt; gespeicherte Quelle prüfen; Ergänzung bleibt eigene Quelle |
| Modell verbinden, danach Auswahl ändern, noch nicht speichern | kein Angebot, mit dem ungespeicherten Modell loszulegen |
| Gedächtnislauf mit übersprungenen Quellen | Abschluss behauptet nicht, alle Quellen seien eingeordnet |
| Kalender in hell/dunkel, Fenster ab 1280 px | lesbare Umschalter und bedienbare Liste; Smartphone-Breite wird derzeit nicht unterstützt |

Die bestehende
Sicherung vor dem Update prüfen, bevor mit echten Daten gearbeitet wird.

## 5. Messen

Einmal die Python-Umgebung auf dem Mac anlegen (ohne Docker, für die Skripte):

```sh
make sidecar-dev
```

**Modelle vergleichen** (nur synthetischer Katalog, keine eigenen Daten):

```sh
.venv/bin/python scripts/probe_working_memory_models.py \
  --arm ollama:qwen3.5:4b \
  --output docs/evaluations/memory-quality/models/mac-$(git rev-parse --short HEAD).json
```

Weitere installierte Modelle als zusätzliche `--arm` angeben. Die Ausgabe
nennt je Modell richtige Einordnungen, richtige Auswahl und **Sekunden je
Aufruf**.

**Großes Postfach hochrechnen** mit der gemessenen Sekundenzahl je Quelle
(aus Schritt 3 oder dem Modellvergleich):

```sh
.venv/bin/python scripts/probe_working_memory_scale.py --sekunden-je-quelle 12 \
  --output docs/evaluations/memory-quality/scale/mac-$(git rev-parse --short HEAD).json
```

**Bedeutungssuche** mit `bge-m3`:

```sh
.venv/bin/python scripts/probe_working_memory_paraphrase.py --embedder bge-m3 \
  --output docs/evaluations/memory-quality/paraphrase/bge-m3-$(git rev-parse --short HEAD).json
```

## 6. Was die Zahlen entscheiden

| Messung | Schwelle | Folge |
| --- | --- | --- |
| Modellvergleich, Auswahl | weniger als 8 von 10 richtig | anderes lokales Modell prüfen, bevor echte Fragen bewertet werden |
| Erste Einordnung, hochgerechnet | mehr als eine Nacht | Einordnung auf die letzten Monate begrenzen (eigener PR) |
| Bedeutungssuche, Arm „produktiv“ | mindestens 12 von 16 Umschreibungen, direkte 16 von 16 | `ICARUS_MEMORY_SEMANTIC=1` in `.kingfisher.env`, `make start` |

Die Ergebnisdateien bitte einchecken; sie werden nie überschrieben.

## 7. Wenn etwas hakt

- `make logs` zeigt, was der Sidecar sagt.
- Zurück zum Stand vor dem Update, während Kingfisher läuft:
  `make zurueck-vor-update`. Der jetzige Stand wird beiseitegelegt, nicht
  gelöscht; Kingfisher öffnet den alten Stand zuerst in der Prüfansicht. Wer
  danach mit dem alten Programm weiterarbeiten will: `git checkout` auf den
  Stand vor dem Merge und `make start`.
- Die verschlüsselte Sicherung außerhalb des Volumes bleibt der Weg für einen
  verlorenen Rechner: `UPDATE-AND-RETURN.md`.
- Einordnung pausieren: Gedächtnis → Verarbeitung & Verlauf.

# Eine Bedingung nach der Abnahme darf nicht verschwinden

## Ausgangslage und vollständiger Gedächtnisweg

Der unveränderte Stand `3cf769f` durchläuft mit zehn künstlichen Originalen die tatsächliche Dokumentaufnahme per HTTP, den lokalen Einordnungsworker, Kategorienvorschläge, den dauerhaft gespeicherten bge-m3-Index und acht Gesprächsfragen im Modus `memory_evidence`. Die Speicher und der Suchdienst werden vor den Fragen geschlossen und neu geöffnet. Quellen werden nicht direkt an die Satzgenerierung vorbeigeschleust; es gibt keine manuell bestätigten Aussagen, Projektzuordnungen oder Überholungslinks. Automatisches UI-Routing und echte persönliche Modellrollen sind damit nicht abgenommen.

Die unabhängige Inhaltsprüfung bewertet die sichtbaren Antworten gegen die eingefrorenen Originale: fünf ausreichend, drei unvollständig, keine unbelegte Aussage. IA01 und IA03 zeigen sichere Originalzitate statt einer direkten Antwort. IA07 wählt diesmal nur die neuere Korrektur und beantwortet die Frage richtig. Die Aktenkontexte sind jedoch leer; daraus folgt keine allgemeine Überholungs-/Beziehungsgarantie.

IA08 reproduziert den Fehler auch über den vollständigen Weg: Der Satz mit der schriftlichen Anordnung **nach** der Abnahme wird wegen eines Verbots **bis** zur Abnahme abgelehnt. Sichtbar bleibt nur das Vorher-Verbot. Die vorhandene Prüfung verlor diese Bedingung auch innerhalb derselben Quelle.

Die automatische Auswahlmetrik ist ausdrücklich diagnostisch. Bei IA02 fehlt zwar eine erwartete Quelle in der Auswahl, aber die ausgewählte zweite Quelle enthält die Voraussetzung selbst ausdrücklich; die sichtbare Antwort ist ausreichend. Quellenidentität allein ist kein Qualitätsmaß.

Produktcode: `ae1e2ec20f7eb963a85989ab6d637b79929dabfa`.

## Korrektur und Grenzen

Die Korrektur trennt nur eine vollständige wörtliche bedingte Erlaubnis nach einer ausdrücklich identischen Grenze von einem Verbot, das ausdrücklich bis zu dieser Grenze gilt. Sie darf weder andere Quellenverbote noch Verbote im selben Zeitfenster überstimmen. Die bestehende passive Bedingungsgrammatik bleibt erhalten. Zusätzlich werden die engen Formen „ist/sind (nur) zulässig/gestattet/erlaubt, wenn …“ für den wörtlichen Bedingungsschutz und für die Vollständigkeit nach einer Satzverwerfung erkannt.

Lehnt das Modellprüftor die notwendige Regel ab, werden Originalstellen statt einer scheinbar ausreichenden Teilantwort gezeigt. Derselbe Schutz gilt bei erneuter Anzeige gespeicherter Antworten. Beliebige Sprache, Kausalität, zeitliche Logik und Vollständigkeit werden dadurch nicht allgemein bewiesen. Aus einer bedingten Erlaubnis folgt weder eine vorhandene Anordnung noch eine ausgeführte Handlung.

## Laufgrenzen

Ausschließlich künstliche Quellen und bereits vorhandene lokale qwen3.5:4b/bge-m3-Gewichte. Eigener Server auf 11439, Cloud deaktiviert, keine Downloads und keine produktive Quellenverarbeitung. Der Diagnosepfad entlädt nach vier Paketen; die RAM-Stichprobe mit Notstopp ist keine harte GPU-/Speichergrenze oder Akkuabnahme. Vorheriger Lauf: eigener Client und Server jeweils mit Exit 0 beendet. Originale erhalten und Quellenentzug nach Wiederöffnung wirksam.

## Nachweise

- `catalog.json`: dieselben zehn Originale und acht vorab festgelegten Fragen.
- `before-answers.json`, `before-runtime.json`, `before-content-review.json`: unveränderte Baseline einschließlich Original-/Code-Hashes und unabhängiger Prüfung.
- `after-answers.json`, `after-runtime.json`, `after-content-review.json`: vollständiger Nachherlauf und unabhängige Prüfung; `comparison.json` trennt Textinhalt von tatsächlich unterschiedlichen Erfassungszeiten.
- `affected-tests.txt`: 366 betroffene Prüfungen bestanden, darunter 23 neue Regressionen. Eine bestehende Starlette-Deprecation-Warnung. Keine Vollsuite oder neue UI-Abnahme behauptet.
- `disabled-guards.txt`: Nur die neuen Schutzfunktionen im Testprozess deaktiviert; sieben Tests scheitern wieder, 16 Sicherheitskontrollen bestehen. Keine Produktionsdatei wurde dafür zurückgesetzt.
- `code-review.json`: 23 unabhängige Gegenproben und 23 fokussierte Tests auf eingefrorenen Dateihashes; kein offener Blocker im beschriebenen Bereich. Zwischenfehler bei koordinierten Fremdgrenzen, verkürzten Erlaubnissen und qualifizierten Ereignissen wurden vor Lieferung korrigiert.
- `expected.json`, `package-smoke.jsonl`, `installed-hashes.json`: exakte 3cf769f-Basis mit zwei ersetzten Pythonquellen und Versionsmetadaten; 264 Python- und 112 UI-Dateien geprüft. Netzloser Pakettest umfasst Vorgangsbindung, Bedingungen, Originalfassungen, alte Antworten und Quellenentzug. Kein neuer Abhängigkeitsinstallationslauf.
- `installation-result.json`, `models-stopped.json`: tatsächlich laufendes Mac-Backend, Datenerhalt, globale Pause und beendete Modellprozesse.

## Ergebnis und Mac

Die unabhängige Prüfung steigt in diesem begrenzten Acht-Fragen-Lauf von **fünf auf sechs ausreichende Antworten**; IA08 enthält nun die vollständige schriftliche Anordnung nach der Abnahme. Die übrigen sieben Antworten sind inhaltlich unverändert (die neu aufgenommenen Zitatquellen tragen naturgemäß neue Erfassungszeiten). IA01 und IA03 bleiben sichere Zitat-Rückfälle ohne direkte Antwort. Keine unbelegte Aussage in diesen acht Antworten, aber keine allgemeine Fehlerfreiheitsgarantie.

Nach tatsächlichem Schließen und Wiederöffnen aller Speicher bleiben alle acht Antworten unverändert und benötigen keine Modellaufrufe. Quellenentzug nach Wiederöffnung sperrt die betroffene Antwort; das Original bleibt erhalten. Der Nachherlauf dauert etwa 101 Sekunden, Stichprobenmaximum rund 6,1 GiB Prozess-RSS. Das ist keine vollständige GPU-/RAM-Messung und kein Akku-Alltagstest.

Installiert und byteweise nachgeprüft: **1.0.6-local.ae1e2ec**. 344 Original-IDs/Digests, 17 SQLite-Dateien, Konten, Modellrollen, Zeitplan und Datenvolume erhalten. Native Programmdatei und strikte Signatur unverändert. Kalte Rückwegsicherung unter `Kingfisher-Rueckweg/2026-10-09-vor-ae1e2ec-geprueft`. Persönlicher Import bleibt pausiert, produktives Ollama aus; Bedeutungsdienst deshalb `unavailable`. Native Fenster-, Tages- und Akkubedienung bleiben wegen des gesperrten Macs offen.

Als Nächstes unnötige Zitat-Rückfälle ohne gelockerte Belegprüfung reduzieren und die tatsächliche Quellen-/Einordnungsabdeckung sowie den normalen Mac-Alltag abnehmen. Dieser Nachweis qualifiziert weder den großen persönlichen Postfachbestand noch automatische Aktenbeziehungen oder einen fertigen CoS.

# Unabhängige Gedächtnisprobe: lokaler Lastabbruch

**Ergebnis: keine bewertbare Modellantwort.** Der echte lokale Versuch mit
Qwen9B wurde am 04.11.2026 nach 3,1 Sekunden wegen Speicherdruck gestoppt.
Die technischen Schutzgrenzen haben gegriffen; Personen-, Aufgaben-, Fristen-
und Abrufqualität sind damit weder bestanden noch inhaltlich durchgefallen.

## Vor dem Lauf festgelegt

- Zehn eigenständig formulierte künstliche Mails, fünf Fragen und vier erwartete
  eigene Aufgaben. Alle Adressen sind fiktive `.example`-Adressen.
- Getrennte Quellen und semantische Erwartungen. Ein unabhängiger Review
  korrigierte vor dem Lauf eine zu strenge Identitätsannahme: zwei Adressen mit
  gleichem Namen beweisen nicht zwei verschiedene Menschen. Die Antwort darf
  nachfragen oder beide Adressen mit eindeutigem Kontext nennen.
- Die gesendete Zusage trägt ausdrücklich den Ordner `Sent`. Tagesfrist und
  belegte Uhrzeit bleiben in der Bewertung verschieden.
- [Pilot v1](../../fixtures/memory-acceptance-20261104/pilot-v1/README.md) bleibt
  unverändert erhalten. Der tatsächlich verwendete
  [Pilot v2](../../fixtures/memory-acceptance-20261104/pilot-v2/README.md) wurde
  vor dem Lauf samt Referenzantworten per SHA-256 eingefroren.
- Maximal 60 Modellaufrufe und 600 Sekunden; diese technischen Obergrenzen
  sind keine Cloudfreigabe. Großimport bleibt immer gesperrt.

## Tatsächlich ausgeführt

Code: `09bd4af7a501bd13dc465911a0d87e88d89791ce`. Der vorhandene
`probe_mail_intake_quality.py`-Ablauf verwendet echte Aufnahme-, Aufgaben- und
Gesprächspfade; nur der Mailtransport ist künstlich. Der archivierte
[Wrapper](local-runner.py) bindet genau den eingefrorenen Pilot und vorhandene
Qwen-Gewichte. Seine absoluten temporären Pfade dokumentieren den historischen
Aufruf; er ist kein portables Installationsskript.

Modell: `kingfisher-qwen3.5:9b-8k`, Digest
`8a5919e3ddda74b7729b65ca0bad9896d36615d872756ca98b17ec8a80374b17`.
Dies ist der begrenzte native 8K-Diagnosetransport, keine Abnahme des installierten
App-Transports. BGE-M3 war für den späteren Suchschritt vorgesehen, wurde aber
noch nicht aufgerufen.

| Seit Beginn | macOS-Speicherdruck | Gemeldete freie Reserve |
|---|---:|---:|
| 0,0 s | 2 | 43 % |
| 1,0 s | 2 | 43 % |
| 2,0 s | 2 | 36 % |
| 3,1 s | 4 | 21 % |

Der Wächter beendete ausschließlich den eigenen Prüfarbeitsprozess. Keine
anderen Programme wurden geschlossen. Danach zeigte Ollama keine geladenen
Modelle mehr; die gemeldete Reserve lag bei 49 %. Unter unveränderten Bedingungen
wurde kein weiterer Versuch gestartet und keine Schutzgrenze gelockert.

[Unveränderter Laufbericht](local-attempt.json) und [Prüfquittung](validation.json)
enthalten die Nachweise. `model_calls: 1` zählt einen gestarteten Aufruf;
`model_seconds: 0` ist das leere Aggregat abgeschlossener Antworten, keine
gemessene Antwortzeit. Keine der fünf Fragen wurde beantwortet. Anlagen,
Quellenänderung und -entzug wurden in diesem Versuch noch nicht geprüft.

## Mistral-Vorschau ohne Anbieteraufruf

Der neue [Pilothelfer](../../../scripts/probe_mistral_memory_pilot.py) nimmt
dieselben zehn Mails über den echten Mailleser und die Aufnahme auf. Nur der
IMAP-Transport ist künstlich. Er bereitet den bestehenden Mistral-Quellenauftrag
mit `include_tasks=True` vor: Einordnung, Personen/Kategorien, Aufgabenextraktion
und semantische Gegenprüfung. Keine vorgegebenen Klassifikationen werden geladen.

Aus dem Repository, mit installierten Sidecar-Abhängigkeiten:

```sh
PYTHONPATH=sidecar:scripts:. python scripts/probe_mistral_memory_pilot.py --output /private/tmp/kingfisher-mistral-pilot-vorschau.json
```

Der Ausgabepfad muss neu sein. Ohne `--run` bleibt es auch bei vorhandenen
Umgebungsvariablen bei einer Vorschau. Ein tatsächlicher Lauf verlangt zusätzlich
eine ausdrückliche künstliche Datenfreigabe, einen eigens übergebenen
Test-API-Schlüssel und ein gewähltes Kostenlimit von höchstens 1 USD. Dieser
Bericht erteilt diese Freigabe nicht. Gespeicherte App-Schlüssel werden nicht
gelesen; persönliche App-Verzeichnisse sind keine Eingabe dieses Werkzeugs.

Die [wirklich ausgeführte Offline-Vorschau](mistral-offline-preview.json) enthält
zehn Quellen, null HTTP-Aufrufe, keine angelegten Aufgaben und unveränderte
Originale. Die geplante Obergrenze beträgt 50 Inferenzanfragen; der Laufdeckel
umfasst höchstens 60 HTTP-Aufrufe einschließlich Metadatenabruf und 600 Sekunden.
Das gewählte Budget ist leer. Abruffragen sind ausdrücklich `not_run`.

46 neue Werkzeugtests und die unveränderten 31 Tests der älteren Quellenprobe
bestehen im finalen Lauf (77 Tests). Vor der letzten eng begrenzten
Deadlinekorrektur bestand außerdem eine Gruppe von 173 betroffenen Tests
einschließlich Cloud-Aufgaben, Anbieter und Jobs. Alle Anbieterantworten waren
simuliert; diese Zahlen bescheinigen keine Mistral-Qualität. Der
unabhängige Review und drei eng begrenzte Korrekturrunden sind dokumentiert.
Die [Abschlussprüfung](memory-pilot-round3-review.md) führt alle Befunde als
behoben; der Code-Review bestätigt weiterhin keine echte Modellqualität.

Vorbereitung, Anfragezulassung und HTTP-Warten teilen ein absolutes Zeitbudget.
Nach einem Timeout wird ein spätes Ergebnis nicht mehr übernommen. Eine beim
Anbieter bereits gestartete Anfrage kann trotzdem weiterlaufen und Kosten
verursachen; unklare Nutzung bleibt deshalb mit dem reservierten Höchstbetrag
offen. Ein serverseitiger Abbruch wird nicht behauptet. Beliebig blockierende
lokale Dateisystemoperationen haben keinen Betriebssystem-Wächter. Fehlende oder
geänderte Originale und nicht lesbare Abrechnungsfelder werden einzeln berichtet,
statt die gesamte Kostenquittung zu verlieren.

## Was als Nächstes sinnvoll ist

Die gleiche kleine Quellenmenge wird für den vorhandenen, ausdrücklich begrenzten
Mistral-Weg vorbereitet. Er soll Quelleinordnung **und** Aufgabenextraktion mit
Gegenprüfung erfassen. Die ältere Sieben-Quellen-Probe ohne Aufgaben darf dafür
nicht als Ersatznachweis verwendet werden. Abrufqualität braucht danach einen
eigenen tatsächlichen Lauf.

Ohne Mistral-Schlüssel und konkret gewähltes Budget bleiben alle Cloudaufrufe
gesperrt. Eine Vorschau oder simulierte Anbieterantwort ist kein Qualitätsbeleg.
Ein gesonderter größerer Prüfungssatz bleibt bis zu seiner Freigabe unbenutzt.
Weder dieser Pilot noch ein späterer technischer Erfolg aktiviert den Großimport.

Die vorhandenen 65 Tests des Diagnoseablaufs bestanden. Sie prüfen die
Messmechanik und ersetzen keine ausgefallene Modellantwort. Persönliche Daten,
App-Einstellungen, Konten und der pausierte Großimport wurden nicht verändert.

## Getrennte CI-Korrektur

Der vollständige CI-Lauf am vorherigen Code `09bd4af` endete unter Python 3.10
und 3.12 mit jeweils 10.196 bestandenen, zwei übersprungenen und zwei
fehlgeschlagenen Tests sowie 26 bestandenen Untertests. Beide Fehler waren
veraltete Erwartungen der Gesprächsdatenbankversion: Die Tests verlangten
Version 1 statt der inzwischen vorhandenen Version 3.

Nur die Testdatei wurde korrigiert. Sie prüft jetzt zusätzlich unveränderte alte
Nachrichten samt Metadaten, Entwürfe mit Leerraum und Revision sowie die
ungesendete erste Gesprächsübergabe nach Migration/Neustart. Die 122 betroffenen
Tests bestanden lokal. Diese Zahl ersetzt keinen noch ausstehenden CI-Lauf des
neuen Commits. Mac-Bau, Container- und UI-Prüfung am alten Commit waren grün;
es gab keinen manuellen Neustart eines CI-Laufs.

## Größerer Prüfungssatz: eingefroren, noch nicht ausgeführt

Der unabhängig erstellte [Heldout v2](../../fixtures/memory-acceptance-20261104/heldout-v2/README.md)
umfasst 100 neue künstliche Mails mit 40 Abruffragen, zehn native Originale mit
sieben Fragen sowie neun Zustandszweige mit elf weiteren Fragen. Die nativen
Originale enthalten echte MIME/PDF-Verbindungen, DOCX und Kalenderstände. Zwei
Transkripte sind Text; sie prüfen keine Audioerkennung.

Vor einem Modelllauf fand der Referenzreview vier fehlende Aufgaben, einen
falschen Zeitmetadatenwert und eine vermischte Kalenderphase. V2 korrigiert
ausschließlich Referenz, Metadaten und Dokumentation; V1 bleibt erhalten. Alle
100 Maildatensätze und zehn nativen Dateien wurden beim Kopieren ins Repository
noch einmal auf Unverändertheit geprüft. Alle 15 eingefrorenen Artefaktprüfsummen
stimmen. SHA-256 von V2 `freeze.json`:
`5f9e54252b0513d58dffaa0e943e471431e0f3759866af171f559b37e289a39e`.

Handlung, Eigentümer, Frist samt Präzision/Unklarheit und Status werden getrennt
bewertet. Die 46 aktuellen Erkennungsfälle schließen unklare Fristen und
unbekannte Sprecher ein; zwei historische beziehungsweise aufgehobene Fälle
sind zusätzliche Pflichtprüfungen. Eine falsche Person oder erfundene Frist
blockiert die Abnahme trotz eines guten Durchschnitts.

Der [statische Prüfbericht](heldout-static-validation.json) und der
[unveränderte ursprüngliche Validator](heldout-validator-original.py) sind
archiviert. Der Validator enthält seine damaligen temporären Pfade; sein Hash
entspricht dem eingefrorenen Manifest. Zehn absichtlich eingebaute Referenzfehler
wurden erkannt. Das belegt die Konsistenz dieser Referenzen, keine
Modellqualität. Der bisherige begrenzte Mailrunner kann diesen ganzen Satz
noch nicht korrekt aufnehmen und bewerten. Native Aufnahme, alle Aufgaben pro
Quelle, die getrennten Zustandsphasen und semantische Auswertung bleiben für
den späteren Ausführungsadapter offen.

## Entwicklungsumgebung wiederhergestellt

Zum Tageswechsel auf den 05.11. fehlten ältere Dateien und der Git-Verweis der
temporären Arbeitskopie; die Ursache wurde nicht festgestellt. Alle 72 aktuellen
Änderungs-, Nachweis- und Ledgerdateien wurden mit Prüfsummen im dauerhaften
Workspace gesichert. Eine neue getrennte Arbeitskopie wurde aus demselben
Git-Stand `09bd4af` erstellt und ausschließlich mit diesen Dateien ergänzt.
Die finale Helfersuite (77 Tests) und die Migrationsgruppe (122 Tests) bestanden
dort. Die eingefrorenen Quellen und die persönliche App blieben unverändert.

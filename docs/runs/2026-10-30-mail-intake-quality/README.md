# Frische Mailaufnahme und Abruf: lokale Qualitätsprobe

**Ergebnis: keine Qualitätsfreigabe.** Der erste echte Qwen-Aufruf wurde nach
3,1 Sekunden vom eigenen Lastwächter wegen kritischen Speicherdrucks abgebrochen.
Die 24 Mails wurden deshalb nicht vollständig eingeordnet, keine Aufgaben oder
Antworten bewertet und BGE-M3 noch nicht aufgerufen. Der Großimport bleibt pausiert.

## Was vorbereitet und geprüft wurde

Ein festgeschriebener [Entwicklungskatalog](../../evaluations/memory-quality/intake/catalog.json)
enthält 24 erfundene Mails und 16 Abruffragen. Seine Sollwerte wurden vor dem
Modelllauf festgelegt und werden nicht an das Produkt oder Modell übermittelt.
Die Probe verwendet die vorhandene Messlatte: echter Mailparser, frische
Arbeitsspeicher-Einordnung, echte SQLite-Speicher, Aufgabenerkennung,
Vorausfüllung, Personenansicht und Gesprächs-API. Nach der Einordnung wird der
vorhandene semantische Index mit echtem BGE-M3 aufgebaut; unvollständige Abdeckung
verhindert den anschließenden Abruf. Es werden keine früheren Einordnungen
wiedergegeben und keine Aufgaben automatisch angenommen.

Die Gegenfälle umfassen gleichnamige Personen mit getrennten Adressen,
Serviceadressen, Signaturen, fremde Zusagen, eigene ausgehende Zusagen,
Friständerungen, Terminzeit gegenüber Aufgabenfrist, historische und weitergeleitete
Mails, Werbung, bedingte Angebote, eine unbestätigte Buchung, ausgewählte Newsletter,
Quellen mit Manipulationsversuchen sowie fehlende und mehrdeutige Datumsangaben.
Das fehlende Maildatum wird bereits im künstlichen RFC-822-Postfach entfernt.

25 neue Werkzeugtests und die betroffenen Messlatten-/Diagnostiktests:
**340 bestanden**, eine bestehende Starlette/httpx-Abkündigungswarnung.
Die Mechaniktests verwenden ausdrücklich künstliche Sprach- und Suchantworten;
sie belegen die Messung, keine Zuordnungsqualität von Qwen.

## Echter Versuch A

Der unveränderte [Rohbericht](attempt-a.json) hält auch den begonnenen Modellaufruf
fest. Gemessen wurde auf Commit `7c382e68b2b18996019449bc5b22555f95cb11e0`.

| Merkmal | Beobachtung |
|---|---|
| Qwen | `kingfisher-qwen3.5:9b-32k`, bestehende lokale GGUF-Gewichte positiv geprüft |
| Diagnose-Transport | natives Ollama, 8.192 Kontexttoken, maximal 1.200 Ausgabetoken, Thinking aus |
| Ausgangszustand | kein anderes Modell geladen, Speicherdruckstufe 2, 39 % freie Reserve |
| Abbruch | nach 3,1 s: Speicherdruckstufe 4, 21 % freie Reserve |
| Fertige Modellaufrufe | 0; ein begonnener Aufruf, keine Antwort als Erfolg gewertet |
| Aufgaben, Personen, Fristen, Abruf | **nicht bewertet** |
| BGE-Abdeckung | **nicht erreicht**, keine Embedding-Aufrufe |
| Private Daten / Cloud / Downloads | keine |

Die Prozentwerte stammen aus `memory_pressure -Q`, die Druckstufe aus
`kern.memorystatus_vm_pressure_level`. Sie sind Systemindikatoren, keine direkte
Messung der Reaktionszeit anderer Mac-Programme. Der Wächter beendet nur seinen
eigenen Messprozess; er beendet weder andere Programme noch den Ollama-Dienst.
Ein bereits an Ollama übergebener Auftrag kann serverseitig noch auslaufen.
Die Anfrage verwendet `keep_alive: 15s`; eine spätere Kontrolle fand keine geladenen
Modelle mehr, normalen Druck (Stufe 1) und 53 % freie Reserve.

Vor einem möglichen zweiten Versuch wurde eine stabile Reserve von mindestens
48 % bei Druckstufe 1 verlangt. Die Kontrolle ergab bereits zu Beginn 47 %:
[Kontrollprotokoll](resource-recovery.json). Deshalb **kein zweiter Modellversuch**,
keine gelockerte Abbruchschwelle und keine Auswahl eines günstigeren Ergebnisses.

## Wiederholen und Grenzen

```sh
python scripts/probe_mail_intake_quality.py --check
python scripts/probe_mail_intake_quality.py --output /private/tmp/kf-mail-quality-NEU
```

Voraussetzungen: vorhandenes Qwen-Modell und BGE-M3 in lokalem Ollama, ausreichend
freie Mac-Ressourcen, neue Ergebnisablage. Maximal 900 Sekunden und 140
Sprachmodellaufrufe; Abbruch bei kritischem Druck oder unter 25 % freier Reserve.
Keine Produktionseinstellungen werden geladen, der persönliche Bestand bleibt
unberührt. SQLite-Laufzeitdateien werden nicht veröffentlicht.

Die 8K-Diagnose ist ausdrücklich **keine Messung des unveränderten 32K-App-Transports**.
Der Katalog ist eine kleine Entwicklungsprobe, kein repräsentativer Realmail-Test.
Wort-, Quellen- und Statusverträge ersetzen keine semantische Einzelprüfung.
Auch ein vollständig grüner Lauf setzt `bulk_import_authorized` nie auf `true`.

Nächster offener Nachweis: denselben eingefrorenen Katalog bei ausreichend freier
Reserve vollständig laufen lassen und alle Aufgaben, Identitäten und Antworten
einzeln lesen. Danach bleiben die vertagte Bedienprüfung der veröffentlichten
Fassung 1.0.32 im Mac-Fenster und eine kleine ausdrücklich freigegebene Realmail-Probe.
Ein App-Update nur für dieses Prüfwerkzeug ist nicht erforderlich.

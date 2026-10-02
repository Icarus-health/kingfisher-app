# M2c: vollständige Aussagefelder und genaue Quellenzeit

Nach dem unabhängig geprüften M1d ausführen, mit
superpowers:subagent-driven-development. Vor Implementierung den finalen M1d-Code
und beide konkreten Dokumente vollständig lesen:

- ../../evaluations/memory-quality/audits/2026-09-14/m2c-design.md
- ../../evaluations/memory-quality/audits/2026-09-14/m2c-design-review.md

## Verbindliche Entscheidungen

Eine einzige reine Projektion aus dem tatsächlich geprüften Claim und eingefrorenen
primären Original versorgt knowledge-context-v3, API-Metadaten und Verlaufssignatur.
Prädikat, Wert, Claim-Anlagezeit, Gültigkeitsintervall und Ereignis-/Importzeit bleiben
getrennte Felder. Fehlende Ereigniszeit bleibt null; UTC-Normalisierung darf keine
Information erfinden. Primär bedeutet erster gespeicherter Beleg, nicht alleiniger
Beleg oder vollständige Chronologie.

Die separate Gültigkeitsbindung erfasst ID und Entzugsgeneration jedes erforderlichen
Originals im transitiven Claim-Graphen. Sie bindet genau die damals verwendeten
Quellenzustände, erteilt keine Freigabe und repariert keine alte Akzeptanz. Niemals
aktuelle Generationen in alte Verlaufseinträge nachtragen. Bestehende Claim-Status-,
Intervall- und Evidenzprüfung bleibt vollständig erhalten.

Für den gesamten Wissensaufbau gelten getrennt maximal 128 verschiedene Claims und
128 verschiedene Originalquellen. Keine Verdrängung mit erneutem Laden als Umgehung.
Jeder einzelne Beleg einschließlich zweiter Zitate derselben Quelle wird geprüft.
Fehlende oder überschrittene vollständige Prüfung macht den Kandidaten unbrauchbar.
Diese Limits verbrauchen keine SelfModel-Produzentenplätze.

Pro vollständiger tatsächlich serialisierter JSON-Zeile höchstens 8 KiB UTF-8; über
alle präfixierten Zeilen und Trennzeichen höchstens 32 KiB; höchstens fünf ausgelieferte
Claims. Die feste Formaterklärung ist davon ausdrücklich nicht erfasst. Übergroße
Zeilen ganz auslassen, keine kanonischen Werte abschneiden. Übrige bereits begrenzte
Kandidaten prüfen, bis fünf passen oder das Kandidatenbudget endet. `payload_omitted`
zählt nur tatsächlich wegen Bytes ausgelassene Kandidaten, nicht ungesehene Treffer.

Knowledge-Lineage v2 verlangt genau dieselben Root-IDs und Signaturschlüssel;
gegenläufige Signaturen desselben Roots dürfen nicht still überschrieben werden.
Alte v1-Lineage wird konservativ einmal zurückgesetzt, sichtbarer Verlauf bleibt.
Erfassung und erneute Prüfung verwenden getrennte Caches. Alle tatsächlichen und
gescopten Agenten, Provider-/Fehler-/Werkzeug-/Freigabegrenzen und aktuellen Karten
müssen dieselbe Prüfung verwenden. Das ist eine optimistische Publikationsprüfung,
keine atomare Transaktion mit einem Modellaufruf.

Der Recorder friert erwartete Werte unabhängig aus synthetischen kanonischen Zeilen
vor dem Aufruf ein. Produktionsserializer und spätes Nachlesen dürfen die Erwartung
nicht erzeugen. Strikte v2-Auswertung historischer Daten bleibt; v2 erfüllt niemals
einen v3-Feldvertrag. Bestehende beide Referenzmodi und rohe Versuche bleiben unverändert.

## Abnahme

Die im Entwurf beschriebenen RecordingProvider-, Zeit-, Null-, Intervall-, Offset-,
Metadatenänderungs-, Zweitquellen-, Entzug/Wiederöffnung-, Neustart-, Karten-, Egress-,
UTF-8-/Omissions- und Recorder-Gegenfälle ausführen. Keine echten Modelle oder privaten
Daten für diesen Korrektheitsnachweis erforderlich. Unabhängige Prüfung, dann relevante
Backend-/Frontend-/CI-Prüfung. Erst danach den separaten Antwortvergleich einfrieren.

Keine neue Timeline-Oberfläche, keine neue Quellengenehmigung, keine Übernahme von
SelfModel-Produzentenrechten in ClaimStore, kein Restore-/Löschversprechen.


## Task 1: Vollständiger M2c-Durchstich einschließlich unabhängigem Recorder

Basis: `ebb2e63bc61f7bfcc867ffd3e03c28b5db3614c3`, nach unabhängiger M1d-Abnahme
und grüner Python-3.10/3.12-/Container-CI. Arbeitsbranch:
`fix/knowledge-semantic-time-context`. Vorhandener isolierter Worktree bleibt erhalten.

Lies zuerst CLAUDE.md und die Produktvision. Die vollständigen fachlichen Vorgaben
stehen in `docs/evaluations/memory-quality/audits/2026-09-14/m2c-design.md` und
`m2c-design-review.md`; lies beide vollständig. Die obigen verbindlichen Entscheidungen
und die drei Reviewpräzisierungen gelten gemeinsam. Wiederverwendung bezieht sich jetzt
auf den tatsächlich geprüften M1d-Code, nicht auf die historischen hypothetischen Namen.

Der Auftrag umfasst den gesamten zusammenhängenden Codepfad: reine knowledge-context-v3
Projektion aus exakt geprüften, eingefrorenen Claim-/Originaldaten; getrennte begrenzte
Quellen-/Claimprüfung; Knowledge-Lineage v2; tatsächliche Agenten- und Servergrenzen;
aktuelle Kontextkarten; strikter unabhängiger v3-Recorder bei unveränderten v2- und
Referenzmodi. Passe API-Typen nur an, soweit die vorhandene Oberfläche korrekte Metadaten
weiterreichen muss. Keine neue Timeline, keine Schemaänderung an ClaimStore und keine
Restore-Freigabe.

Exakte Limits: 128 verschiedene Claims und separat 128 Originalquellen pro vollständigem
Wissensaufbau, keine Verdrängung; alle Belege prüfen. Höchstens fünf ausgelieferte
Zeilen, höchstens 8 KiB UTF-8 pro vollständiger JSON-Zeile, höchstens 32 KiB für alle
präfixierten Zeilen samt Trennzeichen. Feste Erklärung ist aus diesem Datenzeilenbudget
ausgenommen. Ganze übergroße Zeilen auslassen, begrenzte übrige Kandidaten weiter prüfen,
korrektes payload_omitted. Fehlende Ereigniszeit bleibt null, Zeiten kanonisch UTC,
Gültigkeit [valid_from, valid_until). Erste gespeicherte Quelle ist primär, kein Ersatz
für vollständige transitive Evidenz. Keine aktuelle Generation in alte Historie eintragen.

TDD vor Produktion: tatsächlicher RecordingProvider muss den gegenwärtigen Verlust
von predicate/value, akzeptierter Aussagezeit, Intervall sowie getrennten Ereignis-/
Importdaten zeigen. Prüfe danach die gesamten im Design benannten Mutations-,
Verlaufs-/Neustart-/Karten-, Freigabe-/Tool-/Fehlergrenzen, Null-/Offset-/Intervall-,
Mehrfachbeleg-/Generations-, UTF-8-/Omissions- und strikten Recorder-Gegenfälle.
Erwartungen unabhängig aus vor Aufruf eingefrorenen synthetischen kanonischen Zeilen;
kein Produktionsserializer für Sollwerte und kein spätes Nachlesen als Erwartung.

Bearbeitungsbereich: betroffene `sidecar/icarus_memory`-Module, ihre Tests und
`scripts/probe_memory_pipeline.py`, `memory_probe_fixtures.py`, unterstützende
Diagnoseskripte/-tests; API-Typen soweit erforderlich. Dokumentation/Release-Nachweise
koordiniert Root. Vorhandene M3-Entwürfe nicht verändern oder committen. Keine privaten
Daten, echten Modelle, Downloads von Modellgewichten, laufende private Container oder
Konfigurationen verwenden. Tests isoliert; vorhandene .venv/Node-Laufzeit nutzen.

Prüfen: fokussierte rote/grüne Tests, gesamte `sidecar/tests` und alle drei
Memory-Probe-Testdateien, Schema/Beispiel und bei API-Typänderung Frontend-Build.
Python 3.10 und 3.12 sind unterstützt; insbesondere UTC-Z-Verarbeitung erhalten.
Keine neuen Tests nur für triviale Weiterleitungen oder Prosa.

Nach Selbstprüfung nur eigene Code-/Testdateien committen, nicht pushen. Im Bericht
exakte Kommandos, rote/grüne Ergebnisse, Eingriffspunkte, erhaltene Referenzkompatibilität,
Kontrollmatrix und offene Grenzen nennen; bei fertigem Stand Produktionscode einfrieren.
Root erstellt unabhängiges Review und isolierten echten API-/Container-/Provider-Nachweis.

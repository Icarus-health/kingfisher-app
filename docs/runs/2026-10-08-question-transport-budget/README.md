# Fragenbudget bis zum lokalen JSON-Transport

## Reproduzierter Defekt

Das Fragenverständnis fällt nach sechs Sekunden zurück. Sein ThreadPool beendet den HTTP-Aufruf dadurch jedoch nicht: `OpenAICompatible.complete_json()` verwendete weiterhin 30 Sekunden Netzwerkphasenlimit. Ein echter langsamer Loopback-Server reproduzierte den Fehler: nach Rückfall blieb der Client offen. Dieser Test scheiterte vor der Korrektur und besteht danach.

Ein worker-lokales, monotones Zeitbudget wird nun durch bestehende synchrone Anbieterwrapper bis zum JSON-Transport getragen. Verstrichene Modellwarte-/Vorbereitungszeit verkürzt das verbleibende HTTP-Phasenlimit. Nach bereits abgelaufener Vorbereitung beginnt kein Generierungsrequest. Normale JSON-Aufträge behalten 30 bzw. 60 Sekunden, andere Gespräche und Anbieter ihren bisherigen Weg. Prompt, Schema, Suchschwelle und Quellenauswahl sind unverändert.

Dies ist **keine harte Gesamtfrist** für den gesamten Worker: Wartephasen, Modellvorbereitung/-nachlauf und kontinuierlich eintreffende Antwortstücke sind damit nicht vollständig abbrechbar. Anbieter ohne diesen lokalen OpenAI-kompatiblen JSON-Transport bleiben unverändert. Die äußere Rückfallfrist besteht weiterhin.

## Prüfungen

- RED: langsamer echter lokaler HTTP-Server hält den Worker nach Rückfall offen.
- GREEN: Verbindung wird geschlossen; verstrichene Modellwartezeit verhindert einen verspäteten Request; paralleler Kontext und Rücksetzen nach Fehler funktionieren. Finale drei Regressionen bestanden.
- 199 betroffene Frage-/Transport-/Routing-/Modellspeicher-/Hintergrund-/Diagnosetests bestanden, 1 übersprungen, bestehende Starlette/httpx-Warnung. Keine neue UI-Änderung.
- Unabhängiger Reviewer fand keine wichtige konkrete Regression. Zwei neue Offlinekontrollen sowie zusätzlich verschachtelte Deadlines und `RoutedProvider → VerifiedLocalProvider → OpenAICompatible` unabhängig geprüft. Sein Sandboxkontext erlaubte keine Loopback-Bindung; der echte Netzwerktest wurde vom Hauptagenten mit lokaler Portfreigabe ausgeführt.

## Echter, begrenzter Modellvergleich

Alle Quellen sind künstlich. Unveränderte erste vier Fragen des eingefrorenen Umschreibungskatalogs, deterministische Einordnung (keine Einordnungsqualifikation), echte bge-m3-Vektoren und echter `SemanticService`/`DurableSemanticIndex`. Modelle sind vorhandene lokale Gewichte, keine Downloads oder Cloudaufrufe:

- `gemma3:1b-it-qat`, Digest `b491bd3989c65bf74267bfb9e7d5fd0bf7b6548bc12f91a98df3c56865ce2f80`.
- `bge-m3:latest`, Digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.

Ein separater Docker-Modellserver ohne Netzwerk oder Hostport, zwei CPU-Kerne, 3584 MiB Speicher ohne Swap und nur lesbare vorhandene Gewichte; separater Client mit einem Kern/512 MiB. Ein zuvor abgeschlossener Vorlauf mit zwei residenten Modellen überschritt das Speicherlimit. Daher verwendet der folgende kontrollierte Vorher-/Nachhervergleich jeweils **ein** gleichzeitig geladenes Modell, Kontext4096. Beide verglichenen Läufe sind abgeschlossen und meldeten keinen OOM-Kill. Das ist kein Lauf des privaten Imports und kein Mac-GPU-Benchmark.

`before.json` importiert nachgewiesen die installierten Klassen aus site-packages. `after.json` importiert ausdrücklich den geänderten Arbeitsbaum; Pfade und SHA-256 der Agent-/Suchdienstmodule sind festgehalten. Der erste, nicht als Vergleich veröffentlichte Vorlauf lud durch Probehelfer zunächst Repo-Code statt installiertem Code; dies wurde vor diesem Vergleich korrigiert. Die Treiber liegen unverändert bei; sie erwarten /repo und /out im beschriebenen isolierten Container.

| Frage | Vorher | Nachher | Bewertung |
|---|---|---|---|
| Beginn Serverwartung | S1, 36,057s | S1, 34,591s | Erwartete Originalquelle angezeigt |
| System abends nicht erreichbar | keine, 8,754s | keine, 7,784s | Keine Antwort; Gold bewertet nur Quellenpotential, keine belegte Unerreichbarkeit |
| Dachrechnung überwiesen | S2, 35,484s | S2, 34,124s | Erwartete Originalquelle angezeigt |
| Handwerkerleistung oben am Haus beglichen | S7, 36,757s | S7, 36,280s | **Falsche Auswahl**: S7 berichtet einen verschobenen Dresden-Termin, obwohl die semantische Suche S2 findet |

Die Bedeutungssuche meldet in allen acht verglichenen Fragen `ok`, einschließlich leerem Ergebnis. Vorher enden die Frageverständnis-Aufrufe erst nach dem äußeren Rückfall; nachher verzeichnet die Diagnose jeweils einen tatsächlich abgebrochenen HTTP-Aufruf. Deshalb verdienen die Nachherzeilen trotz korrekt angezeigter Direktquellen **keinen vollständigen Diagnose-Erfolgspunkt**. Rückfall/Nichtantwort und tatsächliche Auswahlfehler bleiben getrennt sichtbar. Der Quellenentzugstest besteht in beiden Läufen.

Das kleine Modell ist für diese Aufgabe nicht freigegeben: falsche Quellenwahl und Antwortzeiten über30s auf CPU. Die Korrektur verbessert den Transportvertrag; sie belegt weder verbesserte Trefferquote noch interaktive Nutzbarkeit oder vollständige CoS-Antwortqualität. Kein voller 36-Fragenlauf mit diesem bereits ungeeigneten Kandidaten, keine Änderung der persönlichen Modellrollen, keine blinde Schwellenabsenkung. Nächste Kernabnahme bleibt ein leistungsfähigerer freigegebener lokaler Modellweg oder konkret freigegebener Cloudvergleich, zusätzlich native Alltagsbedienung und Quellenabdeckung.

Nach Abschluss wurden die eigenen Testcontainer beendet/entfernt. Die persönliche Hintergrundpause und das ausgeschaltete produktive Ollama bleiben erhalten.

## Geprüfte lokale Lieferung

Produktcode `f5af412867f379689db1f6c097171785c59c5008`, installiert **1.0.6-local.f5af412**, Image `sha256:9b0c2db264e60093ef0927f2a926b74ef807c0755d63daec004f157a1f8f3c79`. Die264 Paket- und112 UI-Dateien wurden im fertigen Image byteweise geprüft. Der echte langsame Loopback-Transporttest besteht auch darin, ohne Internet oder Modelle. Kein erneuter UI-Build nötig, da Oberfläche unverändert und bytegleich übernommen.

Kalte Sicherung vor Austausch unter `Kingfisher-Rueckweg/2026-10-08-vor-f5af412`. Alle344 Original-IDs/Digests und17 SQLite-Dateien geprüft, Konten-/Kalender-/Modell-/Zeitplaneinstellungen erhalten, unverändertes natives Programm und gleicher Datenvolume. Backend gesund, richtige Version, globale Pause erhalten, echter Mailstatus pausiert. Der semantische Index bleibt bei ausgeschaltetem produktivem Ollama `unavailable`. Native Fensterprüfung erneut durch gesperrten Mac blockiert. Kein öffentlicher Release/Registry-Upload, kein CI-Neustart und keine neue private Verarbeitung.

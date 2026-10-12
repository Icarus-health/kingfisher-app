# Gemeinsamer Backend-Abgleich und Abnahmegrenzen

9. Oktober 2026. Gemeinsame Draft-Vorschau #46; kein Main-Merge, keine persönliche Installation oder Bedienung. Der Nutzer hat den Fenstertest ausdrücklich auf später verschoben. Persönliche Quellen, Modelle, Import und Freigaben wurden in dieser Runde nicht benutzt.

## Prüfstand

Laufzeitquellen aus sauberem Gitarchiv `e326f8113eae2e6e8123c7a39417fddf1e9fbebc`; Archiv-SHA-256 `08e28271e6015924c327a9eb5b4c5259f216a17daad1deede57eafc0b6fdd109`. Das bleibt der Laufzeitstand des [geprüften gekoppelten Pakets](../2026-10-09-conditional-report-binding/README.md). Die Änderungen dieser Runde betreffen ausschließlich Tests und Dokumentation. Ein neues Paket ist dadurch nicht nötig.

Der vollständige Backend-Lauf ist abgeschlossen: **6134 bestanden, 10 fehlgeschlagen, 1 Linux-Plattformskip, 1 Starlette/httpx-Warnung und 26 bestandene Unterfälle, 899,20 Sekunden**. Kein grüner Gesamtlauf behauptet. Alle zehn Fehler sind einzeln aufgeklärt; die vollständigen betroffenen Testdateien bestehen in separaten Nachläufen (insgesamt **196 Fälle**, einschließlich drei zusätzlicher Bedingungsfälle). Der Gesamtlauf selbst wird nicht nachträglich grün gerechnet und wurde nicht nochmals vollständig ausgeführt.

Seine Prüfkopie enthält die Paketfassung `1.0.6-preview.e326f81` in `VERSION`, statt der unveränderten Repository-Fassung `1.0.6`. Das verursacht **drei Fehler** in den streng auf eine Release-Fassung prüfenden Repository-/Manifest-/Tagtests. Die komplette Fassungs-Testdatei wurde separat mit der tatsächlichen Repository-Datei erneut ausgeführt: **57 bestanden, eine Starlette/httpx-Warnung**. Release-Seite und Anführungszeichenprüfung: **46 bestanden, eine bestehende SyntaxWarning** nach Wiederherstellung der tatsächlichen Repository-Fassung und Git-Dateiliste. Der weitere Fehler der Anführungszeichenprüfung war `git ls-files` mit Exit 128 im Gitarchiv ohne `.git`; keine fehlerhafte Anführungszeichenstelle. Nur die getrennte Prüfkopie erhielt Git-Metadaten und die genaue ursprüngliche Liste verfolgter Dateien. Tests unverändert; Preview-Kennungen werden nicht still als öffentliche Release-Fassungen akzeptiert.

Der letzte Fehler betraf einen Rangfolgetest für Termin/Nachbereitung: zur tatsächlichen Testzeit 23:11 Uhr in Berlin liegt dessen „in einer Stunde“-Termin bereits am nächsten Tag. Die unveränderte Logik berücksichtigt absichtlich nur heutige bevorstehende Termine. `briefing.py` und dieser alte Test waren bis zur Korrektur identisch zum früheren Main-Stand `3667e4e`. Nur der Rangfolgetest erhält jetzt einen festen Zeitzonen-Stichtag um 10:00 UTC; alle Ereignisse sind relativ dazu angelegt, die Erwartung bleibt unverändert. **35 Fälle** der vollständigen Nachbereitungs-/Briefing-Testdateien bestanden, eine Starlette/httpx-Warnung. Der bestehende gesonderte Morgen-Ausschluss und die Zeitzonenfälle bleiben erhalten.

## Fünf Absatz-Testfehler und ihre Ursache

Die zehn bisherigen Auszugstests verwenden eine 480-Zeichen-Füllpassage. Darin stand „Wir melden uns, sobald es Neuigkeiten gibt“. Die erweiterte Bedingungsbindung erkennt diese echte Bedingung. Sie erhält konservativ den ganzen Absatz; dieser überschreitet das 400-Zeichen-Limit einer Original-Satzeinheit. Die Formulierung fällt deshalb teilweise schon vor dem Modellaufruf auf die Originalquelle zurück. Ein frei formulierter Satz erfüllt außerdem den neuen Original-Vertrag nicht. **Fünf Fehler/fünf bestandene Fälle** auf dem neuen Laufzeitstand; mit dem alten Satzprüfmodul **zehn bestanden**. Das ist eine nachgewiesene Verhaltensänderung, kein behaupteter Infrastrukturfehler.

Die Füllpassage der bisherigen Tests ist jetzt bedingungsfrei, damit diese weiterhin Auszugsbildung, Volltextprüfung und Datumsumformulierung prüfen. Ihre Erwartungen bleiben unverändert. Drei zusätzliche reale prepare/render-Fälle prüfen die bisher vermischte Bedingungsgrenze ausdrücklich:

- Kurzer Absatz mit Datum und nachfolgender Bedingung: Das Modell wählt eine serverseitig ausgegebene Originalstelle; Datum und Bedingung werden vollständig gezeigt.
- Bedingter Absatz über 400 Zeichen: Kein Formulierungsaufruf; Originalbericht zeigt die vollständige Quelle einschließlich Datum und Bedingung.
- Bedingung in einem anderen Absatz und alte freie Datumsumformulierung: konservativer Rückfall auf den vollständigen Originalbericht.

**58 Fälle** der beiden vollständigen Absatz-/Bedingungs-Testdateien bestanden auf getrenntem sauberem Archiv mit diesen Teständerungen. Die drei neuen Fälle schlagen mit dem alten Satzprüfmodul alle fehl; 45 andere Fälle waren in dieser engen Gegenprobe abgewählt. Keine Änderung am Laufzeitcode oder Lockerung der Bedingungsprüfung. Unabhängiges enges Review bestätigt die Trennung der Testverträge und die sichtbare Originalinformation; es ist kein eigener Testlauf.

## Bewusst erhaltene Grenze

Die Erkennung prüft den Volltext, nicht ausschließlich einen möglicherweise gekürzten Ausschnitt. Auch eine Bedingung außerhalb des ausgewählten Absatzes kann deshalb die kurze freie Antwort verhindern. Der Originalbericht erhält die gesuchte Information, kann aber länger und weniger angenehm zu lesen sein. Bloß auf den Ausschnitt umzustellen könnte eine beim Ausschneiden verlorene Einschränkung übergehen; eine sichere Relevanz-/Kontextlösung ist mit dieser Testkorrektur nicht geliefert. Keine allgemeine Sprachverständnis- oder persönliche Qualitätsgarantie.

## Was noch zur tatsächlichen Nutzung fehlt

Der Abgleich mit Produktvision und LifeOS-Übernahmeplan ergibt keine weitere belegte Pflichtfunktion, die in dieser Runde unter den bestehenden Grenzen sinnvoll neu gebaut werden muss. Das allgemeine Atlas-Geräte-/Serverinventar ist ausdrücklich eine spätere optionale Erweiterung. Die Kernnachweise bleiben:

1. Native Bedienkette, lokale Kalenderfreigabe, drei ausgewählte Kalender und korrekte Terminanzeige.
2. Vorab festgelegte persönliche Fragen gegen Originale: Menschen, Projekte, Fristen, Bedingungen, Absagen, fehlende Informationen; gewählte Modellrollen und tatsächliche Quellenabdeckung.
3. Reale RAM-/Akkulast und Qualität während eines Arbeitstages; erst danach den großen Import kontrolliert fortsetzen.
4. Geprüfte vollständige persönliche Sicherung vor der v21-Installation; danach Paketinstallation, Wiederaufnahme und Alltagsabnahme.

Codeprüfungen und synthetische Daten ersetzen diese Nachweise nicht. Der [aktuelle Abnahmestand](../../64-cos-abnahme-status-2026-10-09.md) und die [Alltagsabnahme](../../60-alltagsabnahme.md) sind der Einstieg für weitere Arbeit. Vollständige Logs (komprimiert), `verification.json` und das unabhängige lesende Review liegen in diesem Ordner. Die ursprünglichen Fehler bleiben samt Nachprüfungen erhalten; keine CI-Wiederholung, neue Automatisierung oder Cloudkosten.

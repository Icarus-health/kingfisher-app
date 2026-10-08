# Bedingungen und fehlende Freigaben gemeinsam erhalten

## Problem

Die getrennte native KontrolleQ5 wählte die richtige Quelle aus. Die Satzprüfung verwarf die Regel „erst nach schriftlicher Freigabe durch die Lagerleitung“, weil dieselbe Quelle anschließend „Freigabe liegt noch nicht vor“ sagt. Sichtbar blieb nur der Fehlstatus. Zugleich bestanden unbedingte Versandbehauptungen, obwohl allein eine bedingte Erlaubnis belegt war. PR15 schützte bereits vollständig verlorene Quellen, nicht diesen Verlust innerhalb derselben Quelle.

## Konservative Korrektur

Bei zitierten Quellkörpern mit erkannten passiven Erlaubnissen (`darf/dürfen/duerfen`, `erst/nur nach` oder `wenn/sofern/sobald/falls`, passiver Schluss mit `werden`) müssen freie Antwortsätze vollständig als eigene Sätze in einem zitierten Quellkörper stehen. Kommas und angehängte Bedingungen bleiben Bestandteil der Einheit. Nur Groß-/Kleinschreibung und Leerraum werden vereinheitlicht; Umlaute und ß bleiben verschieden. Titel etablieren keine Erlaubnis.

Damit kann weder eine ausgelassene Bedingung noch eine freie Umschreibung wie „Material darf raus“ oder „Es ist raus“ allein aus der Regel bestehen. Ein separat ausdrücklich belegter wörtlicher Versandbericht bleibt möglich. Ein vollständiger unveränderter Regelsatz darf neben dem eigenständigen Status „Freigabe liegt noch nicht vor“ derselben Quelle stehen; diese eng begrenzte Ausnahme hebt keine separate Negation, kein Verbot und keine negative Aussage einer anderen Quelle auf.

Nach mindestens einer Verwerfung wird zusätzlich geprüft, ob alle erkannten Regeln aus dem aktuellen Volltext der vorgelegten Quellen in den verbleibenden Sätzen vertreten sind. Fehlt eine, greift der vorhandene Originalzitatpfad – auch innerhalb derselben Episode und beim Wiederlesen alter JSON-Antworten. Quellenentzug blockiert weiterhin die Anzeige. Keine Änderung an gespeicherten Originalen, Suchindex, Modellrollen, Prompts oder Importpause.

## Evidenz und Review

33 neue Fälle: vollständige Regel plus Status, unbedingte Erlaubnis, behauptetes Ereignis, aktive/umgangssprachliche/Pronomen-Umschreibungen, ausgelassene Schriftlichkeit/Autorität, umgekehrte Bedingung, falsche Kennung, positive Freigabe, zusätzliche Komma-Bedingung, Plural, getrennte Tatsachenmeldung, separates Verbot, andere Quelle, neue/gespeicherte Teilantwort, zweites Prüftor, Entzug. Die ersten21 Fälle zeigten vor der Änderung10 Fehler; zusätzlich aktive Versandform und vier Reviewfälle separat rot vor ihrer jeweiligen Korrektur. Endstand270 betroffene Prüfungen bestanden, eine bestehende Starlette/httpx-Warnung.

Ein günstiger unabhängiger Agent fand echte Umgehungen im Zwischenstand: „raus“/Pronomen, übersehene Pluralformen und Wortkollisionen durch `falten`. Diese wurden vor Lieferung korrigiert und durch Regressionstests belegt. Er führte die33 neuen Tests selbst aus; Endkontrolle sauber. Die breite Runde stammt vom Hauptagenten. Ein erster Sandboxlauf scheiterte ausschließlich am lokalen Testport des Transporttests; die autorisierte Prüfung mit Loopback bestand.

`recorded-output-replay.json` spielt die unveränderten nativen Q5-Ausgaben gegen vorherigen Code ae3e695 und neuen Code ab: vorher nur Fehlstatus, nachher Zitate bei derselben Verwerfung und derselben Zahl wiedergegebener Modellantworten. Keine neue Inferenz, kein Abruf-/Einordnungsbenchmark. Eigener Smoke mit künstlicher Kennung T-204 prüft den fertigen Paketweg einschließlich JSON-Wiederherstellung und Entzug; kein Modell oder Netzwerk.

## Grenzen

Bewusst weniger freie Sprache bei erkannten Regelquellen; vollständige Originale sind die Rückfallebene. Kein allgemeiner Parser für aktive Regeln, beliebige Modalverben, Abkürzungen oder alle deutschen Bedingungsformen. Regeln außerhalb der Erkennung bleiben ein offenes Qualitätsrisiko. Kein Beweis semantischer Vollständigkeit bei einer Auslassung ohne Verwerfung, kein Beweis für korrekte Einspeisung, Suche oder Aktualität einer Quelle. Native UI-/Alltagsabnahme, Batterieprüfung und echte Quellenabdeckung bleiben offen. Insgesamt noch kein abgenommener CoS.

## Lieferung

Produktcode32d5a12f8243b48580e768b94e39403623092447, lokal **1.0.6-local.32d5a12**. Image `sha256:6f402653b27c52e0a5174a75ae98b0d564ef843093cfbc79603bb1c761e90dff`:264Paket- und112unveränderte UI-Dateien byteweise geprüft; netzloser Paket-Smoke mit128MB besteht. Kein öffentlicher Imageupload oder Release.

Kalte Sicherung `Kingfisher-Rueckweg/2026-10-08-vor-32d5a12`:344Original-IDs/Inhaltsdigests und17SQLite-Dateien erhalten/geprüft, gleiches Datenvolume. Konten, Kalender, Anbieter, Modellrollen und Zeitpläne erhalten; native Binärdatei unverändert, ad-hoc Signatur geprüft, Backend gesund. Hintergrund-/Mailpause bleibt bestehen; Ollama aus und Bedeutungssuche deshalb `unavailable`. Frischer Versuch der nativen Bedienprüfung weiterhin am gesperrten Mac gescheitert. Keine CI-Wiederholung, kein Abonnement, kein Check-in; keine Cloudinferenz oder Modellinstallation.

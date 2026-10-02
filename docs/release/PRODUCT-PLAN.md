# Kingfisher: verbindlicher Plan bis zum fertigen Programm

Stand: 6. September 2026. Produktauftrag: der ausgearbeitete Icarus-Funktionsumfang
in der freigegebenen Kingfisher-Oberfläche auf dem Mac. **Das überprüfbare Graphengedächtnis
ist der Kern; alle anderen Funktionen liefern ihm Quellen oder arbeiten mit
seinem belegten Kontext.**

## Priorisierung ab 13. September 2026

Die [Memory-first-Roadmap](MEMORY-FIRST-ROADMAP.md) konkretisiert die inzwischen
präzisierte Produktvision und hat Vorrang für die nächste Arbeitsreihenfolge.
Die folgende ursprüngliche Funktionsplanung bleibt als Umfangsnachweis erhalten;
ihre Abnahmequote ersetzt keine Gedächtnis-/Modellqualifikation. Breitere
Werkzeugausführung und zusätzliche Office-Integrationen sind nachgeordnet, bis
korrekter Kontext, Korrekturen und angemessene Antwortzeiten nachgewiesen sind.

## Aktuelle Plattformgrenze

Produktentscheidung vom 6. September 2026: **Docker auf dem Mac, Bedienung im
Browser.** Eine native App ist für diese Lieferung nicht erforderlich. Mobile,
Smartphone-Navigation, Tauri-Paketierung, App-Signierung und App-Store-Vertrieb
sind keine aktuellen Freigabekriterien. Bestehender nativer Icarus-Code bleibt
historischer Bestand; wir bauen keine zweite Produktoberfläche.

Der schnellste Weg nutzt das vorhandene Kingfisher-Image, dieselbe React-UI und
das persistente lokale Volume. Desktop-Screens bleiben verbindlich. Ein
Linux-Container-/Chromiumtest belegt die Containerfunktion; der abschließende
Start mit Docker Desktop und Browser auf einem echten Mac bleibt separat
nachzuweisen. Der [Abnahmestand](ROADMAP-STATUS.md) zählt die erledigten Punkte.

## Wann das Programm fertig ist

Eine Funktion ist erst fertig, wenn sie in der ausgelieferten Kingfisher-App
bedienbar ist, mit echten freigegebenen Daten arbeitet, nach einem Neustart
weiter funktioniert, Fehler verständlich behandelt und an den passenden
Referenzscreens abgenommen wurde. Eine vorhandene API, ein grüner Unit-Test
oder ein schöner Screen allein erfüllt diese Definition nicht.

Die komplette Liste der zwölf Icarus-Funktionssäulen steht in
[Funktionsabgleich](../icarus-kingfisher-funktionsabgleich.md). Sie bleibt der
Umfangsvertrag. Ein früher Alltagstest ist ein Zwischenstand; er ersetzt keine
noch offene Funktion des vollständigen Programms.

## Lieferpakete und Abnahme

Jeder Eintrag wird über einen oder mehrere kleine PRs abgeschlossen. PR-Nummern
werden erst eingetragen, wenn der PR existiert; Pläne erhalten keine erfundenen
PR-Links. Ein abhängiger PR nennt seinen Vorgänger und enthält nur seinen
zusätzlichen Änderungssatz.

| Paket | Konkreter Nutzungsablauf | Abnahmekriterium | Stand / Nachweis |
| --- | --- | --- | --- |
| K0 – Start und Wiederanlauf | App installieren, öffnen, ein Modell verbinden, Gespräch führen, neu starten und dasselbe Gespräch wiederfinden | Der gebaute Container liefert die React-App und alle freigegebenen Assets; alle aktiven URLs sind direkt aufrufbar; API ist geschützt; Gespräch und bestätigtes Wissen überleben den Container-Neustart | In Umsetzung in [PR #2](https://github.com/Icarus-health/Kingfisher/pull/2): Container-/Browser-Prüfung, `/memory`-Reload, Host-Modellzugang; [Prüfnachweise](K0-RUNTIME-VERIFICATION.md); Modelleinrichtung einschließlich echter Antwort, Neustart und begrenzter visueller Umsetzungsfreigabe nun in VISUAL-CHECK-local-model-v1.md belegt |
| K1 – Gedächtnisgrundlage | Eine Person arbeitet an zwei Projekten und ist gleichzeitig ein persönlicher Kontakt; gleichnamige Menschen bleiben unterscheidbar | Stabile Kennungen, mehrere belegte Beziehungen, Zeit und Kontext, Korrekturhistorie, transitive Entwertung und Wiederherstellung | Backend-Teil in [PR #1](https://github.com/Icarus-health/Kingfisher/pull/1), 219 gezielte Tests bestanden; UI-Anbindung offen |
| K2 – Gedächtnis vollständig bedienen | Im Gespräch einen Vorschlag prüfen, Quelle öffnen, bestätigen, Person/Projekt wiederfinden, falsche Beziehung korrigieren oder widerrufen | Alle Schritte in freigegebenen Kingfisher-Zuständen; Rohquelle, Vermutung und bestätigtes Wissen klar getrennt; neue Antworten verwenden den korrigierten Stand; Mehrdeutigkeiten werden sichtbar geklärt | [PR #3](https://github.com/Icarus-health/Kingfisher/pull/3): Quellenzugriff, aktueller Claim-Status und Widerruf in Gesprächskarten; [Vertrag und Nachweise](K2-CONVERSATION-MEMORY.md). Profile, Identitätsklärung und direkter Beziehungseditor bleiben offen |
| K3 – Quellen und fortlaufende Aufnahme | Mehrere freigegebene Mail-/Kalenderkonten und lokale Ordner verbinden, neue Inhalte und Änderungen aufnehmen, Quelle wieder entziehen | Wiederholter Import dupliziert nichts; Konto-/Quellkennungen, Sync-Cursor, Änderungen und Löschungen nachvollziehbar; Teilausfälle sichtbar; keine automatische Faktbestätigung | Quellenverhalten (Punkt 10) abgenommen: [ACCEPTANCE-SOURCES.md](ACCEPTANCE-SOURCES.md). Fortlaufende Einrichtung mit echtem Mailanbieter (Punkt 09) bleibt offen |
| K4 – Chief of Staff im Alltag | Tagesbriefing öffnen, Termin vorbereiten, Aufgabe/Projekt bearbeiten, Zusage delegieren, offene Antwort verfolgen und Entscheidung begründen | Briefing und Aktionen greifen auf denselben aktuellen Kontext zu; keine Demo-Inhalte im Produktmodus; Zustand, Herkunft, Freigabe und Ergebnis jeder Aktion sichtbar | Gemeinsamer Ablauf von Punkt 12 abgenommen; Nachweis: [ACCEPTANCE-COS.md](ACCEPTANCE-COS.md) |
| K5 – Vollständiger Icarus-Umfang | Ziele/Gewohnheiten, Außenwelt, Modellwahl, spezialisierte Agenten, Werkzeuge, Browser/Computer, dauerhafte Prozesse, Sprachnutzung auf dem Mac | Alle unten aufgeführten Umfangsbereiche besitzen einen getesteten Nutzungsablauf; gemeinsame Policy, Quellen- und Gedächtnisregeln gelten überall | Offen; in separate PRs pro Bereich teilen |
| K6 – Exakte Oberfläche | Jeden ausgelieferten Zustand am richtigen Referenzviewport verwenden, einschließlich Laden, leerem Bestand, Fehlern und Erfolg | Freigegebene Schriften, Medien, Icons, Layout und Interaktionen; Screenshotvergleich und Abweichungsliste je Screen; keine ungeklärten sichtbaren Entscheidungen | Fortlaufend in jedem Desktop-UI-PR. Mobile ist ausdrücklich zurückgestellt und kein Freigabekriterium der Mac-Version. Abschließender Mac-Gesamtdurchgang offen |
| K7 – Mac-Auslieferung und Alltagstest | Mac-Installation und Update eines vorhandenen Bestands, Backup erstellen, Wiederherstellung durchführen, Alltagsszenarien über Neustarts ausführen | Reproduzierbarer Docker-Build mit Kingfisher-UI; Start mit Docker Desktop und Browser auf macOS; keine verlorenen Daten; geschützte lokale Installation; eindeutige Start-/Updateanleitung; vollständige Funktions- und visuelle Abnahme | Offen; erst danach als fertiges Programm ausweisen |

## Vollständigkeit: keine Icarus-Funktion fällt weg

| Bereich aus der Produktvision | Zugeordnete Lieferung | Noch erforderlicher Produktnachweis |
| --- | --- | --- |
| 7.1 Langzeitgedächtnis | K1–K3, K7 | Quellen, Kandidaten, Annahme, Zeitverlauf, Korrektur, Export und Wiederherstellung in der App |
| 7.2 Wissens- und Beziehungsgraph | K1–K2 | Personen/Organisationen/Projekte/Quellen verbinden, Beziehungen erklären, Mehrdeutigkeit lösen und Fehler rückgängig machen |
| 7.3 Ziele, Gewohnheiten, Lernen | K5-Lernen | Beobachtung als prüfbare Hypothese, bewusste Annahme/Ablehnung und korrigierbare Lernhistorie |
| 7.4 Projekte, Aufgaben, Entscheidungen | K4 | Verantwortliche, Zusagen, Abhängigkeiten, Risiken, Entscheidungen und erschütterte Grundlagen im Zusammenhang bearbeiten |
| 7.5 Kommunikation und Kalender | K3–K4 | Mail-/Meeting-Kontext, Entwurf/Antwort, offene Rückmeldung und kontrollierte Freigabe |
| 7.6 Aktuelle Außenwelt | K5-Außenwelt | Relevante neue Informationen mit Quelle, Aktualität und Bezug zu eigenen Vorhaben; Beobachtung opt-in |
| 7.7 Modell-Harness und Routing | K0, K5-Modelle | Einfache Einrichtung, Datenschutz/Kosten/Toolfähigkeit, Fallback und erkennbare Modellfehler |
| 7.8 Agentenarchitektur | K5-Agenten | Gemeinsames Gedächtnis, begrenzte Aufträge, Übergaben und überprüfbare Ergebnisse unter einer Policy |
| 7.9 Werkzeuge und Konnektoren | K3, K5-Werkzeuge | Einheitliche Rechte, Herkunft, Außenwirkung, Freigabe, Widerruf und Audit für jede Anbindung |
| 7.10 Browser- und Computersteuerung | K5-Browser | Nachvollziehbare Schritte, isolierte Sitzung, Fremdinhaltsgrenzen, Vorschau und Freigabe vor Außenwirkung |
| 7.11 Automationen und dauerhafte Prozesse | K5-Automationen | Zeit-/Ereignissteuerung, Warten, Neustart, Retry, Fehlerbehandlung, Pause und nachvollziehbarer Verlauf |
| 7.12 Geräte, Sprache, Mobilität | K5-Mac; Mobile später | Sprachinput und lokale Nutzung auf dem Mac. Mobile Oberfläche und geräteübergreifende Mobilabnahme sind ausdrücklich zurückgestellt |

## Wie wir vorhandene Arbeit erhalten

Die Basis bleibt `integration/icarus-main`; der noch nicht hochgeladene PC-Stand
wird vor dem Zusammenführen abgeglichen. Existierende Icarus-Implementierungen
und offene Foundation-Branches werden anhand der Funktionskontrakte geprüft
und übernommen. Abweichende UI-Implementierungen dürfen die Kingfisher-
Referenzen nicht überschreiben. Wir bauen keine Funktion erneut, wenn eine
passende, geprüfte Implementierung schon vorhanden ist.

K0 und K1 können unabhängig vorbereitet werden. K2 benötigt beide. K3 und K4
werden danach in vollständigen vertikalen Abläufen umgesetzt: Quelle →
Gedächtnis → Handlung → sichtbares Ergebnis. K5 ergänzt den vereinbarten
Umfang. K6 begleitet jede sichtbare Änderung, K7 schließt das Programm ab.

## Arbeitsteilung mit begrenzten Kosten

Zentral bleiben Produktumfang, Architektur, Migrationen, Sicherheitsgrenzen,
Zusammenführung und visuelle Abnahme. Günstigere Subagenten übernehmen klar
begrenzte Implementierungen, Adapter oder Vertragstests in benannten Dateien.
Sie bekommen nur den nötigen Kontext und dürfen ihren Auftrag nicht erweitern.

Ein typischer Auftrag enthält: Paket-ID, erwarteten Nutzungsablauf,
Schnittstellen, erlaubte Dateien und einen prüfbaren Fehlerfall. Es laufen nur
so viele Agenten gleichzeitig, wie unabhängig prüfbare Aufgaben vorliegen.
Der Verbrauch wird nicht durch eine behauptete Prozentersparnis bewertet,
sondern durch abgenommene Ergebnisse und notwendige Nacharbeit.

## Sichtbare Nachweise in jedem PR

Die [PR-Vorlage](../../.github/pull_request_template.md) verlangt:

1. Paket-ID und konkreten Nutzen mit Voraussetzungen/Abhängigkeiten.
2. Verweise auf Icarus-Vertrag und Kingfisher-Referenz.
3. Tatsächlich bestandene Prüfungen mit Commit, Befehlen und CI-Nachweisen.
4. Screenshots/Interaktionsnachweis bei UI-Änderungen und eine Abweichungsliste.
5. Ungeprüfte oder blockierte Punkte und den verbleibenden Teil des Pakets.
6. Angaben zu Migration, Wiederanlauf und gegebenenfalls Rückkehrweg.

Ein grüner automatischer Browserlauf zeigt Bedienbarkeit; er bestätigt nicht
von selbst die Übereinstimmung mit dem Design. Ein lokales Testmodell prüft
Integration und Persistenz; die Antwortqualität und Einrichtung mit einem
realen unterstützten Modell sind zusätzlich abzunehmen. Diese Grenzen werden
im PR ausdrücklich ausgewiesen.

## Nächster Liefernachweis

Der aktuelle Docker-Start wird von einer leeren Einrichtung aus geprüft:
kein vorkonfiguriertes Modell → Modell bewusst verbinden → Verbindung wirklich
testen → Gespräch und Gedächtnis verwenden → Container neu starten →
Konfiguration und Wissen erneut verwenden. Eine native macOS-Paketierung wird
dafür nicht entwickelt. Danach folgen die offene Modelleinrichtung in der
freigegebenen UI und die Personen-/Projektbedienung am gemeinsamen Gedächtnis.

Die CLI-Einrichtung ist ein nutzbarer Zwischenschritt. Sie ersetzt weder die
visuelle Abnahme noch den echten Test mit einem unterstützten lokalen Modell.

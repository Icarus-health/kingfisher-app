# Funktionsprüfung und nächste Verbesserungen

Stand: 7. Oktober 2026, Inventur ab `ec2e9e9` und erster anschließender Ausbau für das noch nicht installierte Update 1.0.6. Ziel: Kingfisher nimmt Such-, Erinnerungs- und Koordinationsarbeit ab. Bezug: [Zielbild](41-zielbild.md), [Kernablauf](59-kernablauf-gedaechtnis-cos.md) und [Alltagsabnahme](60-alltagsabnahme.md).

## Nachweisgrenze

Dies ist eine Prüfung der vorhandenen Implementierung und ihrer technischen Tests, **kein abgeschlossener visueller UX-Audit**. Der Mac steht für die Bedienprüfung noch nicht zur Verfügung. Lesbarkeit, tatsächlicher Klickaufwand, Tastaturbedienung, Fokus, schmale Fenster und Verständlichkeit werden erst am laufenden Produkt beurteilt. Die Tabelle hält die Ausgangslücken fest; der folgende Abschnitt benennt die inzwischen umgesetzte erste Teillieferung.

Auch der erfolgreiche breite Testlauf ist kein Nachweis für vollständige Aufnahme echter Konten oder die Qualität eines tatsächlich angeschlossenen Modells. Prüfstand und Grenzen stehen im [Laufbericht](runs/2026-10-07-core-workflow/README.md).

## Erste Teillieferung umgesetzt

- Bestätigte Aufgaben auf „Heute“ direkt erledigen, zurückholen oder mit den vorhandenen Aufgabenfeldern bearbeiten. Quelle und Änderungsverlauf bleiben erreichbar.
- Konkrete Aufgabenlinks laden die gespeicherte Kennung unabhängig von Listenbegrenzung oder Filter. Neu angelegte und angenommene Aufgaben sowie Mail-Aufgaben sind direkt erreichbar.
- Fälligkeitstage einheitlich bis 23:59 Ortszeit; unveränderte vorgeschlagene genaue Zeitpunkte bleiben erhalten. Das Datumsfeld und der angezeigte Zeitpunkt verwenden dieselbe lokale Zeitzone. Ein enger Datumshelfer bietet eindeutige absolute „bis“-Angaben aus der Originalstelle zur ausdrücklichen Wahl an. Er ersetzt keine semantische Fristenprüfung und ordnet kein Projekt automatisch zu.
- Mailverlauf mit Originaldatum, Originaltext und gespeicherter Quelle. Zuordnung über exakte, kontogebundene Antwortheader; keine Gruppierung allein nach Betreff. Nur aktuelle, nicht ausgeschlossene Fassungen; begrenzte Nachrichtenzahl, Textlänge, Beziehungstiefe und SQL-Arbeit. Neue Outlook-Aufnahmen behalten hierfür auch Antwortbezüge.

Das ist ein quellengestützter Verlauf, **noch keine verständliche KI-Zusammenfassung des gesamten Gesprächs**. Ältere Aufnahmen ohne Antwortheader und noch nicht aufgenommene Nachrichten können fehlen. Absagen erledigen keine bestätigte Aufgabe automatisch. Google-OAuth-Schreiben, terminierte Wiedervorlagen, Serienaufgaben und die priorisierte Darstellung aller Gedächtnisfragen bleiben offen. Der [Umsetzungsplan](plans/2026-10-07-direkte-alltagsablaeufe.md) begrenzt diesen ersten Ausbau; Tests und unabhängiges Review stehen im Laufbericht.

## Vorhandene Funktionen und ihre praktische Grenze

| Bereich | In der Implementierung vorhanden | Grenze oder nächste Verbesserung |
|---|---|---|
| Einrichtung und Quellen | Postfächer, Kalender, ausgewählte Ordner, Google-/Microsoft-Anmeldung und Freigaben; neuer sichtbarer KI-Bereich | Ein geführter Abschluss muss zeigen: verbunden, Umfang gewählt, aufgenommen, eingeordnet und tatsächlich nutzbar. Diese Zustände sind verschieden. |
| Heute | Tageslage, wichtige Punkte, Termine, Vorbereitungen, offene Zusagen, Quellenstatus und Logbuch | Direkte Bearbeitung vorhandener Aufgaben führt teilweise noch in die Aufgabenliste. Zu prüfen: die häufigen Handlungen direkt am Punkt erledigen, Kontext und Rückkehrposition erhalten. |
| Mail verstehen | „Auf einen Blick“, ausgewählte Originalstellen, mögliche nächste Schritte, Quellenaufnahme, Antwortvorschlag und Freigabe | Der Überblick arbeitet pro Nachricht mit Originalauszügen. Eine verständliche, belegte Zusammenfassung des ganzen Verlaufs mit Änderungen und Absagen fehlt in diesem Ablauf. |
| Aufgabe aus Mail | Schnelle Übernahme oder ausführliche Vorbereitung mit Quellenbezug | Die Schnellübernahme setzt `due`, `project_id` und `waiting_for` ausdrücklich auf `null`. Für verlässliche Fristen reicht das nicht: belegte Vorschläge vorbereiten, Unbekanntes offenlassen und die menschliche Wahl speichern. |
| Aufgaben verwalten | Anlegen, bearbeiten, erledigen, wieder öffnen, Projekt zuordnen, „Wartet auf“ mit Wartebeginn, Quellen und Verlauf; Vorschlagsprüfung mit Seiten/Zeitraumfilter | Für normale Aufgaben fehlen ein eigenes terminiertes Wiedervorlage-Datum und Serienfelder im geprüften Aufgabenmodell/Bedienweg. Der vorhandene Wartestatus ist eine Grundlage fürs Nachfassen. Wiederkehrende Angaben in Akten sind bereits vorhanden, ersetzen aber keine Serienaufgaben. |
| Kalender | Ansichten, Google-Kalender lesen, Kalenderabgleich, automatische Terminvorbereitung, Projektbezug, Nachbereitung und Mitschriften | Google-OAuth-Adapter ist ausdrücklich lesend. Das allgemeine CalDAV-Werkzeug kann Termine anlegen und nennt auch Google als Anbieter; es ist aber kein OAuth-Schreibfluss für die dort ausgewählten Kalender. Ein einfacher Ablauf für Anlegen, Ändern und Absagen über die bestehende Google-Anmeldung fehlt. |
| Gedächtnis und Suche | Originalquellen, automatische Einordnung, Akten/Personen/Projekte, Belege, Klärungsfragen, Aussagehistorie, Berichtigung, Quellenentzug und Timeline | Tatsächliche Vollständigkeit, Verwechslungen, Fristen und Widersprüche am echten Bestand messen. Begrenzte Kandidatensuche und vorsichtige Antworten sind kein Beweis, dass nichts übersehen wurde. |
| Gedächtnispflege | Hintergrundprüfung über Akten, Widerspruchsbefunde mit Entscheidungen, Logbuch, Rückmeldungen und Export als Prüffälle | Befunde sind auch unter „Für Techniker“ eingeordnet. Wichtige Rückfragen sollen im normalen Tagesablauf verständlich und priorisiert erscheinen, ohne die ganze Prüfverwaltung zu öffnen. |
| Handeln und Modelle | Antwortentwürfe, Quellenprüfung, protokollierte Freigaben; vorbereitete regionale Cloud-Zugänge | Ein einheitlicher Arbeitsweg für Rückfragen, Entwürfe und nächste Schritte muss vorhandene Abläufe verbinden. Cloud-Hintergrundaufbereitung, echter Kostenrahmen und Modellqualität sind weiterhin nicht nachgewiesen. |

### Nachvollziehbare Ausgangsstellen

- Heute und direkte Handlungswege: `app/kingfisher/src/TodayOverview.tsx`, `TagesLage.tsx`, `TodaySourceStatus.tsx`.
- Mail und Schnellübernahme: `app/kingfisher/src/MailBriefing.tsx`, `MailQuickTask.tsx`, `MailReader.tsx`; `sidecar/icarus_memory/mail_briefing.py`.
- Kalender: `app/kingfisher/src/CalendarPage.tsx`, `CalendarPreparation.tsx`, `TerminVorbereitung.tsx`, `CalendarFollowup.tsx`; `sidecar/icarus_memory/google_calendar.py`, `connectors/calendar.py`, `tools.py`.
- Aufgaben: `sidecar/icarus_memory/tasks.py`, `task_candidates.py`; `app/kingfisher/src/App.tsx` und `TaskSuggestions.tsx`.
- Pflege und Einstellungen: `sidecar/icarus_memory/lint_routes.py`, `logbuch_routes.py`; `app/kingfisher/src/Einstellungen/gliederung.ts`.

## Reihenfolge der nächsten Lieferungen

### 1. Einen verlässlichen Arbeitstag belegen

Die zwölf Abnahmefälle durchlaufen, den tatsächlichen Quellenumfang feststellen und das echte Modell gegen vorher festgelegte Antworten prüfen. Jede falsche Person, Frist oder verlorene Bedingung wird als wiederholbarer Prüffall erfasst. Bedienhürden werden am Mac beobachtet. Konkrete Fehler korrigieren, bevor neue Quellenarten dazukommen.

### 2. Die vorhandenen Abläufe in „Heute“ zusammenführen

Ein übersichtlicher Einstieg für wichtige Aufgaben, nötige Rückfragen, vorbereitete Antworten und Termine. Häufige lokale Handlungen direkt dort anbieten; die zugehörige Quelle bleibt erreichbar. Aufgabenverweise sollen die konkrete Aufgabe öffnen statt nur eine lange Liste. Wichtige Gedächtnisfragen erscheinen verständlich im Alltag. Als Abnahme messen: abgeschlossene Arbeitsschritte und notwendige Wechsel, nicht nur die Anzahl sichtbarer Knöpfe.

Das ist ein Ausbau des vorhandenen Designs. Eine komplette neue Oberfläche oder eine zusätzliche technische Schaltzentrale ist dafür nicht Voraussetzung. Die genaue Anordnung folgt dem beobachteten Mac-Ablauf.

### 3. Mail, Fristen und Kalender als durchgehende Arbeit nutzbar machen

Mailverläufe mit Quelldaten, aktuellen Änderungen und Absagen verständlich zusammenführen. Daraus Aufgabe, Rückfrage oder Antwort vorbereiten. Belegte Daten und Projekte vorschlagen, ungeklärte Werte nicht erraten. Anschließend den Kalender-Schreibablauf über die vorhandene Google-Anmeldung mit eng begrenzter Freigabe und idempotenten Aktionen ergänzen. Wiedervorlage und Serienaufgaben getrennt vom Fälligkeitsdatum behandeln: „morgen wieder ansehen“ ändert keine vertragliche Frist.

Diese Lieferung wird in kleine, überprüfbare Teile aufgeteilt. Kein pauschaler neuer Zugriff auf Postfächer, Kalender oder Cloudmodelle wird dafür still eingeschaltet. Nicht jede externe Aktion lässt sich rückgängig machen; vor dem Senden ist die Ausführung ausdrücklich zu prüfen.

## Später erweitern

Weitere Nachrichtenquellen wie WhatsApp/LinkedIn, mehr Modelle, zusätzliche private Rubriken und Serverbetrieb folgen dem belegten Nutzen des Kerns. Bestehende Microsoft-, Ordner-, Mitschriften- und Wiederkehrend-Funktionen zunächst praktisch prüfen, bevor dieselben Fähigkeiten nochmals gebaut werden.

Eine begrenzte unabhängige Codeprüfung bestätigte die Mailverlaufs-Lücke und präzisierte die Abgrenzung zwischen Wartestatus und terminierter Wiedervorlage sowie zwischen allgemeinem CalDAV-Anlegen und Google-OAuth-Schreibfluss. Dabei wurden keine Tests, Anbieteraufrufe oder Bedienprüfungen ausgeführt.

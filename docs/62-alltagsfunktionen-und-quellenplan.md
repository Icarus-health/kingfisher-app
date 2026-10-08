# Vom vorhandenen Kern zum täglichen Arbeitsablauf

Stand: 7. Oktober 2026, Entwicklungsbranch `feat/core-workflow-20261007`, nach `981f70e`. Ergänzt die [Funktionsprüfung](61-funktionspruefung-und-prioritaeten.md), ersetzt keine visuelle Abnahme. Persönliche Installation und Daten bleiben unverändert. Die folgenden offenen Lieferungen sind **nicht implementiert**, soweit sie nicht ausdrücklich als umgesetzt bezeichnet sind.

## Aktueller Funktionsstand

| Bereich | Vorhanden | Für den täglichen Gebrauch als Nächstes |
| --- | --- | --- |
| Aufgaben | Anlegen, Titel/Notizen/Frist bearbeiten, erledigen/zurückholen, Projekt, Warten auf andere, terminierte Wiedervorlage, Quelle, Verlauf und exakter Aufgabenlink | Vollständiges Finden auch bei großen Beständen; Suche und Filter; danach Serienaufgaben und Zeitplanung. |
| Kalender | Liste/Woche/Monat/Jahr, mehrere lesende Quellen, Vorbereitung und Nachbereitung, Projektzuordnung | Verlässliche Zeitraumnavigation über Jahresgrenzen und ehrliche Ladezustände; danach Anlegen/Ändern/Absagen über Google-OAuth. |
| Gedächtnis | Originalquellen, Quellen- und Erfassungszeit, Personen/Projekte/Akten, belegte Aussagen und Historie, Quellenentzug, Konfliktentscheidungen und Pflegebefunde | Ein verständlicher Arbeitsweg für offene Fragen und Korrekturen; Quellenumfang und Suchgrenzen sichtbar machen; echte Abrufqualität belegen. |
| Nachrichten | Konten, Mail-Originale und kontogebundene Verläufe, wörtlicher Überblick auf Wunsch, geprüfte Aufgabenübernahme | Den Weg „lesen → verstehen → entscheiden → Aufgabe/Antwort/Termin“ verbinden; alte Bitte, neue Änderung und Absage gemeinsam berücksichtigen. |

Die Oberfläche hat bereits viele der nötigen Bestandteile. Der nächste Ausbau verbindet diese Bestandteile; er braucht keine neue Hauptnavigation, keine neue Modellarchitektur und keinen zweiten Gedächtnisspeicher. Die konkrete Anordnung und Verständlichkeit werden am Mac geprüft. Aus Code und Komponenten allein folgt keine Aussage über Lesbarkeit, tatsächliche Klickzahl oder visuelle Qualität.

## Ausgangsbefunde vor dem Ausbau

1. **Aufgabenlisten begrenzen vor der fachlichen Auswahl.** `server.py::_task_view` filtert „Meine Aufgaben“ nach `open_tasks()` mit Standardgrenze 200; `tasks.py::wartend()` verwendet dieselbe bereits begrenzte Menge. Erledigte Aufgaben werden aus `all_tasks()` mit Grenze 500 gefiltert. `/api/v1/tasks` meldet diese Begrenzung nicht. Aufgaben können deshalb in einer Ansicht fehlen, obwohl sie gespeichert und per Kennung erreichbar sind. Die neue Wiedervorlagen-Abfrage arbeitet unabhängig davon; sie beseitigt diese Listenlücke nicht.
2. **Kalender ist auf das aktuelle Jahr begrenzt.** `CalendarPage.tsx` sperrt Navigation ins Nachbarjahr; `api.calendar()` fordert `year_view=true` an, `server.py::kingfisher_calendar` lädt dafür nur das aktuelle Jahr. Auch die nächsten sieben Tage können am Jahresende über die geladene Grenze reichen. Nur die Pfeile zu entsperren wäre keine vollständige Korrektur. Vorbereitung sucht ebenfalls im aktuellen Jahresbestand und muss bei einer späteren Erweiterung mitgeführt werden.
3. **Laufende mehrtägige Termine fehlten in der Siebentageliste.** Der Filter berücksichtigte nur den Beginn. **In dieser Lieferung korrigiert:** Tagesansicht und Liste verwenden dieselbe Zeitintervallprüfung (`calendarRange.ts`). Endzeiten sind exklusiv; Termine ohne nutzbare Endzeit erscheinen als Zeitpunkt am Beginn. Das erweitert nicht den vom Backend geladenen Zeitraum.
4. **Google-Kalender ist ausdrücklich lesend.** `google_calendar.py` und die vorhandene Anmeldung ersetzen keinen Schreibablauf. Ein allgemeines CalDAV-Werkzeug ist kein bereits fertiges Anlegen/Ändern/Absagen über die Google-Anmeldung.
5. **Prüfen ist auf mehrere Bereiche verteilt.** `KnowledgeQuestions.tsx`, `MemoryQuestions.tsx`, Personenprüfung und Aufgaben-Vorschläge bilden verschiedene fachliche Schritte ab. Bei Wissensfragen erscheinen technische Referenzen und Beziehungsnamen. Die gemeinsame Darstellung darf diese unterschiedlichen Entscheidungen verbinden, aber nicht ihre unterschiedlichen Belege oder Freigaben gleichsetzen.
6. **Verzeichnissuche ist keine vollständige Wissenssuche.** `MemoryDirectory.tsx` filtert Beschriftungen der bereits geladenen Knoten. Das darf nicht wie eine Volltextsuche in sämtlichen Quellen dargestellt werden. Quellen-/Chat-Suche und Verzeichnis haben verschiedene Suchräume.

## Umsetzungsstand am 7. Oktober

Aufgaben werden jetzt vor der Seitengrenze gefiltert und im gespeicherten Bestand gesucht; Gesamtzahl und Bestandswechsel sind sichtbar. Kalender laden den gewählten Zeitraum und konkrete Vorkommen über Jahresgrenzen. Wissensfragen und Pflegebefunde haben den normalen Arbeitsweg `/review`. Separate Google-Schreibrechte, persistente manuelle Entwürfe und ausdrückliche Ausführung sind mit künstlichem Anbieter gebaut. Automatische Mail → Termin-Übernahme und echter Mac-/Anbieternachweis bleiben offen. Details und Abnahmen im [Produktabschluss](63-cos-produktabschluss.md).

## Reihenfolge und Abnahme

### 1. Nichts Wichtiges unbemerkt ausblenden

Aufgaben nach Sicht und Projekt **vor** der Begrenzung in SQLite auswählen. Eine begrenzte, stabil sortierte Seitenschnittstelle mit sichtbarem Weiterblättern und Suche anbieten. Bei Änderungen darf eine alte Seite nicht still eine andere Aufgabe treffen; Schreibaktionen verwenden weiterhin die gespeicherte Kennung. Keine unbegrenzte Vollbestandsübertragung als Ersatz für Paginierung.

Abnahme mit künstlichen Daten: mehr als 200 offene Aufgaben, darunter viele wartende; mehr als 500 gemischte erledigte/offene Aufgaben; gesuchte Aufgabe außerhalb der ersten Seite. Jede passende Aufgabe bleibt erreichbar. Suche arbeitet im gespeicherten Bestand, nicht nur in der aktuellen Seite. Eine leere gefilterte Seite behauptet keinen leeren Gesamtbestand.

Kalender für den tatsächlich sichtbaren Zeitraum abfragen, einschließlich Wochen über Jahresgrenzen. Zeitraumwechsel darf alte Ergebnisse nicht unter einer neuen Monatsüberschrift zeigen. Fehler und noch nicht geladene Zeiträume bleiben von „keine Termine“ unterscheidbar. Vorbereitung/Nachbereitung müssen den gewählten Quelltermin und sein Vorkommen erreichen.

Abnahme: Dezember/Januar, Wochen über Jahresgrenzen, laufende mehrtägige Termine, ganztägiger Termin mit exklusivem Ende, Zeitumstellung, zwei gleichnamige Termine und Serientermine. Die aktuelle kleine Kalenderkorrektur deckt nur die Intervallauswahl ab.

### 2. Einen verständlichen Eingang für Entscheidungen

„Heute“ priorisiert fällige Aufgaben, heutige Termine und wenige tatsächlich nötige Rückfragen. Jede Rückfrage zeigt in Alltagssprache: worum es geht, Originalstelle mit Datum, was unklar ist und was die gewählte Aktion verändert. Direkt öffnen, beantworten oder für später vorlegen; keine technische Einstellungen-Seite als üblicher Arbeitsweg. Referenzkennungen nur als zusätzliche Details. Keine Person allein aus einem Namen erraten.

Abnahme: Eine geänderte Frist und eine Absage sind von einer aktuellen Bitte unterscheidbar. Eine unklare Person wird gezielt erfragt. Eine bestätigte Entscheidung verschwindet aus der offenen Liste, bleibt im Verlauf nachvollziehbar und übersteht Neustart. Eine inzwischen entzogene Quelle oder geänderte Entscheidung sperrt eine alte Bestätigung.

Die vorhandenen Tagesansichten anschließend am Mac auf Reihenfolge, Informationsmenge, Fokus und benötigte Wechsel prüfen. Kein pauschales neues Dashboard vor dieser Beobachtung.

### 3. Aus einer Nachricht eine abgeschlossene Arbeit machen

Originalverlauf → belegter nächster Schritt → Aufgabe, Antwortentwurf oder Terminentwurf. Zuständige Person, Projekt, Datum und Kalender nur aus nachprüfbaren Angaben übernehmen; Unklarheiten gezielt erfragen. Ein Entwurf ist keine ausgeführte Aktion.

Google-Schreibrechte separat und erst bei Bedarf anfordern. Vor einer Ausführung Zielkonto, Kalender, Teilnehmer, Zeitpunkt/Zeitzone und Änderungen anzeigen. Doppelklick, Wiederholung und Netzwerkabbruch dürfen keine doppelten Termine erzeugen. Benachrichtigungen an Teilnehmer und Absagen sind vor der Ausführung ausdrücklich erkennbar. Ein API-Aufruf ohne bestätigten Anbieterzustand darf nicht als erfolgreich erledigt erscheinen.

Serienaufgaben, Zeitblöcke und weitere Quellen danach ergänzen. Sie sind nützlich, aber nicht Voraussetzung, um zuerst einen einfachen Arbeitstag zuverlässig abzubilden.

## WhatsApp: offizielle API bevorzugt, nach dem Kernablauf

WhatsApp bietet einen [Chat-Export mit oder ohne Medien](https://faq.whatsapp.com/1180414079177245/) an. Der Nutzer bevorzugt inzwischen die offizielle API. Vor einer Umsetzung müssen wir deren Reichweite für den gewünschten Geschäfts- oder privaten Kanal prüfen. Ein bewusst ausgewählter lokaler Export ist eine begrenzte Alternative, kein verpflichtender erster Schritt. Das ist **keine laufende Synchronisation**. Die [Business Platform](https://business.whatsapp.com/products/business-platform/) ist für geschäftliche Kundenkommunikation beschrieben; daraus lässt sich keine allgemeine Anbindung des privaten Chatbestands ableiten. Ein inoffizieller verknüpfter Client wäre gesondert zu bewerten: WhatsApp weist auf mögliche [Kontosperren bei solchen Verknüpfungen](https://faq.whatsapp.com/378279804439436/) hin. Deshalb wird dafür hier keine Verbindung eingerichtet.

Die vorhandene Datei-/Quellenaufnahme kann die Grundlage sein. Der allgemeine TXT-Mitschriftenparser ersetzt jedoch keinen WhatsApp-Nachrichtenparser. Falls später ein Exportweg gewählt wird, gilt folgender geplanter enger Umfang:

- Export auswählen, Chat benennen, Zeitraum und erkannte Absender vor dem Import zeigen. Original unverändert erhalten; jede Nachricht bleibt auf ihre Originalstelle zurückführbar.
- Nachrichtenzeit und Importzeit getrennt speichern. Mehrdeutige Datumsformate oder fehlende Zeitzone klären, statt einen sicheren Zeitpunkt zu behaupten. Mehrzeilige Nachrichten, Systemmeldungen und fehlende Medien unterscheiden.
- Absender als quellenspezifische Identität aufnehmen. Gleiche Anzeigenamen ergeben keine automatische Personen-Zusammenführung; „Ich“ braucht eine ausdrückliche Zuordnung.
- Wiederholte oder überlappende Exporte erkennen. Exportdateien liefern nicht zwingend stabile Nachrichtenkennungen; gleichlautende Nachrichten nicht blind zusammenlegen. Unklare Überlappungen sichtbar machen.
- Alte Aufgabenbitten nicht als neue Aufgaben übernehmen. Eine spätere Änderung oder Absage mitprüfen; unsichere Zuständigkeit/Frist bleibt ein Vorschlag. Keine Nachrichten senden.
- Verarbeiteten Umfang, übersprungene Zeilen, Fehler, erste/letzte erkannte Nachricht und fehlende Medien melden. Aus einem Export allein keine Vollständigkeit des gesamten WhatsApp-Verlaufs behaupten.

Erste Abnahme ausschließlich mit künstlichen iOS-/Android-Textbeispielen: Mehrzeiler, zwei gleiche Namen, wiederholte Nachricht, überlappender Export, unklarer Tag/Monat, Medienplatzhalter, alte Bitte mit späterer Absage. Danach ein bewusst ausgewählter echter Chat durch den Nutzer. Kein Zugriff auf WhatsApp, Cloudaufruf oder neuer Kontozugang ist Bestandteil dieser Lieferung.

## Was vorerst nicht neu gebaut wird

Mehrere Agentenmodelle, eine neue Datenbank, ein zweiter Obsidian-Speicher, automatische Personenverschmelzung und zusätzliche private Rubriken lösen die oben bestätigten Arbeitslücken nicht. Bestehende Aufnahme, Pflege, Such- und Freigabewege gezielt fertigstellen; Abrufqualität separat an erwarteten Antworten und Quellen messen.

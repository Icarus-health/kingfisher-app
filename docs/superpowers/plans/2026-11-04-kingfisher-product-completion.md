# Kingfisher: fertiger persönlicher Chief of Staff — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Track deliverables with checkboxes. This is the product-level master plan; execute bounded packages, not every optional extension at once.

**Goal:** Eine hochwertige Mac-App, die Informationen zuverlässig mit Personen und Projekten verbindet, rechtzeitig die richtigen Zusammenhänge zeigt, Arbeit vorbereitet und durch kontrollierte Erweiterungen mitwachsen kann.

**Architecture:** Das vorhandene Gedächtnis bleibt die gemeinsame maßgebliche Datenhaltung. Skills beschreiben wiederverwendbare Verfahren; Module ergänzen Ansichten, Quellen und begrenzte Aktionen. Kingfisher entscheidet über Rechte, Datenfreigaben, Aktualität und Ausführung; die Agentenlaufzeit und Modelle bleiben austauschbar.

**Tech Stack:** Bestehendes Python/FastAPI-Backend, vorhandene persistente Stores, React/TypeScript/Vite, native Mac-Hülle, Ollama/Qwen9B/BGE-M3, getrennte optionale Harness-Laufzeit. Kein Framework- oder Datenbankwechsel als Voraussetzung.

**Spec:** [Freigegebenes modulares Zielbild](../specs/2026-11-02-modular-chief-of-staff-design.md), [freigegebener Bedienplan](2026-10-14-workspace-usability.md), Nutzerbriefing vom 04.11.2026. Dieser Gesamtplan ergänzt die bestehenden Vereinbarungen; historische Prüfprotokolle bleiben erhalten.

**Stand:** 04.11.2026. Planungsdokument, keine neue Abnahme. Technische Bestandsaufnahme am lokalen Entwicklungsstand `fb49545`; letzter ausgewerteter Mac-Nachweis vom 03.11.2026. In diesem Planungsschritt wurden weder Mac-Zustand noch GitHub live neu abgenommen.

## 1. Das fertige Produkt

Kingfisher ist der persönliche Arbeitsmittelpunkt: morgens wissen, was zählt; tagsüber Informationen finden und Arbeit erledigen; abends nachvollziehen können, was offen bleibt. Der Nutzer muss weder Datenpfleger noch Modelladministrator sein.

Das Ziel ist ein verlässlicher Assistent mit erkennbarem Nichtwissen. „Perfekt“ wird nicht als Fehlerfreiheit versprochen: Unklare Personen, fehlende Fristen und widersprüchliche Belege müssen sichtbar bleiben, statt durch eine überzeugende Antwort verdeckt zu werden.

Zwei verbindlich getrennte Lieferziele verhindern eine endlose Baustelle:

| Lieferziel | Enthalten | Abschluss |
|---|---|---|
| **Alltagsversion** | Gedächtnis, Skills, Mail, Kalender, Aufgaben/Projekte, Gespräche, Morgenbriefing, durchgängige Oberfläche, belastbare Einrichtung/Updates/Sicherung; schmale Erweiterungsschnittstelle | Pakete P0–P5 und echte Alltagsabnahme bestanden. Nutzbar, bevor zusätzliche Dienste fertig sind. |
| **Modulare Produktfassung** | Zusätzlich verständliche Erweiterungsverwaltung, geprüfte Installation/Deaktivierung/Updates und ein unabhängiges Referenzmodul | P6 bestanden. Neue Module können ergänzt werden, ohne den Gedächtniskern umzubauen. |

Health, weitere Messenger, Musik, Lernräume und ähnliche Erweiterungen bilden danach einzelne Produkteinheiten. Ihre stetig wachsende Wunschliste verschiebt diese beiden Ziellinien nicht. Versionsnummern werden erst bei der Veröffentlichung vergeben.

## 2. Was bereits da ist und was tatsächlich fehlt

| Bereich | Vorhandene Grundlage | Noch zu schließen |
|---|---|---|
| Gedächtnis | Originalquellen, Akten, Identitäten, Beziehungen, Zeitbezug, Belege, Korrektur/Entzug, Suche | Repräsentative Qualität im echten Ablauf; noch offene Kategorie-/Ankerfälle und direkte Rückfrage bei Namensmehrdeutigkeit |
| Skills | Essenzielle Markdown-Skills, Router, Verfahren mit Versionen, Vorschlägen und Kontextprüfung | Automatischen Abruf, Konflikte, Lernen, Widerruf und Alltagssprache zusammenhängend abnehmen |
| CoS-Oberfläche | Gespräche, Aufgaben, Mail, Kalender, Profile, Briefing; bereits überarbeiteter visueller Stil | Abläufe vereinfachen, Darstellung vereinheitlichen, relevante Inhalte stärker gewichten |
| Agenten/Module | 1.0.43: begrenzte lokale Arbeit an einer ausgewählten Quelle, getrennte Laufzeit und kontrollierte Werkzeuge | Dies ist noch keine vollständige Erweiterungsplattform; echte Modellabnahme und verallgemeinerter Modulvertrag fehlen |
| Mac/Betrieb | Letzter Nachweis: App-Hülle und Backend 1.0.43, Originale erhalten, Kalender und lokale Inhalte erreichbar | Modellprüfung unter ausreichender Speicherreserve, Dauerbetrieb und Alltagswoche |

Der Großimport bleibt pausiert. Die bisherige Installation und die grünen Tests belegen nicht, dass alle persönlichen Quellen korrekt verstanden werden. Ältere Roadmap-Prozentwerte und pauschale Aussagen wie „lokal reicht nicht, Cloud reicht“ werden nicht als aktuelle Produktabnahme übernommen.

## 3. Global Constraints

- Originale, stabile Identitäten, bestätigte Nutzerkorrekturen, Konten und Quellenhistorie erhalten; keine Neuinstallation mit Datenverlust.
- Gedächtnis ist die maßgebliche Wissensbasis; kein zweites konkurrierendes Agentengedächtnis.
- Quelle berichtet, Modell vermutet und Nutzer bestätigt bleiben unterscheidbar.
- Großimport erst nach bestandener Qualitätsprobe und innerhalb einer tatsächlich freigegebenen Daten-/Kostenregel; dieser Plan aktiviert nichts.
- Qwen9B und BGE-M3 bleiben Standard. Mistral und bestehende weitere Cloudzugänge sind optionale, ausdrücklich erlaubte Wege. Keine automatische Cloudweitergabe wegen lokaler Langsamkeit.
- Keine persönlichen Quellen, Schlüssel oder privaten Prüfberichte in GitHub. Öffentliche Nachweise mit künstlichen Daten; private Nachweise geschützt lokal.
- Keine Nachricht versenden, Buchung auslösen oder fremde Daten löschen, ohne passende tatsächliche Nutzerfreigabe. Wiederholte Ausführung darf keine Dubletten erzeugen.
- Keine Modellarbeit beim bloßen Blättern; Hintergrundarbeit begrenzt, unterbrechbar und mit verständlichem Fortschritt.
- App, Backend, Schema, Modulversion und getesteter Modellstand werden getrennt dokumentiert. Veröffentlicht, installiert und im Alltag bestanden sind unterschiedliche Zustände.

## 4. Review Focus

1. Ein Weiterleitungs-/Signaturblock nennt eine andere Person als den tatsächlichen Auftraggeber: Identität und Verantwortung dürfen nicht vermischt werden. Test in P0/P1.
2. Eine Nachricht ändert nur einen Termin; eine frühere Abgabefrist bleibt bestehen: beide Zeitarten und Quellenstände getrennt behandeln. Test in P1/P3.
3. Eine Quelle, ein Skill oder eine Freigabe ändert sich während laufender Modellarbeit: das alte Ergebnis darf nicht als aktuell übernommen werden. Test in P1/P2/P6.
4. Speicher wird knapp, der Mac schläft ein oder der Prozess wird nach bereits erfolgter Aktion beendet: sicher wiederaufnehmen, ohne Doppelarbeit und ohne verlorenen Entwurf. Test in P0/P3/P5.
5. Ein Plugin oder eine Mail enthält Anweisungen, mehr Daten zu lesen oder Befugnisse auszuweiten: als unberechtigten Inhalt behandeln; keine Rechteausweitung. Test in P2/P6.

## 5. Bedienung und Erscheinungsbild

### Informationsarchitektur

Die Hauptnavigation zeigt **Heute, Gespräche, Aufgaben, Kalender, Nachrichten und Gedächtnis**. Erweiterungen sind ein eigener Zugang mit optional angehefteten Favoriten. Einstellungen bleiben unten; Skills erscheinen im normalen Gebrauch als „Meine Abläufe“. Ihre technische Verwaltung ist kein zusätzlicher Pflichtweg im Alltag.

Eine globale Suche findet Personen, Projekte, Aufgaben, Nachrichten und Dokumente. Ein gemeinsamer Eingang sammelt Vorschläge und Rückfragen; keine parallelen Prüflisten in jedem Bereich. Einträge bleiben an ihrer jeweiligen Quelle erreichbar.

| Ansicht | Auf den ersten Blick | Erst bei Bedarf |
|---|---|---|
| Heute | Nächster Termin, wichtigste Aufgaben, Antworten/Entscheidungen, die wirklich nötig sind | Vollständiges Briefing, Belege, vergangene Änderungen |
| Gespräche | Verlauf, lesbare Antwort, Eingabe mit Datei/Diktat | Verwendete Quellen, ausgewählte Skills, Ausführungsschritte |
| Aufgaben | Überfällig, heute, demnächst, ohne Termin; Zuständigkeit und Projekt | Details, Herkunft, Chronik, Wiederholungs-/Automationsregeln |
| Projekt | Ziel, Stand, nächster Schritt, offene Aufgaben, Beteiligte | Board, Entscheidungen, Dokumente, abgeschlossene Vorgänge |
| Nachrichten | Konten, klare Liste, gut gesetzter Nachrichtentext, kurze Zusammenfassung und relevante Aktion | Kopfzeilen, kompletter zitierter Verlauf, Analysebegründung |
| Kalender | Woche mit Zeitraster, Kalenderfarben, Konflikte, nächster Termin | Vorbereitung, Teilnehmer, Originalquelle, belegte Spiegelkopien |
| Personenakte | Wer ist das, was verbindet uns, letzter belegter Kontakt, offene Zusagen | Beziehungen, Projekte, Timeline, Dokumente, Vollquellen |
| Gedächtnisübersicht | Menschen, Projekte, Dokumente und Lebensbereiche; Suchfeld | Organisationsgruppen, Orte, Themenfilter, Pflege und Verlauf |
| Einstellungen | Konten, KI-Betriebsart, Importstatus, Sicherung/Update | Kosten-/Datendetails und „Für Techniker“ |

Die Akte führt schrittweise von Überblick zu Beziehungen und Zeitverlauf, dann zu belegten Einzelinformationen und zum vollständigen Original. Zusammenfassungen tragen einen Stand und dürfen widersprüchliche Aussagen nicht glattbügeln.

### Visuelle Richtung

Die gewählte Variante 3 bleibt Grundlage: dunkles Eisvogelblau in der Navigation, helle beziehungsweise dunkle ruhige Arbeitsflächen, erkennbare Marke und zurückhaltende Landschaft. Die bestehenden `NordicWorkspace.css`-Farben werden konsolidiert, nicht durch ein fremdes Komplett-Theme ersetzt.

- Ein gemeinsames System für Farben, Schriftgrößen, Abstände, Rahmen, Fokus und Zustände. Kleine lokale Stilkorrekturen dürfen nicht zu einer weiteren Schicht widersprüchlicher CSS-Overrides werden.
- Systemnahe Schrift; bestehende lokal verfügbare Schrift prüfen. Ausgangswerte: 15–16 px Lesetext, 13–14 px Metadaten, 22–28 px Seitentitel. Zoom und größere Schrift müssen funktionieren.
- Eine klare Hauptaktion je Arbeitssituation. Häufiges direkt erreichbar; seltene Aktionen in einem verständlichen Menü. Unsicherheit, fehlgeschlagenes Speichern und notwendige Freigaben bleiben sichtbar.
- Menschen, Dokumente und Projekte durch Initialen/Bilder, Dateivorschauen und gezielte Farbakzente erfassbar machen. Farbe unterstützt Bedeutung, ersetzt keine Beschriftung.
- Navigation, Inhaltsliste und Details räumlich klar trennen. Bei schmalem Fenster wird das Detail zur vollständigen Ansicht mit erhaltenem Rückweg.
- Abstände, Typografie und Kontrast schaffen Qualität. Transparenz nur sparsam in der Bedienebene; Nachrichtentext und Quellen auf gut lesbaren Flächen.
- Adaptiv bedeutet: passende Details, Fensterbreite und Arbeitszustand berücksichtigen. Navigation und wichtige Aktionen springen nicht unvorhersehbar herum.
- Entwürfe, Suche, Auswahl und Scrollposition bleiben erhalten. Tastatur und VoiceOver werden an echten Kernabläufen geprüft; reduzierte Bewegung und Hell-/Dunkelmodus berücksichtigen.

Dafür dienen Apples Empfehlungen zu [Layout](https://developer.apple.com/design/human-interface-guidelines/layout), [Split Views](https://developer.apple.com/design/human-interface-guidelines/split-views), [Materialien](https://developer.apple.com/design/human-interface-guidelines/materials) und [Barrierefreiheit](https://developer.apple.com/design/human-interface-guidelines/accessibility) als Referenz. Die konkrete Gestaltung bleibt Kingfisher. UI/UX Pro Max unterstützt die Prüfung; generische Landingpage-Empfehlungen werden nicht auf die Arbeitsoberfläche übertragen.

**Gestaltungsablauf:** Zuerst drei repräsentative, gefüllte Ansichten abstimmen: Heute, Nachricht mit Aufgabe und Personenakte. Danach dieselben Bausteine auf die übrigen Bereiche übertragen. Zusätzlich leere, lange, fehlerhafte und ladende Zustände gestalten. Kein neuer Komplettentwurf für jede Seite.

## 6. Gedächtnis und Skills als gemeinsamer Kern

### Eingang → Verständnis → Akte → Wiederfinden

1. Quelle unverändert aufnehmen, Herkunft, Konto, Zeitpunkt und Version erhalten. Bei Mail: Absender, Empfänger, Thread, Gesendet-Ordner und Anlagen getrennt berücksichtigen.
2. Dubletten und bereits bearbeitete Fassungen erkennen. Billige Vorfilter nutzen Absender/Betreff/Regeln; Unklares nicht wegwerfen. Automatische Absender können wichtige Rechnungen oder Fristen enthalten. Newsletter-Auswahl bleibt konfigurierbar.
3. Personen, Beziehungen, Bitten, eigene Zusagen, Aufgaben, Termine, Fristen und optionale Bedingungen mit Beleg extrahieren. Ereigniszeit, Quellenzeit und Einlesezeit getrennt speichern.
4. Passende bestehende Identitäten/Projekte begrenzt suchen. Bei mehreren Alex zuerst klären; Signatur oder Namensähnlichkeit allein beweisen keine Identität.
5. Sichere belegte Angaben als solche ablegen; unsichere Zuordnungen gesammelt zur Prüfung stellen. Bestätigte Fakten und aus einer Quelle abgeleitete Aussagen bleiben verschieden. Wiederholte Hinweise müssen nicht immer dieselbe Nutzerfrage erzeugen.
6. Akten und Suchindex nachvollziehbar aktualisieren. Änderungen markieren abhängige Antworten, Zusammenfassungen und Skills als veraltet; Nutzerkorrekturen nicht überschreiben.
7. Beim Abruf Personen-/Projekt-/Zeitbezug und Rechte bestimmen; gezielte Suche, Erweiterung bei Bedarf, aktuelle Belege prüfen. „Nicht gefunden“, „nicht vollständig geprüft“ und „in diesen Quellen keine Frist genannt“ sind verschiedene Antworten.

Die Ersteinrichtung bearbeitet ein Archiv in kontrollierten Paketen. Der Regelbetrieb bearbeitet Änderungen und neu eingegangene Quellen. Eine Wartungsschleife prüft geänderte Beziehungen, Dublettenvorschläge, veraltete Zusammenfassungen und offene Konflikte; sie liest nicht jeden Tag das gesamte Archiv erneut durch ein teures Modell.

### Skills

| Ebene | Zweck | Beispiel |
|---|---|---|
| Essenzielle Verfahren | Stabile, kurze Grundregeln; passend verfügbar | Quelle prüfen, Person klären, Erinnerung abrufen, Aktion freigeben |
| Kontextbezogene Verfahren | Nur bei passender Aufgabe laden | Offizielle Vereinsmail, Terminvorbereitung, Projektplanung, Dokumentvergleich |
| Persönliche Präferenzen | Daten mit Geltungsbereich, keine vervielfachten ausführbaren Skills | Alex duzen; Vorstandsmail sachlich; bestimmte Anrede |

Der „Master-Skill“ ist der bereits angelegte Router, ergänzt durch eine überprüfbare Auswahlsteuerung: Auftrag erkennen → Kategorie und Rechte eingrenzen → aktive passende Verfahren suchen → höchstens wenige passende Verfahren laden → Konflikte klären. Ein Modell darf Vorschläge machen; die tatsächliche Freigabe und Auswahlgrenzen werden im Code durchgesetzt.

Fehlt ein Verfahren, kann der erlaubte allgemeine Ablauf trotzdem helfen. Ein neuer Skill wird nur als Entwurf angeboten, wenn Wiederverwendung plausibel ist oder der Nutzer es ausdrücklich wünscht. Einmalige Fakten gehören in die Akte. Die Skillbibliothek soll nicht bei jeder Nachricht wachsen.

Ein Skill enthält Kennung, Version, Kategorie, Auslöser, Geltungsbereich, benötigte Werkzeuge, Schritte, Ergebnisprüfung, Abbruch-/Rückfragebedingungen, Positiv- und Gegenbeispiel sowie Herkunft/Abhängigkeiten. Markdown bleibt lesbar; strukturierte Metadaten werden validiert. „Bestätigt“ ersetzt keine technische Berechtigung.

Lernweg: Beobachtung/Korrektur → inaktiver Vorschlag → Prüfung auf Duplikat, Konflikt und Beispiele → verständliche Bestätigung → aktiv. Änderung oder Entzug löst eine erneute Prüfung betroffener Verfahren aus. Herkunft aus einer Mail erteilt niemals automatisch Ausführungsrechte. Wir messen Auswahlqualität, Tokens und Zeit; mehr Skills sind kein Erfolgskriterium.

## 7. Erweiterungen: ein gemeinsamer Arbeitsplatz

„Alles als Plugin“ ist als klare Modularisierung sinnvoll. Stabile Gedächtnisdaten, Rechteprüfung und Sicherung bleiben ein gemeinsamer Kern. Bestehende Ansichten werden schrittweise an Modulgrenzen angeschlossen; kein Neuaufbau als viele kleine Dienste.

### Vier Integrationsstufen

| Stufe | Nutzererlebnis | Grenze |
|---|---|---|
| Verknüpfung | Dienst aus Kingfisher öffnen | Keine automatische Übernahme oder Steuerung |
| Eingebettete Ansicht | Dienst, sofern unterstützt, innerhalb eines Arbeitsbereichs sehen | Anmeldung, Einbettung und Anbieterbedingungen beachten; Sichtbarkeit ist kein Datenzugriffsrecht |
| Datenverbindung | Freigegebene Inhalte über API oder Import mit Quellenbezug übernehmen | Umfang, Konto, Zeitraum, Aktualisierung und Widerruf festlegen |
| Aktionsmodul | Entwurf, Wiedergabe, Termin oder andere konkrete Aktion vorbereiten/ausführen | Eigene Rechte, aktuelle Freigabe, Wiederholschutz und Ergebnisprüfung |

ChatGPT oder Claude als angezeigter Dienst ist etwas anderes als ihre Modell-API. Login, Abo und API-Abrechnung dürfen nicht gleichgesetzt werden. Bei Diensten ohne geeignete Schnittstelle bleibt es bei Verknüpfung oder erlaubtem Import; keine Umgehung gesperrter Einbettung oder Anmeldung.

### Vertrag eines Moduls

- Identität, Version, Herkunft, Integritätsnachweis und kompatible Host-Version.
- Beitrag zur Oberfläche: Ansicht, Suchtreffer, Briefingelement oder Aktion nach gemeinsamen UI-Bausteinen.
- Explizite Fähigkeiten: lesen, Vorschlag erstellen, bestätigte Aktion ausführen; getrennt nach Datentyp, Konto und Geltungsbereich.
- Zugelassene Netzziele, verwendeter Modellanbieter, Zeit-/Kosten-/Lastbudget und lokale Aufbewahrung.
- Quellenereignisse mit stabilen externen IDs und Versionen. Vorschläge durch dieselben Bestätigungswege wie die Kernfunktionen.
- Zustände für Einrichtung, aktiv, pausiert, Fehler, deaktiviert und Aktualisierung; pro Vorgang ein nachvollziehbares Ergebnis.
- Deaktivierung stoppt neue Arbeit und entzieht Zugriff. Historische Quellen bleiben mit Herkunft erhalten, sofern der Nutzer nicht ausdrücklich deren Entfernung wählt.
- Updates dürfen neue Rechte nicht still aktivieren. Fehler eines Moduls dürfen Kalender, Chat oder Gedächtnis nicht lahmlegen.
- Drittcode hat keinen direkten Store-/Schlüsselzugriff und kein allgemeines Terminal. Laufzeit und Datenfreigaben werden unabhängig geprüft.

DeepSeek Harness kann die Ausführung übernehmen, wenn die konkreten Anforderungen belegt erfüllt sind. Es bestimmt nicht die Datenstruktur und darf ersetzbar bleiben. Ein Harness allein macht fremde Apps nicht steuerbar.

### Erweiterungskatalog für das Zielprodukt

| Erweiterung | Sinnvoller Umfang | Einordnung |
|---|---|---|
| Dateien, Notizen, Evernote/weitere Ablagen | Auswahl, Import, Versionen, Originalvorschau, Volltext, Projektbezug | Vorhandene Wege in der Alltagsversion prüfen; weitere Connectoren einzeln |
| Stimme | Diktieren, Transkripte, Antworten/Briefing vorlesen; später Gespräch | Vorhandene Aufnahme wiederverwenden; kleine lokale Modelle separat auf Deutsch, Zeit und Last prüfen |
| Gesundheit | Medikamente, Messwerte, Befunde, Verlauf und vorbereitete Fragen | Bestehende Ansätze inventarisieren; besonders geschütztes Modul, keine eigenmächtigen Therapieänderungen |
| Lernen / Grow | Ziele, Lernnotizen, Wiederholung, persönliche Fortschritte | Vorhandene Ziel-/Lernbereiche nutzen, ohne neue parallele Faktensammlung |
| Außenwelt / Pulse / Atlas | Gewählte Nachrichtenquellen, Themen, Reise-/Ortsbezug | Öffentliche Berichte getrennt von persönlichen Fakten; Datum, Quelle, Interessen und Drosselung |
| Messenger / Social | Freigegebene Gespräche, Rückmeldungen, Entwürfe | WhatsApp/LinkedIn usw. jeweils auf tatsächlich mögliche Kontotypen/API/Export prüfen |
| Spotify / Medien | Sammlung oder Wiedergabe erreichbar, optional passende Routine | Nur benötigte Rechte; nicht jeder Musiktitel wird Gedächtniswissen |
| ChatGPT / Claude / weitere KI | Anbieterwahl, eigenes Dienstfenster oder bewusste Übergabe ausgewählter Inhalte | Kein stilles Teilen des gesamten Gedächtnisses; Dienstzugang und API getrennt |
| Finanzen / Verträge | Vertragsakten, Belege, Laufzeiten, Kündigungs-/Zahlungsfristen | Keine unbeaufsichtigten Zahlungen; korrekter Rechtspartner bleibt erhalten |
| Passwörter | Zugang über macOS-Schlüsselbund oder bewährten Passwortmanager | Kein eigener KI-Passwortspeicher; Geheimnisse nicht in Gedächtnis, Logs oder Prompts |
| Browser / Recherche | Ausgewählte Seite erfassen, begrenzte Recherche, später freigegebene Interaktion | Eigene Berechtigungs- und Prompt-Injection-Prüfung; keine globale Browserkontrolle |
| Server / weitere Geräte | Dieselben Akten und Aufgaben von mehreren Geräten | Nach stabiler Mac-Fassung: Authentifizierung, Verschlüsselung, Konflikte, Backups und Ersatz lokaler Mac-Funktionen prüfen |

Der Katalog ist die vollständige Richtung, kein Versprechen, jeden Dienst gleichzeitig zu integrieren. Schon vorhandene Teilfunktionen werden verbessert und abgenommen, nicht noch einmal gebaut.

## 8. Umsetzung in getrennt abnehmbaren Paketen

### P0 — Verbindlichen Stand und offene Kernfehler schließen

**Anknüpfung:** `docs/65-ziellinie.md`, bestehende Run Records; `sidecar/icarus_memory/{task_modality,working_memory_identity,people_quality,model_routing,ollama_memory}.py`; `scripts/probe_intake_precision.py` und vorhandene Mail-/Gedächtnisproben.

- [ ] Eine aktuelle Matrix aus „gebaut“, „synthetisch geprüft“, „echtes Modell geprüft“, „auf dem Mac geprüft“, „im Alltag bestanden“ anlegen; ältere widersprüchliche Aussagen mit datiertem Verweis einordnen, nicht löschen.
- [ ] Die noch offenen Kategorien-/Quellenankerfehler und Personenrückfragen mit konkreten Original-Gegenfällen reproduzieren. Nur identifizierte Ursachen ändern; Regression plus Gegenbeispiel je Fehler.
- [ ] Nach bestätigter Speicherreserve die reale Qwen9B-/BGE-M3-Probe im installierten Ablauf durchführen; auch Abbruch, Quellenänderung und Wiederaufnahme prüfen.
- [ ] Laufzeitbegrenzung, Vorfilter und wartende Jobs gemeinsam messen; auf dem Mac währenddessen Mail, Kalender und Texteingabe bedienen.

**Abnahme:** Kein bekannter kritischer offener Fehler im nächsten Stichprobenweg; klare Erklärung fehlender Fristen und direkte Klärung mehrdeutiger Personen. Reale Probe separat dokumentiert. Der Großimport bleibt zunächst pausiert.

### P1 — Gedächtnisaufnahme, Pflege und Abruf alltagstauglich abnehmen

**Anknüpfung:** `sidecar/icarus_memory/{ingest,mail_filter,working_memory_worker,task_review,claim_index,evidence_answer,memory_questions}.py`; `scripts/{probe_mail_intake_quality,probe_memory_core_lifecycle,probe_working_memory_end_to_end}.py`.

- [ ] Eingangsweg und Rückweg für Personen, Projekte, Aufgaben, Fristen und Anhänge gemeinsam prüfen; nicht nur einzelne extrahierte JSON-Felder.
- [ ] Bestehende Fehlzuordnungen als überprüfbare Korrekturliste behandeln. Zusammenführen und Rücknahme müssen Originale, Beziehungen und Suchergebnisse konsistent halten.
- [ ] Zeit, Eigentümerschaft, Bitte/Zusage, optionaler Wunsch, Termin/Frist und historische Nachricht in getrennten Prüffällen abdecken.
- [ ] Kostenarme Vorauswahl gegen wichtige automatische Mails und gewählte Newsletter testen. Aussortierte Quellen auffindbar halten; Fehlfilter korrigierbar machen.
- [ ] Geänderte Quellen gezielt nacharbeiten; abhängige Aktenübersichten und Abrufantworten entwerten, ohne bestätigte Nutzerfakten still zu ersetzen.
- [ ] Kleine gemischte Stichprobe und danach einen zuvor nicht zur Fehleroptimierung genutzten Satz prüfen. Cloud nur innerhalb tatsächlicher Freigaben.

**Abnahme:** Qualitätsmatrix aus Abschnitt 9 bestanden. Ein kleines freigegebenes Paket kann end-to-end einsortiert, korrigiert und wiedergefunden werden; jede ausgelassene/fehlgeschlagene Quelle bleibt sichtbar.

### P2 — Skillbibliothek und kontrolliertes Lernen fertigstellen

**Anknüpfung:** `sidecar/icarus_memory/{procedures,procedure_model,procedure_routes,learning_patterns,learning_service}.py`, `sidecar/icarus_memory/procedure_skills/`, `app/kingfisher/src/ProcedureSettings.tsx`.

- [ ] Bestehende Kategorien und zwei unabhängige Dimensionen verwenden: essenziell/bei Bedarf sowie Suche, Kommunikation, Planung, Analyse/Arbeit. Keine unübersichtliche Ordnerhierarchie.
- [ ] Router, Geltungsbereich, Priorität bestätigter Korrekturen und mehrere gleichzeitig passende Verfahren prüfen; Konflikt zeigt Rückfrage statt stiller Auswahl.
- [ ] Wiederholte Korrektur in einen verständlichen inaktiven Lernvorschlag überführen. Neue Vorschläge auf Duplikate und notwendige Reichweite prüfen.
- [ ] Beispiel, Gegenbeispiel, Quelle, Version, Rechtebedarf und Rücknahme gemeinsam darstellen. Nach Änderung/Entzug alte Ergebnisse und Caches nicht weiter anwenden.
- [ ] „Warum dieser Ablauf?“ bei Bedarf anzeigen; der normale Nutzer muss keine Markdown-Datei bearbeiten.

**Abnahme:** Vereinsmail nutzt den passenden Ton, eine private Mail übernimmt ihn nicht; Namensdaten bleiben Fakten. Kein ungenehmigter Skill wird aktiv. Messprobe zeigt passende Auswahl ohne unnötige Lade-/Modellrunden.

### P3 — Durchgehenden CoS-Arbeitsablauf fertigstellen

**Anknüpfung:** vorhandene Mail-, Kalender-, Aufgaben-, Projekt- und Morgenrouten; `app/kingfisher/src/{TodayOverview,MailReader,MailThreadSummary,SavedMailWorkflow,CalendarPage,ConversationNavigation,SourceWork}.tsx`, `sidecar/icarus_memory/{morning,project_suggestions,mail_thread_summary,calendar_actions}.py`.

- [ ] Mail → Kurzüberblick → Aufgabe mit Projekt → Kalender/Vorbereitung → Rückmeldung → späterer Abruf als einen Ablauf prüfen und unnötige Zwischenseiten entfernen.
- [ ] Aufgaben- und Projektzuordnung gemeinsam bestätigen; Eigentümer, Frist und Quelle vor dem Speichern sichtbar. Teilfehler einer Sammelaktion pro Eintrag melden.
- [ ] „Warte auf andere“, eigene Zusagen und Erledigungsvorschläge trennen. Eine versandte Mail allein erledigt keine Aufgabe automatisch.
- [ ] Briefing nur aus aktuellen zugelassenen Daten vorbereiten, mit kurzem Hinweis auf ungeprüfte Bereiche. Keine zusätzliche Aufgabe allein aus einem Termin erzeugen.
- [ ] Lokale Mails und vorhandene Kalenderdaten bleiben bei Verbindungsproblemen lesbar. Frische, Kontozuordnung und Schreibfähigkeit werden getrennt angezeigt.
- [ ] Entwurfserhalt, wiederholtes Bestätigen, Providerfehler, Zeitzone/Sommerzeit und wiederkehrende Termine prüfen.

**Abnahme:** Fünf reale Tagesabläufe ohne Entwicklerhilfe; keine wiederholte manuelle Übertragung von Mailinhalt in Aufgaben, Akten oder Vorbereitung, wenn die Information bereits verlässlich erkannt wurde.

### P4 — Einheitliche hochwertige Oberfläche ausliefern

**Anknüpfung:** `app/kingfisher/src/{App.tsx,styles.css,NordicWorkspace.css,MemoryDirectory.tsx,MailReader.tsx,CalendarPage.tsx,TodayOverview.tsx,SettingsSections.tsx}` sowie vorhandene Detail-, Profil- und Arbeitsflächenkomponenten.

- [ ] Drei repräsentative Entwürfe mit künstlichen Inhalten und Zuständen erstellen; den vom Nutzer gewählten Stil fortführen und gezielt schärfen.
- [ ] Typografie, Farbe, Abstände und Bedienzustände in bestehenden gemeinsamen Bausteinen vereinheitlichen. Überholte konkurrierende Regeln bei ihrer Ablösung entfernen.
- [ ] Die vereinbarte Hierarchie „Wesentliches → Detail → Beleg“ überall anwenden. Überflüssige Hilfetexte entfernen, notwendige Entscheidungen gut erklären.
- [ ] Zuordnung, Auswahl, Rückweg, Suche und Tastaturbedienung an echten Aufgaben messen. Keine bloße Screenshot-Abnahme.
- [ ] Bei 900, 1.280 und 1.440 Pixeln sowie 200 % Zoom prüfen; kein Verlust primärer Aktionen. Hell/Dunkel, Kontrast, Fokus, VoiceOver-Kernwege und reduzierte Bewegung einschließen.

**Abnahme:** Nutzer findet nächste Aktion und wichtigsten Inhalt in repräsentativen Ansichten ohne Erklärung. Aufgabe samt Projekt aus der sichtbaren Mail in einem Bestätigungsdialog; Originalbeleg aus der Antwort mit einem direkten Zugriff. Details bleiben vollständig erreichbar.

### P5 — Betrieb und kontrollierten echten Import abschließen

**Anknüpfung:** `sidecar/icarus_memory/{hintergrund,hintergrund_cloud,recovery_bundle,local_module_controller}.py`, vorhandene Mac-Starter/Updater/Sicherungshelfer und Einrichtungsansichten. Bestehende native Implementierungsorte vor Änderung gezielt ermitteln.

- [ ] Ersteinrichtung und Regelbetrieb im UI klar trennen: Umfang wählen, Kosten/Datentransfer sehen, Paket starten, Fortschritt/Arbeitsschritt/Fehler sehen, pausieren und fortsetzen.
- [ ] Zunächst höchstens einen generativen Hintergrundjob gleichzeitig; Nutzeraktionen haben Vorrang. Embedding und Generierung nur gemeinsam, wenn gemessene Reserve reicht. Kontext/Teilung begrenzen statt das größte Modellfenster auszunutzen.
- [ ] Bei anhaltendem Speicherdruck Hintergrundarbeit drosseln/pausieren. Akkubetrieb, Ruhezustand und fremde Modellnutzung berücksichtigen. Ausgelagerten Speicher allein nicht mit aktueller Überlast gleichsetzen.
- [ ] Nach P1 kleine echte Pakete mit Protokoll fortsetzen, z. B. 20, dann 100. Größere Pakete erst nach Qualitäts-, Last- und Kostenkontrolle. Wiederaufnahme überspringt nachweislich abgeschlossene Fassungen.
- [ ] Datensicherung samt Wiederherstellung, Update/Rückweg, Schlüsselaufbewahrung, abgelaufene Anmeldung und knappen Speicher im Produktweg prüfen. Aufbewahrungsregeln vermeiden wiederkehrende manuelle Notlöschungen; vorhandene Backups nicht ohne passende Freigabe entfernen.
- [ ] Eine echte Nutzungswoche durchführen; erkannte Fehler gezielt schließen und betroffene Gegenfälle erneut prüfen. Keine zusätzlichen Featurewünsche in diese Abnahme aufnehmen.

**Abnahme:** Alltagsversion nutzbar. Eingelesen, eingeordnet, prüfbedürftig, bewusst ausgelassen und fehlgeschlagen sind getrennt gezählt. Kein stiller Verlust, keine unbemerkten Kosten und kein dauerhaft blockierter Mac.

### P6 — Erweiterungsplattform als Produkt abschließen

**Anknüpfung:** `sidecar/icarus_memory/{harness_broker,harness_protocol,local_module_gateway,local_module_routes,local_module_controller,local_module_runtime}.py`, `integrations/harness/`, vorhandene Einstellungen. Neue Modulregistrierung, Manifestvalidierung und Verwaltungsansicht als begrenztes Teilprojekt entwerfen; bestehende Verträge nicht parallel duplizieren.

- [ ] Manifest und Fähigkeitenvertrag aus Abschnitt 7 als Schema und kleine Entwicklerschnittstelle festlegen. Bestehende ausgewählte Quellenarbeit ist das erste Hostmodul.
- [ ] Lesen, Vorschlag und Ausführen getrennt integrieren; Quellen- und Skillversionen bei Ergebnisverwendung erneut prüfen. Entzug während eines laufenden Jobs testen.
- [ ] Verwaltungsansicht: hinzufügen, Herkunft/Rechte sehen, verbinden, aktivieren, pausieren, aktualisieren und entfernen. Neue Rechte bei Updates erneut freigeben.
- [ ] Ein zweites kleines Modul, etwa lokale Sprachausgabe über bereits vorhandene Mac-Fähigkeiten, durch einen anderen Implementierungsweg nur gegen den Vertrag bauen und prüfen. Kein neuer Cloudanbieter für diesen Nachweis nötig.
- [ ] Fehlerhafte/alte Module, unerlaubte Netzziele, Prompt-Injection, heimliche zusätzliche Werkzeuge und fehlerhafte Ausführungsbestätigungen testen.
- [ ] Entwicklerdokumentation, Beispielmodul, Kompatibilitätstest und Datenexport liefern. Die Oberfläche nutzt dieselben Komponenten wie die Kernbereiche.

**Abnahme:** Ein zusätzliches Modul lässt sich ohne Eingriff in die Gedächtnisspeicherung ergänzen und wieder entziehen. Kein direkter Datenbankzugriff, keine zusätzlichen stillen Rechte. Damit ist die modulare Produktfassung fertig; der Erweiterungskatalog wird anschließend einzeln abgearbeitet.

## 9. Qualitäts- und Betriebsziele

Die folgenden Werte sind vorgeschlagene Freigabeschwellen, keine bereits erzielten Ergebnisse und keine Garantie für unbekannte Daten. Vor einer Messrunde einfrieren; nach einem Fehlschlag nicht nachträglich absenken.

| Prüfung | Ziel und Messweise |
|---|---|
| Kritische Zuordnung | Kein beobachteter Personenwechsel, falscher Aufgabeninhaber, erfundene Frist oder unbelegte automatische Erledigung im freigegebenen Abnahmesatz |
| Abdeckung | Im zurückgehaltenen, gemischten Satz mindestens 100 Quellen; mindestens 95 % der vorher annotierten relevanten Aufgaben/Fristen korrekt als Vorschlag erkannt. Rückfragen, Auslassungen und Fehler getrennt zählen; alles zurückstellen besteht die Prüfung nicht. Die bisherige Sechs-Mail-Probe bleibt Regression, nicht Gesamtabnahme. |
| Zeit und Belege | Alle ausgegebenen konkreten Fristen im Satz durch passende Quelle/Zeitbezug gedeckt; Termin, Abgabe, Vorschlag und historische Frist getrennt. Nachweis über geöffnete Originalstellen. |
| Abruf | Mindestens 30 vorab festgelegte Fragen einschließlich Mehrdeutigkeit, nicht vorhandener Information, veränderter und entzogener Quelle. Mindestens 95 % korrekte unterstützte Antworten; zusätzlich null kritische erfundene Angaben. Rückfrage zählt nur dann richtig, wenn die Referenz wirklich mehrdeutig ist. |
| Skills | Passende Auswahl, bewusst keine Auswahl, konkurrierende/widerrufene Version, Lernvorschlag und Rücknahme bestehen mit Gegenbeispielen. Zeit-/Tokenmehrbedarf separat messen. |
| Oberfläche | Kernwege bei drei Fensterbreiten, Zoom, Tastatur und VoiceOver. Entwürfe bleiben nach Fehler/Wechsel/Neustart erhalten. Vorher/nachher Klicks, Fehler und benötigte Erklärungen an denselben Aufgaben erfassen. |
| Reaktionsfähigkeit | Ziel für bereits geladene lokale Bedienaktionen: p95 unter 200 ms; erster nutzbarer Inhalt typischer lokaler Listen unter 1 s auf dem Test-Mac, auch während Import. Modelllaufzeit getrennt; sofortiger Status, Abbruch und keine falsche Fertigmeldung. |
| Kosten | Vor Start Paketmaximum, danach tatsächliche Nutzungs-/Kostenquittung einschließlich Wiederholungen und Gegenprüfung. Kosten pro 100 tatsächlich bearbeiteter Quellen messen; aus einer Stichprobe nur eine Spannweite für das Archiv ableiten. Budget wird vor Aufrufen reserviert und über parallele Jobs gemeinsam begrenzt. |
| Skalierung | 10.000 und 50.000 künstliche Quellen als frühe Laststufen, danach Größe/Formatverteilung des echten gewählten Bestands. Keine vollständige UI-Liste oder Gesamtkontext im RAM. Index und Queue prüfen, ohne zehntausende künstliche Modellaufrufe zu bezahlen. |
| Sicherung/Update | Wiederherstellung auf getrenntem Bestand erfolgreich; vorher/nachher Quellprüfsummen, Aufgaben/Beziehungen, Schlüsselzugang und Konten konsistent. Fehlender Platz hält das Update verständlich an. |

Referenzannotationen umfassen auch Anlagen, eigene gesendete Mails, weitergeleitete Texte, gleichnamige Personen, automatische wichtige Nachrichten, Newsletter, historische Daten und mehrsprachige Quellen. Gegenprüfung darf nicht bloß dieselbe LLM-Antwort noch einmal bestätigen: Quellenprüfung, deterministische Verträge und unabhängige Fallbewertung ergänzen sie. Persönliche Daten und bezahlte Aufrufe bleiben innerhalb konkreter Freigaben; fehlt eine davon, sind synthetische Vorbereitung und private Freigabe getrennte Gates.

## 10. Modelle, Datenschutz und Wartungsaufwand

- Fähigkeiten auswählen, keine wachsende Sammlung gleichzeitig geladener Modelle. Kleines Routingmodell erst, wenn es gegenüber Regeln oder bestehendem Qwen messbar Qualität/Zeit spart.
- Cloud kann große Ersteinrichtung oder schwierige Einzelfälle unterstützen; ein stärkeres Modell ersetzt keine Beleg- und Identitätsprüfung. Mistral ist eine Option neben bereits angebundenen Anbietern, kein pauschales Qualitäts- oder Datenschutzversprechen.
- Vor Aktivierung konkrete Endpoint-Region, Verarbeitung, Speicherung, Trainingsnutzung, Protokollierung, Unterauftragnehmer und notwendige Vertragsbedingungen prüfen. Europäischer Firmensitz allein entscheidet diese Fragen nicht.
- In der normalen UI „Auf diesem Mac“, „Cloud für freigegebene Arbeit“ und „pausiert“ verständlich anzeigen; die tatsächliche freigegebene Datenmenge und das Kostenlimit sind einsehbar.
- Versionen für Modell, Prompt, Verfahren und Index in privaten Prüfquittungen festhalten; Modellwechsel nicht still durchführen. Suchmodellwechsel kann einen neuen Index benötigen, nie ungeprüft bestehende Vektoren mischen.
- Gezielte Prüfungen pro Änderung, unabhängiges Review kritischer Speicher-/Rechte-/Aktionswege, breite Regression vor Release. Kein erneuter Volltestlauf ohne Änderung oder offene Frage.
- Diagnose ohne private Inhalte; Daten-/Skill-Export und kurze Wiederherstellungsanleitung. Deutsch zuerst, Texte für spätere englische Oberfläche sauber trennbar.

## 11. Reihenfolge, Arbeitsteilung und Endabnahme

P0 zuerst. P1 und P2 bilden den verlässlichen Kern; P3 nutzt ihn. Die drei UI-Referenzansichten aus P4 können früh mit künstlichen Daten vorbereitet werden, die Übertragung erfolgt entlang der stabilen Abläufe. P5 schließt die Alltagsversion ab. P6 baut auf der bereits schmal vorhandenen Modulgrenze auf; spätere Erweiterungen folgen einzeln.

Jedes Paket endet mit überprüfbarer Lieferung: kleiner PR, unabhängige Prüfung wo sinnvoll, passende Tests, Bedienprüfung mit künstlichen Daten und danach die erforderlichen Mac-Schritte. Ein günstigerer Agent kann klar abgegrenzte UI- oder Testarbeit erledigen; Identitäten, Datenentzug, Rechte, Kosten und Releasefreigabe werden fachlich zusammen geprüft. Niemals mehrere Agenten gleichzeitig dieselbe Datenmigration verändern lassen.

Ohne Mac möglich: Code-/Datenverträge, synthetische Regressionen, UX-Entwürfe, Komponenten, Dokumentation und isolierte Modulprüfung. Am Mac erforderlich: echtes Modell unter Last, native Freigaben, Update, Wiederherstellung und die reale Nutzerbedienung. Die Nutzungswoche kann nur der Nutzer im Alltag abschließen; dafür bekommt er konkrete kurze Aufgaben statt eine technische Testliste.

**Endabnahme in Alltagssprache:**

1. Ich öffne Kingfisher und erkenne, was heute wichtig ist und wo die Informationen noch unvollständig sind.
2. Meine Nachrichten landen bei der richtigen Person/dem richtigen Projekt oder eine nachvollziehbare Rückfrage bleibt offen.
3. Ich erkenne eigene Aufgaben, fremde Zusagen, Termine und Fristen; Vorschläge werden nicht als bereits erledigte Arbeit ausgegeben.
4. Ich finde Aussagen samt Original wieder und kann Fehler einmal korrigieren, sodass die Korrektur bei späteren Antworten gilt.
5. Wiederkehrende Arbeitsweisen werden sinnvoll wiederverwendet, ohne falschen Ton oder ungeprüfte Regeln einzuschleusen.
6. Die Oberfläche ist ohne Erklärung bedienbar und der Mac bleibt während der Hintergrundarbeit nutzbar.
7. Daten bleiben über Neustart, Update und Wiederherstellung erhalten; Kosten und Datenweitergabe bleiben unter meiner Kontrolle.
8. Eine neue Erweiterung ergänzt meinen Arbeitsplatz, ohne mein Gedächtnis neu aufzubauen oder unbemerkt zusätzliche Rechte zu bekommen.

Kein künstlicher Prozentwert und kein Enddatum aus der Zahl vorhandener Tests. Nach P0 und der ersten repräsentativen P1-Runde lässt sich der verbleibende Aufwand belastbarer schätzen. Danach wird eine konkrete Lieferprognose pro Paket festgehalten. Neue Ideen wandern in den Erweiterungskatalog; sie öffnen die erledigten Kernpakete nicht wieder, sofern kein echter Fehler oder neuer klarer Auftrag vorliegt.

## 12. Prüfung dieses Plans

- Gedächtnisaufnahme, Speicherung, Abruf, Rückfragen, Pflege und Originale: P0/P1.
- Skillbibliothek, Kategorien, automatischer Abruf, Lernvorschläge und Rechte: P2.
- Mail, Kalender, Aufgaben, Projekte, Gespräch und Morgenbriefing: P3.
- Optik, Lesbarkeit, Darstellung, wenige Schritte und progressive Details: P4.
- Import, Ressourcen, Cloudkosten, Sicherung, Updates und echte Nutzung: P5.
- Harness, Erweiterungsverwaltung, Referenzmodul, zukünftige Dienste: P6.
- Alle fünf besonderen Fehlerklassen aus „Review Focus“ sind einem Paket und einer Abnahme zugeordnet.
- In diesem Schritt wurden ausschließlich Planung und Quellenabgleich vorgenommen; keine Modell-, Import-, Konto- oder App-Einstellungen geändert.

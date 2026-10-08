# Alltagsfunktionen fertigstellen

Grundlage: [freigegebener Alltagsplan](../62-alltagsfunktionen-und-quellenplan.md). Der Nutzer hat am 7. Oktober die aufeinanderfolgende Umsetzung ausdrücklich freigegeben und möchte bis zum Mac-Test keine weiteren Produktentscheidungen beantworten. Bestehenden Entwicklungsbranch verwenden; keine persönlichen Daten/Konten, Cloudaufrufe, Installation, Veröffentlichung oder Kontoberechtigungen ändern.

## Ausführung und Nachweise

1. Aufgaben: SQLite filtert Sicht/Projekt/Suchbegriffe vor einer begrenzten Seite. API liefert Gesamtzahl, nächste Seite und Bestandskennung. Änderungen invalidieren alte Seiten. UI bietet Bestandssuche, Seiten und verständliche Fehler. Abnahme: >200 offene, >500 gemischte Aufgaben, Unicode/literale Suchzeichen, veränderte und fremde Seitentoken, mehrere Store-Verbindungen. Backend-Verhaltenstests und UI-Logiktests, TypeScript/Build.
2. Kalender: sichtbaren Zeitraum mit Zeitzone und begrenzter Dauer anfordern; Jahreswechsel, Sommerzeit, alte Antworten und vorbereitete konkrete Vorkommen berücksichtigen. Backendroute und API werden zentral integriert; Kalenderkomponente und reine Zeitraumlogik getrennt bearbeitet. Abnahme mit künstlichem Anbieter, keine echten Kalenderzugriffe.
3. Tagesentscheidungen: vorhandene Wissensfragen verständlich benennen und in einen normalen Arbeitsweg zusammenführen; fachliche Prüfungen und Quellenbezug behalten. Unbekannte Identitäten bleiben unbekannt. Freigabeentzug und veraltete Bestätigungen unverändert sperren. Kein neues visuelles Layout ohne native Abnahme behaupten.
4. Nachricht → Handlung: vorhandene Originalverläufe und Aufgabenübernahme verbinden; Termine zunächst als klar erkennbare Entwürfe vorbereiten. Google-Schreiben erst mit separaten Rechten, Vorschau, Wiederholschutz und bestätigtem Anbieterzustand; keine Hintergrundausführung an persönlichen Konten. Fehlende sichere Ausführung nicht als fertig darstellen.
5. Produktabschluss: vorhandene/unbelegte/fehlende Fähigkeiten mit Abnahmen erfassen. WhatsApp-API, Weltgeschehen im Morgenbriefing und Sprache als spätere getrennte Lieferungen beschreiben. Weltgeschehen von persönlichen Quellen trennen und Datum/Quelle erhalten; keine neuen Anbieter still aktivieren.
6. Integration: gezielte Regressionen, vollständige UI-Suite, TypeScript/Build, frischer unabhängiger Code-Review. Native Bedienprüfung bleibt bis zum entsperrten und freigegebenen Mac offen. Bestehenden Draft-PR aktualisieren, `[skip ci]`; nicht mergen/installieren.

## Fortschritt und Entscheidungen

- Ausgangspunkt: `b1267ab`. Kalender-Intervallkorrektur bereits enthalten; nicht nochmals implementieren.
- Entscheidung: bestehende Funktionsfreigabe ist die Umsetzungsgrundlage. Keine erneuten Freigabeschleifen für reversible Codeänderungen.
- Entscheidung: Aufgabenlisten verwenden begrenzte Seiten und einen globalen Aufgaben-Änderungsstand; bei Veränderungen wird neu geladen. Das verhindert still übersprungene Datensätze bei einer veränderten Liste und kostet bei paralleler Bearbeitung einen erneuten Abruf.
- Aufgaben: umgesetzt; Backend-Paging und UI-Zustände geprüft.
- Kalender: umgesetzt; Jahresgrenzen, lokale Datumsgrenzen, konkrete Vorkommen und fehlende Mac-Snapshot-Abdeckung geprüft.
- Tagesentscheidungen: normaler Prüfbereich und verständliche Beschriftung umgesetzt; native Lesbarkeit noch offen.
- Nachricht/Handlung: vorhandene quellengeschützte Aufgaben-/Antwortwege bleiben erhalten. Separate manuelle Google-Terminentwürfe und Ausführung umgesetzt. Automatische Mail → Kalender-Übernahme bleibt ohne sicheren Originalfassungsbezug ausdrücklich offen.
- Produktabschluss: Abnahmematrix in Dokument 63 aktualisiert; offizielle WhatsApp-API nach Nutzerwunsch später prüfen.
- Integration/Review: 408 gezielte Backendtests plus fünf separat ausgeführte Launcher-Tests, 354 UI-Tests und Produktionsbuild bestanden. Unabhängiger Review fand drei Fehler; alle korrigiert und unabhängig nachgeprüft. Native Mac-Abnahme, echte Google-Rechte und externe Schreibwirkung bleiben offen.

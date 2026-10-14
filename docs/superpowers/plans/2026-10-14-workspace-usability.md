# Freigegebener Plan: Kingfisher Arbeitsoberfläche

Der Nutzer hat am 14. Oktober 2026 den im Gespräch ausgearbeiteten Plan ausdrücklich zur Umsetzung freigegeben. Ziel: vertrauter Chat, schlankes Projektmanagement, Kontaktbuch mit persönlicher Akte, weniger Klicks und beleggebundene Zuordnung. Bestehenden Gedächtniskern, Originale, IDs, Zugänge und Verlauf erhalten. Kein Fortsetzen des pausierten Großimports. Kein neues Cloudmodell aktivieren.

## Task 1: Gemeinsame Arbeitsflächen und Gespräche

Ruhige geschlossene Flächen; Eisvogel, Farben und Landschaft erkennbar halten. Kompakte Überschriften und Werkzeugleisten. Gesprächsliste samt Suche und Neuerstellung neben geöffnetem Chat, auf schmalen Fenstern aufklappbar. Kontext ausschließlich bei Bedarf über Verwendete Quellen. Composer unten sichtbar. Enter sendet, Shift+Enter Zeilenumbruch; IME und laufendes Diktat schützen. Dateien/Transkripte/Diktat an der Eingabe zugänglich. Lesbare Antworten mit Absätzen, Listen, Hervorhebungen, bestehende Quellen-/Korrektur-/Bestätigungskarten erhalten. Wartezustand und Fehler sichtbar. Entwürfe je Gespräch bei Wechsel und Sendefehler erhalten. Gesprächssuche findet Nachrichteninhalt, paginiert, ohne Modellaufruf und mit sicheren Vorschauen. Tests für Eingabeverhalten, Entwurfswechsel, unbekannte/veränderte Quellen und 900/1280px.

## Task 2: Aufgaben, Projekte und gemeinsame Vorschlagsbestätigung

Meine Aufgaben gruppiert Überfällig/Heute/Demnächst/Ohne Termin. Wartend, Projekte, Zur Prüfung direkt erreichbar; Erledigt als Filter. Kompakte Taskzeilen mit Projekt/Frist/wartender Person, direkte Änderungen, seitliche Details und Rückweg. Projektübersicht, Aufgabenliste, Board Offen/Wartend/Erledigt verwenden dieselben Daten. Projektabschluss schützt offene Aufgaben; historische Ausnahmen bleiben sichtbar. Gemeinsame Prüfliste zeigt Quelle, Aufgaben-/Projekt-/Ablagevorschlag und Begründung. Eine sichtbare Kombination bestätigen oder ändern. Lokales Modell ordnet anhand Inhalt zu möglichen aktiven Projekten zu; Mehrdeutiges bleibt offen. Neue Projekte als ausdrückliche Vorschläge. Analyse und Vorschläge im Hintergrund anhand Quellenstand cachen; Nutzerzuordnungen haben Vorrang. Quellenstand vor Annahme frisch prüfen, Wiederholung idempotent, Sammelergebnis pro Eintrag. Tests: Fristen, Fremdzusagen, Quellenausfall/Entzug, Doppelübernahme, Teilfehler, Projektabschluss.

## Task 3: Gedächtnisprofile und Ablage

Menschen als kompaktes Kontaktbuch mit Bild/Initialen und Kurzangaben. Profil zuerst Wer ist das/Was verbindet uns/Rückmeldungen/Kontaktstand, danach Projekte/Dokumente/Chronik. Unbekannt bleibt unbekannt. Bereiche beibehalten (Arbeit & Projekte, Privat & Familie, Gesundheit, Finanzen & Verträge, Weitere Hinweise), kurze Listen/Filter, Zitate erst beim Öffnen, direkte und ausgewählte Sammelzuordnung. Themen aus Hauptnavigation entfernen, als weitere Ansicht und Filter/Verbindungen erhalten. Dokumente: virtuelle Ordner/Unterordner, Vorschau, Bereich-/Projektfilter; Originale/Quellenhistorie unangetastet. Organisationen: bestätigte reversible Darstellungsgruppen (etwa Amazon) mit rechtlich getrennten Mitgliedern; keine Identitäts-/Vertragspartnerfusion. Zusätzliche Metadaten separat von Wissensaussagen und Originalen. Bestehende Personenprüfung erhalten.

## Task 4: Nachrichten und Kalender

Postfach: Konten links, kompakte paginierte lokale Liste samt Suche mittig, Lesebereich rechts. Gespeicherte Mails bei Providerfehler weiter lesbar; Stand und beschränkter Umfang sichtbar. Bestehende Zusammenfassung, Aufgabe, Projekt und Kalenderaktionen am Nachrichtentext. Kalender: Mini-Monat, Kalenderauswahl/Farben, Tag/Woche/Monat/Liste (Jahr zusätzlich erhalten), echtes Wochenzeitraster. Termin klickbar zu Details/Vorbereitung/bestehenden Schreibaktionen. Gleicher Titel allein nie Dedup-Grund; belegte Spiegelkopien gemeinsam, unklare Kopien unterscheidbar. Quellenrechte behalten.

## Task 5: Einstellungen, Bilder und Ortskarte

Basic/Für Techniker erhalten, klare Status und Aktionen. Eigene Profil-/Organisationsbilder zuerst. Optionaler ausdrücklicher Schalter erlaubt Logos von bestätigten öffentlichen Firmendomains, lokal gecacht. Keine Tracker aus Mail-HTML nachladen. Leaflet/OSM-Karte erst nach Einschalten, bestätigte Positionen aus Koordinaten oder gesetztem Pin neben Ortsliste. Keine automatische Adressrecherche. Öffentliche Netzfetches begrenzt, Privat-/Loopbackziele und unsichere Formate ablehnen; OSM-Attribution/Caching, keine Massenvorabdownloads. Ausgeschaltet keine externen Bilder/Kacheln. Alle Funktionen bleiben ohne Online-Ergänzungen benutzbar.

## Verifikation und Lieferung

Je Paket passende Regressionen, unabhängiges Review und Bedienprüfung mit künstlichen Daten, danach Mac-Fenster. Gesamter UI-Build/Test sowie betroffene Backendprüfungen; finale Backendregression bei substanziellen Backendänderungen. Vor Mac-Update kalte Sicherung plus Wiederherstellungsprüfung; installierte Dateien/maßgebliche Daten und Zugänge nachprüfen; normaler Updateweg. Keine echten Quellen/Schlüssel/privaten Screenshots in GitHub. GitHub-Minuten schonen, keine CI-Reruns. Die bestehende Fassung 1.0.8 bleibt bis geprüfter Veröffentlichung aktiv.

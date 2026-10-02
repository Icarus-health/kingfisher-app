# Terminvorbereitung — 7. September 2026

## Ablauf

„Vorbereiten“ an einem Kalendertermin öffnet eine lesende Zusammenstellung. Das Projekt wird ausdrücklich für diese Ansicht gewählt; der Termintitel begründet keine dauerhafte Beziehung. Die Ansicht verbindet offene und wartende Aufgaben, aktive Entscheidungen mit Warnung bei korrigierten Grundlagen, aktuell verwendbare belegte Wissensaussagen und separat benannte Arbeitsnotizen. Aufgabenlinks führen in die passende Projekt-/Warteansicht.

Jeder Abruf prüft den Termin erneut in der aktuellen Kalenderquelle. Nicht mehr verfügbare Termine liefern keinen alten Kontext. Die Kalenderansicht aktualisiert sich alle 15 Sekunden und entfernt die Vorbereitung bei Quellenentzug. Fehler werden angezeigt; es entstehen keine neuen Fakten, Beziehungen oder Kalendereinträge. Für die Zusammenstellung wird kein Modellaufruf benötigt.

CalendarCollection kopiert gelieferte Terminobjekte nun vor der Kennzeichnung mit Quellen-IDs. Wiederholte Abrufe verändern dadurch nicht die Identität zwischengespeicherter Termine.

## Nachweise

- 34 gezielte Backendtests bestanden: Kalender, Mac-Synchronisation, Kingfisher, Projekt-/Aufgabenfluss, Entscheidungen und neue Vorbereitungsprüfungen. Bestehende Starlette/httpx-Abkündigungswarnung.
- Neue Tests prüfen explizite Eingrenzung trotz passendem Termintitel, korrigierte Aussagen, erschütterte Entscheidungen, erledigte Aufgaben, widerrufene Entscheidungen, fehlende Projekte, Quellenentzug, Quellenausfall und stabile Termin-IDs.
- TypeScript/Vite lokal und im fertigen Docker-Image erfolgreich; Assetmanifest unverändert (14 Dateien, 17 Icons); git diff --check grün.
- Echter Chromium-Ablauf gegen isolierte lokale App und fertiges Docker-Image: Termin öffnen, explizites Projekt wählen, Aufgabe öffnen, Warnung sehen, Kalenderquelle entfernen, Vorbereitung verschwindet. Keine JavaScript-Seitenfehler. Browser plugin nicht verfügbar; reguläres Playwright verwendet.
- Lokale produktive Instanz auf Port 8891 aktualisiert, bestehendes Volume erhalten. Ein synchronisierter Kalendertermin ließ sich im Browser zur Vorbereitung öffnen; keine Testdaten in die Nutzerinstanz geschrieben.
- Screenshot der synthetischen Desktop-Prüfung: outputs/calendar-preparation-desktop.png im Aufgabenordner.

## Quellenansicht ergänzt

Originalquellen lassen sich direkt aufklappen: Belege aktueller Aussagen zuerst, danach ausdrücklich dem Projekt zugeordnetes Rohmaterial. Pro Antwort höchstens 100 Quellen; lange Texte werden sichtbar auf 20.000 Zeichen gekürzt. Ignoriertes Projektmaterial und automatisch erstellte Zusammenfassungen werden nicht als zusätzliche Quellen empfohlen. Gleichlautende Projektnamen im Text erzeugen keine Zuordnung. Namen einer Quelle werden als dort genannte Personen angezeigt, nicht als Termin-Teilnehmer.

Neue Prüfungen: aktuelle Belege mit Herkunft, Wegfall nach Aussagewiderruf, keine Zuordnung nur nach Titel, ignorierte Quellen ausgeschlossen, lange Texte gekennzeichnet. Im echten Browser wurde Skripttext ausschließlich als Text gerendert, die Quellenansicht geöffnet und über Aktualisieren erhalten. Diese Prüfungen liefen auch gegen das fertige Docker-Image.

## Grenzen

Dies ist ein erster bedienbarer Projektkontext, noch keine vollständige Besprechungsakte. Teilnehmer werden nur angezeigt, wenn der Kalender sie liefert. Die Mac-Brücke überträgt jetzt die im ausgewählten Termin vorhandenen Namen und Mailadressen; daraus entstehen keine Registry-Identitäten. Automatische Mail-Relevanzsuche, langfristige Termin-Projekt-Zuordnungen und KI-Verdichtung fehlen. Bereits aufgenommene Quellen werden anhand vorhandener Zuordnung und Belege angeboten. Die neue Ansicht übernimmt bestehende Gestaltungsformen; der vollständige kanonische Bildvergleich und mobile Abnahme bleiben offen. Die gemeinsame Abnahme von Roadmap-Punkt 11 ist inzwischen in ACCEPTANCE-50-PERCENT.md abgeschlossen; die aktuelle Gesamtzählung steht in ROADMAP-STATUS.md.

## Mac-Teilnehmer ergänzt

Der lesende EventKit-Adapter liefert Teilnehmernamen und Mailadressen aus den bereits ausgewählten Kalendern. Die Einstellungen benennen den gelesenen Umfang. Alte Snapshots ohne Teilnehmer bleiben gültig; Eingabegrößen sind begrenzt. Es werden keine Termine verändert und keine weiteren Kalender ausgewählt.

Nachweise: Swift-Build und native Prüfung ungültiger Eingaben erfolgreich; 12 gezielte Backendtests einschließlich Snapshot-Neustart, Kompatibilität, Trennung und Größenbegrenzung bestanden. TypeScript/Vite und Assetmanifest grün. Der isolierte Docker-Browserlauf zeigt synthetische Teilnehmer. Ein echter lesender Mac-Abruf lieferte 35 Termine im 31-Tage-Fenster, davon 10 mit Teilnehmern. Die laufende Jahres-Synchronisation zeigte 520 Termine, davon 115 mit Teilnehmern und keine Quellenfehler. Bei einem bevorstehenden echten Termin wurden die Angaben im Browser abgeglichen. Keine Teilnehmernamen oder Termininhalte in Testausgaben protokolliert.

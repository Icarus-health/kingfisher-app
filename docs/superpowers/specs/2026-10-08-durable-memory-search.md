# Dauerhafte Suche im großen Gedächtnis

Arbeitsentwurf für den nächsten Teil des freigegebenen CoS-Ziels, 8. Oktober 2026. Noch keine implementierte oder abgenommene Funktion. Die Abdeckungskorrektur aus PR 8 ist geliefert; sie ersetzt diesen Baustein nicht.

## Ziel und Grenzen

Alle zugelassenen, eingeordneten Quellenabschnitte sollen für Bedeutungssuche erreichbar bleiben, auch ältere Quellen außerhalb des bisherigen Fensters von 2048 Abschnitten und nach Neustart. Quellen, Einordnung, Bestätigungen, Zeitbezug und Korrektur bleiben in den vorhandenen Strukturen. Der Vektorindex ist vollständig abgeleitet und wiederaufbaubar; er darf weder neue Fakten behaupten noch Originale überschreiben.

Eine Frage darf genau ihren eigenen lokalen Fragevektor anfordern. Sie darf nicht nebenbei Quellen massenhaft einbetten oder einen Index neu aufbauen. Das Anzeigen gespeicherter Antworten braucht weiterhin gar keine Einbettung. Indexaufbau läuft in kleinen Paketen über den vorhandenen Hintergrundprozess mit dessen Netzteil-, Pause-, Freigabe- und Modellrollenprüfung.

## Vorhandenes wiederverwenden

- `WorkingMemoryStore.commit`, `_delete_items`, `resolve`, `source_fingerprint` und seine Revisions-/Transaktionsregeln bleiben Grundlage.
- Vorhandene Scheduler-Verkabelung in `_wire_scheduler`, Rolle `einbettung`, `LocalEmbedder.identity/model_key` und Herkunftsprüfung nutzen. Keine zweite frei laufende Hintergrundschleife.
- Der bestehende callgebundene Statusvertrag trägt weiterhin `partial` oder `unavailable`, solange der aktuelle Modellbestand nicht aufgebaut bzw. die Suche ausgefallen ist.
- Ein dauerhafter Backfill läuft mit stabilem SQL-Schlüssel weiter, kein newest-first-Inventar und keine OFFSET-Schleife, die neue Mails auf Dauer vor alten bevorzugt.

## Speicher und Suchverfahren zuerst messen

Dauerhafte Python-BLOBs mit einem vollständigen Python-Scan je Frage würden Neustarts überstehen, lösen aber die Geschwindigkeit am großen Bestand nicht. Ein eigener LSH- oder ANN-Algorithmus wäre zusätzlicher Wartungs- und Fehlerrisikoaufwand. Bevorzugt wird deshalb zunächst eine isolierte Eignungsmessung einer vorhandenen lokalen SQLite-Vektorerweiterung. [sqlite-vec](https://github.com/asg017/sqlite-vec) bietet eine Python-Anbindung und Vektortabellen; das Projekt weist selbst auf seinen pre-v1-Stand hin. [Python-Anbindung](https://alexgarcia.xyz/sqlite-vec/python.html) und [KNN-Verhalten](https://alexgarcia.xyz/sqlite-vec/features/knn.html) sind die Primärquellen für den Versuch. Das ist eine zu prüfende Option, keine bereits gewählte Produktionsabhängigkeit oder Geschwindigkeitszusage.

Der Versuch verarbeitet nur erzeugte Vektoren und vorab festgelegte Treffer. Er vergleicht Top-k und Distanz gegen eine exakte kleine Referenz, misst Neustart, Speicher, Disk und Fragezeit zuerst bei 20.000, dann 100.000 Vektoren mit 1024 Dimensionen. Datensätze werden gestreamt erzeugt. Kein Modellstart, Cloudaufruf oder privater Inhalt ist nötig. Vorher freie Kapazität prüfen; temporären Verbrauch begrenzen, bei überschrittenem Prozess-/Zeitbudget abbrechen. Keine Änderung der globalen Docker-Ressourcen. Ein fehlender Plattform-Build, nicht begrenzbare Laufzeit oder zu hoher Verbrauch ist ein negativer Befund und kein Anlass für einen heimlichen Fallback auf den vollständigen Python-Scan.

Vor Umsetzung festlegen: geprüfte Paketfassung und Lizenznachweis, benötigte SQLite-Funktionen, Mac-/Linux-arm64-Unterstützung, sichere Ladegrenze und Wiederherstellbarkeit. Falls virtuelle Tabellen die bestehende Datenbankmigration oder Sicherungsprüfung ohne Erweiterung beeinträchtigen, den abgeleiteten Suchbestand in eine getrennte, entbehrliche Cache-Datei legen. Die Originaldatenbank muss ohne diese Erweiterung lesbar bleiben. Indexpfad und Zuordnung sind dann pro EpisodeStore getrennt; keine gemeinsame globale Cache-Datei über Test-/Produktivbestände.

## Inkrementeller Aufbau

Ein Eintrag bindet Abschnittsschlüssel, Quellenfingerabdruck, exakten lokalen Modellnamen/Digest, Vektordimension und Format. Modellstände werden nie vermischt. Neue oder geänderte Abschnitte sind ausstehend, vorhandene passende Vektoren werden nach Neustart verwendet. Ein erfolgreicher Paketabschluss speichert Vektoren und Fortschritt atomar. Fehler lassen erledigte Pakete intakt und bleiben wiederholbar; ein Netzteil-/Einstellungs-/Modellwechsel stoppt die nächste Arbeit.

Der laufende Prozess verarbeitet höchstens ein kleines Paket pro Tick. Timeout und Abbruch gelten auch beim Einbetten; keine EpisodeStore-Sperre über einen Modellaufruf halten. Backfill und neue Quellen müssen beide Fortschritt erzielen. Speichern nur Vektoren und Verweise, keine weitere Klartextkopie.

## Entzug und Suche

Korrektur, Ausschluss oder Entzug verhindert sofort die Ausgabe alter Abschnitte. Ein noch nicht bereinigter Vektor ist kein gültiger Beleg: vor Rückgabe und erneut vor Anzeige gilt `resolve`. Quellenänderungen während Frage/Indexaufbau dürfen keinen alten Eintrag als vollständig aktuellen Suchbestand zertifizieren. Veraltete Vektoren werden nachgelagert bereinigt; neu freigegebene Quellen machen den Bestand bis zur Nacharbeit wieder teilweise.

Begrenzte Trefferzahl, vollständige Indexabdeckung und semantische Antwortbarkeit sind verschiedene Größen. Auch ein vollständig aufgebauter Index garantiert weder perfekte Relevanz noch richtige Modellauswahl. Wenn Zeit-/Kandidatenbudget oder verworfene veraltete Treffer die Auswahl beschränken, wird dies gemeldet. Die bisherige Schwelle bleibt zunächst unverändert; Trefferqualität wird an den eingefrorenen Original- und unabhängigen Kontrollfragen bewertet.

## Fortschritt und Abnahme

Die API und Gedächtnisoberfläche zeigen Bedeutungssuche getrennt von Mailaufnahme und Einordnung: aktueller Modellbestand, insgesamt geeignete Abschnitte, indexiert, ausstehend, Fehler, letzter Fortschritt und deaktiviert/teilweise/verfügbar. „Aufgenommen“ oder „eingeordnet“ bedeutet nicht automatisch „semantisch indexiert“.

Abnahmefälle:

1. In kleinen Paketen aufbauen, Prozess neu starten, fertige Quellenvektoren ohne erneute Einbettung nutzen; Frage braucht nur ihren Fragevektor, Wiederöffnung keinen.
2. Eine relevante alte Quelle jenseits von 2048 neueren Abschnitten wird indexiert und gefunden. Neue Mails verhindern den Backfill nicht.
3. Entzug, Korrektur, ausgeblendete Quelle und Quellenänderung während eines Pakets schließen alte Treffer auch vor Bereinigung aus.
4. Modell-Digest-/Dimensions-/Formatwechsel isoliert den Bestand; kein stilles Vermischen und kein falscher Komplettstatus.
5. Timeout, voller Datenträger, Neustart und beschädigter abgeleiteter Bestand verlieren weder Originale noch fertige Einordnung; Fortschritt bleibt ehrlich.
6. Große synthetische Messung hält das festgelegte Ressourcenbudget ein. Exakter Referenzvergleich, unabhängige Ablenker und unbekannte Fragen bleiben Teil der Prüfung.
7. Bestehende Datensicherung, Migration, gespeicherte Antworten und Quellenentzug bestehen weiter; erst danach datenerhaltende Mac-Lieferung.

Der erste Umsetzungsschritt ist die begrenzte technische Eignungsmessung. Erst ihr Ergebnis bestimmt das konkrete Speichermodul und die dazugehörige Migration; keine neue Produktabhängigkeit wird allein aufgrund der Dokumentation aktiviert.

# Datierte Gesundheitsangaben im bestehenden Gedächtnis

Der freigegebene CoS-Auftrag umfasst Gesundheit, verständliche Nutzung und erhaltene Originale. Diese Erweiterung setzt eigene datierte Messangaben als Quellen und lesbaren Verlauf um. Keine zweite Datenbank, kein Modell, keine medizinische Deutung, automatische Personenverknüpfung oder Cloudverarbeitung. Der Nutzer hat Routineentscheidungen und Umsetzung ausdrücklich delegiert; es wird keine weitere Freigabeschleife für dieses lokale Datenmodell eingeführt.

## Ablauf und Grenzen

Heute/Entwicklung/Gesundheitsquellen → `/wellbeing` → Messgröße, wörtlicher Zahlenwert, Einheit und Zeitpunkt eingeben → Vorschau und ausdrücklicher Personenbezug „Meine eigene Angabe“ → als Quelle speichern. Mehrere Einträge mit gleichem Zeitpunkt bleiben unterscheidbar. Ein verlorener HTTP-Erfolg wird mit derselben Einmal-Kennung wiederholt; eine andere Eingabe unter derselben Kennung blockiert. Bestätigte Speicherung setzt das Formular zurück.

Aktuelle Angaben werden nach tatsächlichem Messzeitpunkt angezeigt, inklusive ursprünglichem Zeitoffset und Quellenöffnung. Korrektur verlangt aktuellen Belegfingerabdruck und ausdrückliche Speicherung einer neuen Version. Überholte Originale bleiben erhalten und alte abgeleitete Aussagen werden durch die bestehenden Quellenregeln invalidiert. Wiederholung derselben Korrektur erhält die bereits gespeicherte neue Fassung. Ein konkurrierender neuer Stand wird nicht überschrieben. Unveränderte Korrekturen erzeugen keine neue Fassung und entwerten keine Belege. Ausschluss verwendet den vorhandenen Quellenentzug; Verlauf ist ausdrücklich historisch, kein aktives Gesundheitswissen; Status beim Abruf mit sichtbarer Abrufzeit und „Neu prüfen“.

In dieser Lieferung: eigene manuell eingegebene Werte und deren Verlauf. Datei-/HealthKit-Import, Angaben zu anderen Menschen, Diagnose, Normbereiche, Umrechnung und Medikamentenempfehlungen bleiben weitere Arbeit. Der vollständige CoS-Auftrag wird dadurch nicht eingeschränkt.

## Daten und Schnittstellen

- Original: EpisodeKind.DOCUMENT, SourceType.USER_STATED, kanonischer JSON-Text mit Schema, `subject=self`, Messgröße, originalem Dezimaltext, wörtlicher Einheit, bewusst gesetztem zeitzonenbezogenem Zeitpunkt und optionaler Notiz. Originaltext bleibt unveränderlich.
- Bestehender source_key `health-observation:<UUID>` und source_heads schützen Wiederholung/Fassungen. Tags kennzeichnen Format, Personenbezug und Änderungskennung. Kein neues DB-Schema.
- POST `/api/v1/health/observations`: Pflicht-Einmalkennung, ausdrücklicher Personenbezug, Felder; 201 neu / 200 Wiederholung, 409 Kennungskonflikt/entzogener Vorgang.
- GET `/api/v1/health/observations`: begrenzte zeitlich sortierte aktuelle Quellen, höchstens 50 ausgegeben/100 validiert; Fortsetzung und begrenzter Suchraum sichtbar. Cursor besteht aus exakten UTC-Mikrosekunden und rowid (keine SQLite-Julian-Float-Rundung), keine Verwechslung mit Erfassung. Je Quelle Originalsnapshot validieren. Kein Vollbestandszähler erfunden.
- PATCH `/api/v1/health/observations/{id}`: Originalfingerabdruck und Änderungskennung, sonst gleicher Eingabevertrag. Bestehende Claim-Invalidierung und Quellenumschaltung vor Ausgabe. Die Erfassung neuer Originale und Head-Wechsel werden im bestehenden SQLite-Transaktionsweg serialisiert.
- GET `/api/v1/health/observations/{id}/history`: begrenzte Originalfassungen desselben Gesundheits-Schlüssels; aktuell/überholt/ausgeschlossen getrennt. Volltextprüfung vor Projektion; keine Zugehörigkeit aus Namen erfinden.
- Die explizite Gesundheitsablage prüft zuerst, ob die Kategorie `health` verfügbar ist (bei voller eigener Taxonomie kann sie fehlen); ansonsten 409 ohne Teilaufnahme. Sie nutzt Categories.correct für neue Fassungen. Die Ansicht prüft Originalsnapshots mit Bytegrenze und aktuellem Head, unabhängig von Verdichtungsbuchhaltung. Bestehende Mail-/Dateieinordnung, Modelle und Pause bleiben unverändert.

## Beweiskriterien

Reale SQLite-Stores/HTTP: Datum ungleich Aufnahme, Offset erhalten, Dezimaltext/Einheit unverändert, zwei gleiche Zeitpunkte, verlorene Antwort/Neustart, Kennungsreuse mit geändertem Payload, Korrektur/alte Originale/Claim-Invalidierung, Gegenänderung/Entzug, falscher Personenbezug, fehlender Offset, malformed source, ältere Messzeit trotz neuem Import, Cursor/Folge-/Leerseite und Pause ohne Provideraufruf.

Frontend: Formular-/Zeitzonen-/Einmalkennungslogik, stale response nach Ansichtwechsel, bewusste Vorschau, Originalöffnung, Korrektur mit erhaltenen Eingaben bei Fehler, Keyboard-Fokus, schmaler Verlauf und Rückweg. Tests/Build und unabhängige Reviews belegen Code; echte native Bedienung bleibt wegen ausdrücklicher Verschiebung offen und wird nicht durch eine Ausweichoberfläche behauptet.

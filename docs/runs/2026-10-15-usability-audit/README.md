# Alltagsabläufe und Bedienbarkeit · 15. Oktober 2026

Nachprüfung der freigegebenen Gestaltungsvariante 3. Getesteter Produktstand: `9d17f45`, aufbauend auf `6ebdecd`. Getrennte lokale Vorschau mit ausschließlich künstlichen Quellen, Kontakten und Terminen. Dialogantwort und Mailauswertung wurden durch deterministische Testprovider geliefert; daraus folgt keine Aussage über die Qualität eines echten LLM.

Als Maßstab dienten Apples [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines), insbesondere [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [Typography](https://developer.apple.com/design/human-interface-guidelines/typography) und [Feedback](https://developer.apple.com/design/human-interface-guidelines/feedback). Dies ist keine Apple- oder WCAG-Zertifizierung.

## Sichtbar durchgespielte Abläufe

1. **Heute und Briefing:** Prioritäten, Terminvorbereitung, unvollständiger Quellenstand und pausierte Verarbeitung; Dialog öffnen/schließen, Tastaturumlauf, Escape und Rückfokus.
2. **Gespräche:** neues Gespräch, Enter/Zeilenumbruch, formatierte Antwort, fehlender Beleg sichtbar, Rückmeldung, Verlaufssuche und Entwurfserhalt beim Wechsel. SRT aufnehmen und unveränderte Zeitmarken im Original wiederfinden.
3. **Aufgaben und Projekte:** Aufgabe mit Projekt und Frist erstellen, wartende Person setzen/zurücknehmen, erledigen/erneut öffnen, Board und Liste. Projektabschluss mit offener Aufgabe blockieren; nach Erledigung abschließen und wieder aktivieren. Zwei Vorschläge gemeinsam bestätigen, Ergebnisse pro Eintrag. Projekt- und Aufgabenentwurf über die Prüfliste erhalten. Entscheidung speichern und ausdrücklich zurücknehmen.
4. **Gedächtnis:** Textsuche zum neuen Transkript, Original öffnen, Projektzuordnung und bestätigte Bereichskorrektur, Personenprofil mit Aufgabe und Quellenrückweg, Suchfilter beim Rückweg erhalten. Virtuellen Ordner anlegen, Dokumentzuordnung speichern/rückgängig. Anzeigegruppe aus drei Amazon-Einzelakten bestätigen/rückgängig; rechtliche Absender bleiben getrennt. Ungültige Koordinate sperren, gültigen Pin ausdrücklich speichern, Onlinekarte bleibt aus. Aussagen-Leerzustand, Verarbeitungsstand und Quelldatum/Erfassungsdatum getrennt lesen.
5. **Nachrichten und Kalender:** gespeicherte Mail ohne aktuelle Providerverbindung suchen/lesen. Historische Mail von 2020 ergibt nach künstlicher Auswertung eine Aktualitätsprüfung ohne heutige Frist; erst nach Bestätigung wird eine Aufgabe samt Projekt angelegt. Tag/Woche/Monat/Liste/Jahr, Kalender aus-/einblenden, Termindetail und Vorbereitung. Ohne Schreibkonto bleibt die Vorschau zur Terminanlage gesperrt und erklärt den nötigen Zugang.
6. **Weitere Bereiche und Einstellungen:** Health-Messwert aufnehmen, berichtigen, beide Fassungen prüfen und aktuelle Quelle ausschließen; Ziel speichern, nächsten Schritt übernehmen, Gewohnheit abhaken/rückgängig. Öffentliche IANA-Beispielseite registrieren, ausdrücklich abrufen, gespeicherten Quellenbericht lesen und Abrufe deaktivieren. Alle sechs Einstellungsgruppen lesen, lokalen Grußnamen speichern, Rückmeldung wiederfinden. Verschlüsselte Testsicherung herunterladen; Kingfisher meldet die vorherige Prüfung.

## Gefundene und behobene Probleme

| Befund | Korrektur und Nachprüfung |
|---|---|
| Briefing ohne Escape, verlässlichen Fokus und abgeschirmten Hintergrund | Fokus beim Öffnen, Tab-Umlauf, Escape, Rückfokus, inaktiver Hauptinhalt und geschlossener Dialog. Im echten Browser nachgeprüft. |
| Doppelte Warnung, zu kleine Hinweise und schlecht lesbares Autorenlabel | Warnungen zusammengeführt, Quellenart lesbar benannt, Briefing-Typografie vereinheitlicht, Chatlabel dunkler/größer. |
| Projektstatus wird vor der Aktualisierung wieder bedienbar; alte Abschlusswarnung bleibt | Aktualisierung wird abgewartet, parallele Statuswechsel abgewehrt, Warnung bei neuem Aufgabenstand gelöscht. Blockierter und danach erlaubter Abschluss erneut durchgespielt. |
| Hauptaktion öffnet vorhandenen Aufgabenentwurf aus der Prüfliste nicht | Bestehenden Entwurf wieder anzeigen, ohne ihn zu überschreiben. Verhaltenstest und Browserprobe. |
| Globale Prüfliste zeigt Filter, die ihre Vorschläge nicht filtern | Unpassende globale Projekt-/Aufgabensuche ausgeblendet. Projektsteuerung bleibt versteckt montiert, damit ihr Entwurf und ihre sichere Wiederholung erhalten bleiben. |
| Auswahlkästchen und Vorschlagskarten zu groß/unruhig | 18-px-Kästchen mit gemeinsam anklickbarer Beschriftung, kompaktere Belege und einheitliche Werkzeugleiste. |
| Öffentliche Quelle meldet nur allgemeinen Fehler; Wiederholen lädt nur Liste | Handlungsbezogene Meldungen, erhaltene Eingabe, Hinweis auf Adresse/Bezeichnung/Themen/Duplikat entsprechend dem Backendvertrag. Keine falsche Speicherwiederholung. |
| Ergänzende Formulare wirken uneinheitlich | Gemeinsame Felder und kompakte Anordnung; Checkbox-/Radio-/Datei-/Rangefelder ausdrücklich ausgenommen. |
| Entscheidungsgraph hat unbenannte Bereichsbeschriftung | Ergänzende Gedächtnisbereiche für die Beschriftung berücksichtigt. |

Das unabhängige Review fand zusätzlich Entwurfsverlust durch Aushängen der Projektsteuerung, unpassende Zuordnung von HTTP-Fehlern und eine überschreibende Checkbox-Regel. Alle drei korrigiert; Nachreview ohne wichtige offene Befunde.

## Technische Prüfung

| Prüfung | Ergebnis |
|---|---:|
| Gesamte Backend-Suite | 6.604 bestanden, 1 übersprungen; zusätzlich 26 Subtests |
| Messlatte und Mac-Logik | 330 bestanden, 1 übersprungen |
| Diagnose- und CoS-Skripte | 241 unterschiedliche Tests bestanden |
| UI, einschließlich fünf neuer Verhaltensregressionen | 715/715 bestanden |
| TypeScript/Produktionsbuild, Assetvertrag, Diffprüfung | bestanden |

Die Backend-Suite bestand zunächst mit 6.501 Tests; 103 Fälle waren durch lokale Server- und Compiler-Sandboxrechte blockiert. Nur diese 103 wurden mit passender Testumgebung wiederholt und bestanden. Ein Mac-Swift-Test wurde mit beschreibbarem Compiler-Cache wiederholt und bestand. Acht Diagnosetests benötigen einen sauberen Git-Stand; die betroffene Datei bestand nach dem Codecommit mit 11/11. Die Zahlen sind entsprechend zusammengeführte Ergebnisse, kein einzelner Komplettlauf. Keine Backendänderungen.

Frische Bedienprüfung bei 1.280×900, 900×900, 390×844 sowie 1.280×360. Schmale Dokumentansicht mit Rückweg, Sucherhalt und Rückfokus; Chat ohne horizontale Seite und mit erreichbarer Eingabe; Mailrückweg mit Sucherhalt; kurze Mailliste mit weiterhin scrollbar verfügbarem Inhalt. Briefing bei 900 px ohne horizontalen Überlauf. Browserkonsole zum Abschluss ohne erfasste Fehler. Temporäre Fenstergröße zurückgesetzt.

## Grenzen und nächste echte Abnahme

Echte Kontoanmeldungen, Mailversand, echte Kalenderänderungen, Modelltrefferrate und Importleistung wurden nicht live geprüft. Ebenso offen: native Mikrofon-/Kalenderberechtigungen, VoiceOver, 200%-Textvergrößerung, vollständige WCAG-Abnahme und Wiederherstellung auf einem separaten Bestand. Die Browserprobe ersetzt keinen Test der installierten Mac-App mit echten Konten.

Bestehende kleinere Punkte: Markdownzeichen in gekürzten Verlaufsauszügen, technische Zeitangaben bei Health und verschachtelte Ablagewerkzeuge. Der vorhandene Buildhinweis zum großen JavaScript-Bundle (~1,21 MB vor Komprimierung) bleibt offen.

Kein Merge, keine persönliche Mac-Installation, keine Cloud-/Modellaktivierung und keine Fortsetzung des pausierten Großimports durch diese Prüfung. PR #65 bleibt ein Entwurf. Keine CI-Wiederholung angefordert.

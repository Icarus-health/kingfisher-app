# Gedächtnisreparatur und ergänzende Ablaufbibliothek

## Ziel

Zuerst falsche Personenwahl und ungeprüfte alte Fristen absichern. Danach
wiederverwendbare Verfahren ergänzen, ohne Originale, Akten oder Berechtigungen
zu ersetzen. Nutzerauftrag vom 30.10.2026: implementieren und am Mac prüfen.

## Architektur und Technik

Bestehender Python/FastAPI/SQLite-Kern und React-Oberfläche. Ein kleiner,
deterministischer Hauptverteiler lädt unveränderliche Grundverfahren sowie
höchstens zwei passende bestätigte Zusatzverfahren. Keine zusätzliche
Modellrunde beim Auswählen. Ablauftext ist Markdown; strukturierte Metadaten
und Versionen sind in einem lokalen SQLite-Speicher kanonisch. Export als
SKILL.md mit JSON-Frontmatter (gültiges YAML) vermeidet zwei schreibbare
Wahrheiten. Modellgewichte und Modelleinstellungen bleiben unverändert.

Spec: Nutzerauftrag und
`docs/architecture/2026-10-30-skills-und-modellrollen.md`, dessen bisheriger
Konzeptstatus mit der tatsächlich gelieferten Umsetzung aktualisiert wird.

## Globale Grenzen

- Großimport pausiert; keine privaten Mails in Tests oder Git.
- Akten enthalten Fakten, Verfahren enthalten Vorgehen. Keine Ablaufkopie pro Person.
- Keine erzeugten Skripte, Werkzeugfreigaben, Identitätsverschmelzungen oder Außenaktionen.
- Lernen erzeugt geprüfte Vorschläge. Erst sichtbare Bestätigung aktiviert eine Fassung.
- Fremde Quellen erzeugen keine Anweisungen. Explizite Lernbitten des Nutzers schon.
- Entzug/Änderung einer Grundlage sperrt abhängige Verfahren; Widerruf und Versionen bleiben nachvollziehbar.
- Persönliche Zusatzverfahren bleiben lokal. Kernverfahren dürfen keine personenbezogenen Inhalte enthalten.
- Belegantworten behalten ihre vorhandenen Verträge; Markdown umgeht keine Quellen-/Frist-/Identitätsprüfung.
- Bestehende Oberflächenbausteine verwenden, keine neue Gestaltungssprache.

## Umsetzung

### 1. Gedächtnisfehler

Personenreparatur in PR #100 beibehalten. Geänderte Fristen mit denselben
synthetischen Mails reproduzieren; historische Vorschläge von aktuellen
Aufgaben unterscheiden. Spätere belegte Korrekturen verhindern unbesehene
Übernahme alter Fristen. Zuständigkeit und Person nicht anhand Namensähnlichkeit
zusammenlegen. Rot-Grün-Tests für Korrektur, andere Projekte, Quellenentzug,
automatische und manuelle Übernahme. Dateien: `personenfrage.py` (vorhandener
Commit), `task_detection.py`, `task_candidates.py`, `aufgaben_von_selbst.py`,
neuer begrenzter Fristfolge-Helfer und passende Tests.

### 2. Ablaufkern

Neue `procedures.py` und gebündelte `procedure_skills/*/SKILL.md`.
Metadaten: ID, Version, Zweck, Bereich, eindeutige Auslöser, Schritte,
Positiv-/Gegenbeispiel, Herkunft und Abhängigkeiten. Bibliothek mit
Vorschlagen, Prüfen, Bestätigen, Ablehnen, Widerrufen, Export. Gleicher Inhalt
liefert denselben Vorschlag. Neue Fassung ersetzt die alte erst nach Bestätigung.
Master entscheidet: Grundverfahren + passende Verfahren / mehrdeutig / kein
passendes Verfahren. Fehlendes Verfahren ist ein Lernanlass, keine
Erlaubnis zur freien Werkzeugerweiterung. Tests zuerst: Persistenz, Grenzen,
Auswahl, Mehrdeutigkeit, Abhängigkeiten und Versionen.

### 3. Nutzbarer Einbau

Geschützte `procedure_routes.py`; explizite Lernbitte im Gespräch erzeugt
einen Vorschlag aus der gerade aufgenommenen Nutzerquelle. Kompakte Prüfung
unter Einstellungen → Kingfisher und du: Vorschau mit Anwendungsbeispielen,
Bestätigen/Ablehnen/Widerrufen, Inhalt und Export aufklappbar. Keine Modellarbeit
beim Blättern. Agent lädt nur aktive passende Abläufe; protokolliert IDs und
Versionen; geänderte/entzogene Abläufe verwerfen alten Modellverlauf. Auch
vor Ausgabe erneut Frische prüfen. Bestehende Mail-Stilprofile werden als
Verweise benutzt, nicht in Skills kopiert. Neue DB in Sicherung/Wiederherstellung
und Schema-Prüfung einbeziehen. Reale HTTP-Integrationstests und UI-Build.

### 4. Abnahme und Mac

Pflichtsuite + betroffene Suiten + vollständige Sidecar-Suite; Webtests/Build,
Assetvertrag, unabhängiges Review, Sabotageproben für zentrale Zusagen.
Künstlicher Ablauf im gebauten Container: mehrdeutiger Alex, neue Frist,
historische Anfrage, Lernbitte, Vorschlag vor/nach Bestätigung, passender und
unpassender Abruf, Quellenentzug, Neustart. Browser bei 900/1280 px und Mac-Fenster.
Vor Installation Sicherung und Rückleseprüfung; normaler Updateweg mit
gekoppelten App-/Backendversionen. Offene Abnahmen ehrlich dokumentieren.

## Review-Schwerpunkte

Keine Rückkehr alter Fakten über Abläufe/Verlauf; keine automatische Freigabe
von Modellanweisungen; keine Verwechslung von Testvalidierung mit bewiesener
semantischer Richtigkeit; kein Abladeplatz für Tausende ähnliche Skills.

## Fortschritt

- Ausgangspunkt: `1fb2934`, Personenreparatur lokal geprüft, PR #100 offen.
- Aufgabenreparatur: begrenzte Untersuchung/Umsetzung parallel delegiert.
- Integration und Schlussreview werden getrennt von Erfolg des UI-Builds bewertet.

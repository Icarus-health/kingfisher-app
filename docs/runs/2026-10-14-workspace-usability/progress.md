# Fortschritt – freigegebener Arbeitsoberflächenplan

Basis: 6ff97c19c22abfaad27431c59c0bb9c69bf798d4 (1.0.8).
Plan: docs/superpowers/plans/2026-10-14-workspace-usability.md.
Isolierter vorhandener temporärer Checkout, eigener Featurebranch; persönlicher Datenbestand wird nicht zur Entwicklung verwendet.

- Baseline: 609/609 UI-Tests bestanden (14. Oktober).
- Preflight: Task 1/2 teilen App/API; Änderungen daran werden seriell integriert. Neue Ablagemetadaten sind keine Fakten. Task 2/4 nutzen dieselben Quellen- und Projekt-IDs. Bestehende Beleg-/Entzugsprüfungen bleiben aktiv.
- Task 1: umgesetzt; gezielte 50 UI-/37 Backendprüfungen bestanden. Gesprächsuche und sichere Vorschau integriert. Gemeinsame visuelle Abnahme und unabhängiges Review noch offen.
- Task 2: Aufgaben nach Frist gruppiert, direkte Projekt-/Prüfzugänge, Detailpanel und Board mit denselben paginierten Aufgaben umgesetzt. Projektvorschläge nutzen bestätigte Quellzuordnung, vorhandene Absenderregeln oder vorbereitete lokale Vorschläge. Ein Klick übernimmt die sichtbare Aufgaben-/Projektkombination; Quellenprüfung und Wiederholschutz bleiben aktiv. Integrationstest/Review laufen.
- Task 3: separater Implementierungsagent arbeitet an Kontaktbuch, Profilen, Bereichen, Ordnern und Organisationsgruppen.
- Task 4: offen.
- Task 5: Metadatenbasis mit Revision, Verlauf und Rückgängig; eigene Bilder und bestätigte Positionen in Umsetzung. Online-Funktionen bleiben ausgeschaltet.
- Prüfbefund: Projektabschluss mit offenen Aufgaben wird abgewiesen. Lesende Sichten erlauben abgeschlossene Projekte weiterhin; der bestehende historische Ausnahmefall bleibt sichtbar. Ein Testbestand simuliert diesen Zustand ausdrücklich über den Store, nicht über die inzwischen geschützte API.
- Prüfbefund: Wiederholbare neue Projektübernahme brauchte eine reentrante Storesperre. Die zuerst beobachtete Blockade im künstlichen Test wurde korrigiert; der eigene Testprozess gezielt beendet und neu gestartet.
- Ruling: Keine Projekt-Modellprüfung ohne vorhandene Vergleichsprojekte; die manuelle, ausdrückliche Anlage bleibt möglich. Dies spart Modellarbeit ohne brauchbaren Vergleichsrahmen; automatische Erstprojektvorschläge benötigen dann mindestens ein vorhandenes Projekt.
- Ruling: Fristgruppen zeigen die aktuell geladene Aufgaben-Seite mit Gesamtzahl und Seitenwechsel. Board-Spalten zeigen ihren Umfang ausdrücklich; keine scheinbare Vollständigkeit großer Bestände.
- Prüfnachweise liegen lokal unter /private/tmp/kingfisher-usability-*.log. Keine persönlichen Quellen oder Zugänge werden veröffentlicht.

# Kontrollierte Verbesserung von Kingfisher

13. September 2026. Architekturentscheidung für den weiteren Ausbau;
**noch kein automatisch laufender Selbstverbesserungsdienst**.

## Präzisierung: zuerst das lernende Arbeitsprofil

Mit „Selbstverbesserung“ meint der Nutzer zunächst, dass Kingfisher seine
bevorzugte Arbeitsweise und Informationstiefe kennenlernt. Dafür wird das
bestehende Nutzer-/Stilgedächtnis weiterentwickelt, kein zweites Profil angelegt.
Bereich, Herkunft, Zeit, Widersprüche und Rücknahme stehen in
[Memory-first, Abschnitt 7](MEMORY-FIRST-ROADMAP.md#7-nutzerprofil-vorhandenes-gedächtnis-weiterentwickeln).
Der nachfolgende Ablauf für Programm-/Promptverbesserungen ist eine getrennte,
nachgeordnete Fähigkeit und kein bereits laufender Dienst.

Kingfisher soll aus ausdrücklich korrigierten Zuordnungen, Stilwünschen und
fehlgeschlagenen Aufgaben lernen. Das vorhandene korrigierbare Gedächtnis bleibt
die Quelle persönlicher Informationen; Modellgewichte sind kein Personenarchiv.
Unbestätigte Modellinterpretationen bleiben von bestätigten Aussagen getrennt.

## Verbesserungsablauf

1. Fehler erfassen: betroffener Ablauf, belegte Nutzerkorrektur, Modell-/Prompt-
   und App-Version, Laufzeit. Private Originaldaten bleiben im lokalen Bestand.
2. Einen synthetischen Regressionstest ableiten. Ein Testbeispiel allein darf
   keinen allgemeinen Stil, Persönlichkeitszug oder eine Regel festschreiben.
3. Einen begrenzten Vorschlag für Prompt, Retrieval oder Modellrouting erstellen.
   Umfang, erwarteter Nutzen, Risiken, Kosten und Rückweg werden sichtbar.
4. Vorschlag in einer isolierten Kopie gegen eingefrorene Fälle und neue
   Gegenbeispiele prüfen: Identitätsverwechslung, zeitliche Widersprüche,
   Quellenentzug, Prompt-Injection, fehlende Information, Latenz und Kosten.
5. Nur nach bestandenen Prüfungen und ausdrücklicher Freigabe aktivieren;
   vorherige Version behalten und bei Regression zurücknehmen.

Kein automatisches Erweitern von Werkzeugrechten, keine eigenmächtige Änderung
von Sicherheitsregeln, keine automatischen Modell-Downloads oder Weitergabe von
Nutzerdaten. Codeänderungen bleiben reviewbare Branches/PRs mit Tests; ihre
Ausführung gehört nicht zu einem unbegrenzten Agentenwerkzeug. Persönliche
Lernregeln, Profile, Schlüssel und Gesprächsdaten werden nicht ins öffentliche
Repository exportiert. Jeder neue Nutzer startet mit eigenem leeren Bestand.

Der [Kalenderversuch](../evaluations/model-selection/calendar-recall-experiment/README.md)
ist das konkrete Gegenbeispiel: höhere Trefferzahl, aber schlechtere Trennung
von Quelleninhalt und Anweisung. Deshalb bleibt dieser Vorschlag deaktiviert.

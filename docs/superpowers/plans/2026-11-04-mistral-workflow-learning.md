# Mistral für geprüfte Ablaufvorschläge

Teilpaket von P2/P5 des freigegebenen Produktplans. Stand: 04.11.2026.
Der Nutzer möchte lokale Modelloptimierung nicht zur Voraussetzung der Alltagsversion machen.

## Vertrag

- Lokale Aufnahme, Speicherung, Auswahl und Aktivierung von Skills bleiben unverändert.
- Eigene ausdrücklich markierte Arbeitskorrekturen können zusätzlich als genau bezeichnetes Paket mit Mistral geprüft werden. Vorschau und Status arbeiten ohne Modellaufruf.
- Die Vorschau zeigt alle übertragenen Nutzeraufträge, Korrekturen und relevanten Katalogmetadaten. Keine vollständigen Antworten, Mails, Anhänge oder ungeprüft ergänzte Quellen.
- Freigabe gilt einmalig für diese unveränderte Vorschau, Small 4 am regionalen EU/EFTA-Endpunkt und höchstens zwei abgerechnete Aufrufe. Keine automatische Cloudweitergabe bei lokalem Fehler.
- Import und Lernen verwenden dieselbe persistente kumulative Kostenobergrenze und dieselbe Budgetinstanz. Ein Budget allein ist keine Datenfreigabe.
- Quell-, Korrektur-, Katalog-, Schlüssel-, Budget- und Wiederherstellungsänderungen entwerten die Freigabe. Abbrechen verhindert weitere Aufrufe und Ergebnisübernahme, nicht schon entstandene Kosten.
- Wiederholtes Klicken oder Neustart wiederholt keinen Versand. Rechnungsdaten werden auch bei verworfenem Ergebnis verbucht. Ungewisse Kosten stoppen weitere Arbeit.
- Identische semantische Prüfung wie lokal; konkrete Fakten werden nicht zu Skills. Neue Fassungen bleiben inaktiv, Aktivierung/Entzug verwenden die bestehende Bibliothek.

## Schritte

1. [x] Bestehende Korrekturvorbereitung und Ergebnisprüfung ohne Änderung ihrer Regeln für beide Ausführungswege verfügbar machen.
2. [x] Vorschau, einmaligen Start, Status und Abbruch mit bestehendem Mistral-Transport/Budget ergänzen; Fehler und Neustart prüfen.
3. [x] Kompakte, ausdrücklich optionale Bedienung in „Meine Abläufe“ ergänzen, samt Herkunft und gemeinsamer Kostenanzeige.
4. [x] Unabhängiges Review, betroffene Regressionen, künstlicher Bedienablauf und GitHub-Lieferung. Keine echte Mistral-Qualität behaupten, solange Schlüssel und konkrete Daten-/Kostenfreigabe fehlen.

## Review Focus

Falsche lokale Sensitivitätsgrenze bei separatem Cloudaufruf; zu breite Payload;
Rücknahme während HTTP-Aufruf; Wiederholung nach Timeout/Neustart; zweite Budgetinstanz;
Katalogänderung zwischen Vorschau und Übernahme; lokale Faktenkorrekturen als Cloud-Skill;
versteckte Aktivierung oder unlesbare technische Fehlermeldungen.

## Noch getrennt nachzuweisen

Explizite neue Lernbitten im Gespräch bleiben zunächst auf dem vorhandenen lokalen/manualen Weg.
Die gemeinsame Vorschau-/Ausführungsschicht soll danach auch diesen Eingangsweg aufnehmen.
Persönliche Mistral-Probe, Mac-Update und Alltagsabnahme sind keine Ergebnisse der simulierten HTTP-Tests.

Review und künstliche Bedienprüfung abgeschlossen; siehe [Prüfprotokoll](../../runs/2026-11-04-mistral-workflow-learning/README.md).
Als [Draft-PR #121](https://github.com/Icarus-health/kingfisher-app/pull/121) auf der noch offenen Abhängigkeit #120 geliefert. P2/P5 des Gesamtplans bleiben offen.

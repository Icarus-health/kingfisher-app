# Wiederherstellung: vorhandene Stände vor Freigabe vergleichen

Teil von P5 des freigegebenen Produktplans. Die bestehende historische Ansicht
bewahrt Daten, stellt aber noch keinen regulären Arbeitsbestand her.

## Entscheidung und Alternativen

Eine pauschale Entfernung der Restore-Markierung würde alte Quellen-, Skill-
und Cloudfreigaben zurückbringen. Eine automatische Vereinigung von SQLite-
Tabellen könnte Beziehungen und Nutzerkorrekturen beschädigen. Daher zuerst
ein ausschließlich lesender, begrenzter Vergleich aller gesicherten Bereiche.
Dies ist eine Implementierungsentscheidung innerhalb des autonomen Auftrags,
keine zusätzliche Nutzerauswahl und keine Änderung der Ziellinie.

## Vertrag dieser Lieferung

- Authentifiziertes POST mit leerem Body, ausschließlich im Inspection-Modus.
  Ohne Token kein Prüfzugriff. Keine frei wählbaren Dateipfade.
- Inventar aus der zentralen Sicherungs-Allowlist; bekannte beiseitegelegte
  Zeitgruppen einzeln vergleichen, keine davon als aktuelle Wahrheit ausgeben.
- Nur reguläre, unveränderte und abgeschlossene SQLite-Dateien prüfen.
  WAL/SHM/Journal, Symlinks, beschädigte/neue Schemas und Arbeitslimits ergeben
  einen sichtbaren ungeklärten Befund. Keine Store-Konstruktoren/Migrationen.
- Dateiprüfsummen, Schemastände, Tabellenzahlen und bei eindeutigem Schlüssel
  gleiche/geänderte/nur-einseitig-vorhandene Zeilen. Keine Inhalte, Identitäten,
  Schlüssel oder rohen SQLite-Fehler in Bericht und Logs.
- Ein Bericht ist Belege für einen Vergleich, niemals eine Freigabe.
  `operational`, `activation_allowed` und `comparison_complete` bleiben false.
  Fehlende spätere Änderungen sind grundsätzlich nicht beweisbar.
- Oberfläche: „Sicherung prüfen“, verständliche Zusammenfassung, Befunde
  aufklappbar. Bestehende historische Datenansicht weiter verfügbar.

## Danach weiterhin erforderlich

Zustandsabgleich mit aktuellen Korrekturen/Entzügen und gesonderte Arbeitskopie;
frische Konten-, Modell-, Kosten- und Aktionsfreigaben; sauberer Start ohne
geerbte Umgebungs- oder Betriebssystemschlüssel; normale Aufgabe neu speichern
und nach Neustart abrufen. Erst danach kann die operative Wiederherstellung
abgenommen werden. Der jetzige Bericht ersetzt diese Schritte ausdrücklich nicht.

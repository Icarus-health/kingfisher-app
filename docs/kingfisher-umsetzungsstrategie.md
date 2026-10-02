# Icarus mit der Kingfisher-Oberfläche umsetzen

Stand: 5. September 2026. Arbeitsbasis: Kingfisher
`integration/icarus-main`, Commit `7bfdd3238ad212b55a1109deac45b7bd4e1cd683`.

## Verbindliches Ziel

Der bereits ausgearbeitete Funktionsumfang von **Icarus ist der Produktumfang**.
**Kingfisher liefert die verbindliche Oberfläche.** Das Ergebnis soll sämtliche
vereinbarten Icarus-Funktionen in dieser Oberfläche zugänglich machen. Das
Graphengedächtnis ist die Kernfunktion und die gemeinsame Grundlage aller
weiteren Funktionen. Mail, Kalender, Dateien und Gespräche liefern Rohquellen;
bestätigtes, korrigierbares Wissen verbindet Menschen, Projekte und persönliche
Kontexte. Briefings, Planung, Werkzeuge und Agenten bauen darauf auf.
Quellenbeobachtung und bestätigtes Wissen bleiben dabei getrennt.

Fachliche Referenz ist `docs/00-produktvision.md`, insbesondere die zwölf Säulen
in Abschnitt 7, ergänzt um `docs/20-icarus-2.0.md` und die bestehenden
Funktionskontrakte. Der konkrete Abgleich steht in
[icarus-kingfisher-funktionsabgleich.md](icarus-kingfisher-funktionsabgleich.md).
Eine definierte Funktion, vorhandener Backend-Code und ein fertig nutzbarer
Ablauf sind drei verschiedene Zustände und werden getrennt nachgewiesen.

Visuelle Referenz bleibt `design-source/06_Screens/Approved`, danach das
Asset-Manifest und die übrigen freigegebenen Quellen. Der zugehörige
Kingfisher-Ordner in Google Drive wurde bestätigt. Eine Backend-Änderung ist
kein Anlass, das UI neu zu gestalten. Für einen fehlenden freigegebenen Zustand
gilt das bestehende Verfahren aus `CONTRIBUTING.md`.

## Vorgehen bis zum vollständigen Produkt

| Paket | Ergebnis | Abnahme |
| --- | --- | --- |
| 0 – Bestand und Funktionsparität | Icarus-Funktionskatalog mit Zuordnung zu Backend, Kingfisher-Screen und offenen Arbeiten; Abgleich mit dem noch nicht hochgeladenen PC-Stand | Jede vereinbarte Funktion hat eine Zeile und einen Zustand; lokale Arbeit ist berücksichtigt |
| 1 – Verlässliches Gedächtnis | Bestehende Quellen- und Speicherfunktionen übernehmen; stabile Identitäten, mehrere Beziehungen, Belege, zeitliche Gültigkeit, Bestätigung und Korrektur verbinden | Gleiche Namen bleiben unterscheidbar; mehrere Projekte/private Kontakte koexistieren; falsches Wissen kann widerrufen werden; Wiederanlauf und Restore erhalten diese Zustände |
| 2 – Icarus im täglichen Kingfisher-Ablauf | Gespräche, Posteingang, Kalender, Aufgaben, Projekte, Delegation, Briefing und Entscheidungen über die bestehenden APIs einbinden | Jeder Ablauf vom sichtbaren Einstieg bis zum gespeicherten Ergebnis im Docker-Build geprüft; Referenzscreens im Browser verglichen |
| 3 – Chief of Staff und Agenten | Bestehende Priorisierung, Regeln, Freigaben, Modellanbindung und Werkzeuge integrieren; fehlende Teile des vereinbarten Routings und dauerhafter Abläufe ergänzen | Begründete Prioritäten, nachvollziehbare Tool-Auswahl, Freigaben und kontrollierter Wiederanlauf; keine automatische Übernahme von Vermutungen als Fakten |
| 4 – Gesamter vereinbarter Umfang | Übrige Katalogpunkte einschließlich Außenwelt, Konnektoren, Browser/Computer, Sprache, Mobilität, Ziele und Gewohnheiten nach ihrem dokumentierten Stand fertigstellen | Für jede Katalogzeile ist der echte Nutzungsablauf nachgewiesen; geplante Funktionen sind nicht lediglich durch einen Button vertreten |
| 5 – Produktabnahme | Einrichtung, Berechtigungen, Fehlersituationen, Sicherung/Wiederherstellung und komplette Nutzung zusammenführen | Installation und vollständige Kernabläufe auf sauberer Umgebung und vorhandenem Nutzerbestand; visuelle Abnahme und Regression bestanden |

Die Reihenfolge steuert die Umsetzung; sie verkleinert den Zielumfang nicht.
Vorhandene Icarus-Implementierungen werden möglichst übernommen und über
schmale Adapter angebunden. Divergierte Branches werden funktionsweise geprüft;
ein pauschaler Merge darf keine Kingfisher-Designentscheidungen überschreiben.

## Arbeitsteilung und Kosten

Ein zentraler Verantwortlicher hält Funktionskatalog, Architektur,
Schnittstellen, Designvorgaben und Abnahme zusammen. Günstigere Subagenten
bekommen begrenzte Aufgaben mit benannten Dateien und prüfbarem Ergebnis.

Geeignet sind beispielsweise eine reine Beziehungsregel, ein Adapter, ein
API-Client oder Vertragstests für eine fertige Schnittstelle. Architektur,
Migrationen über mehrere Speicher, Sicherheitsgrenzen, konkurrierende
Schreibvorgänge und die finale Integration bleiben unter zentraler Prüfung.

Jeder Auftrag enthält Ziel, Schnittstelle, erlaubte Dateien, ausgeschlossene
Änderungen und Abnahmekriterium. Ein Subagent erhält den dafür nötigen Kontext;
der komplette Gesprächsverlauf wird nicht pauschal vervielfacht. Es arbeiten
höchstens zwei bis drei Implementierungsagenten gleichzeitig an getrennten
Dateien. Ein weiterer Auftrag beginnt erst, wenn eine unabhängige Aufgabe
vorliegt. Fehler werden gezielt nachgebessert; korrekte Arbeit wird nicht erneut
ausgeführt.

Ein günstigeres Modell kann die Kosten senken. Mehr Agenten sparen jedoch nicht
automatisch Tokens: Übergaben, mehrfach gelesener Kontext, Prüfungen und
Nacharbeit können den Vorteil aufheben. Maßstab sind Kosten pro abgenommenem
Arbeitspaket und Fehlerquote; ohne erfasste Verbrauchsdaten wird keine
Ersparnis in Prozent behauptet.

Im ersten Paket wurden Identitätsregistry, Beziehungsregeln und zugehörige
Tests an `gpt-5.6-luna` delegiert. Die Integration, Korrekturpfade und Abnahme
wurden zentral bearbeitet.

## Der aktuelle Entwurf

Der begleitende Code ist ein überprüfbarer Teil von Paket 1:

- Stabile Entitätskennungen mit separaten Anzeigenamen. Gleichnamige Kontakte
  werden nicht automatisch zusammengelegt. Quellenbindungen enthalten Quelle,
  Konto und native Kennung; Umbenennen erhält die Identität.
- Belegte Kandidaten tragen optional ein Beziehungsziel, ein Gültigkeitsintervall
  und ausdrücklich deklarierte Abhängigkeiten zu anderen Wissensaussagen.
- Bekannte mehrwertige Beziehungen wie Projektzugehörigkeit und Freundschaft
  können nebeneinander bestehen. Statuskonflikte bleiben explizit zu klären;
  unbekannte Prädikate bleiben konservativ.
- Bestätigungen prüfen Konflikte innerhalb einer SQLite-Schreibtransaktion,
  auch bei konkurrierenden Verbindungen. Mehrwertige Beziehungen lassen sich
  ausdrücklich ersetzen oder einzeln widerrufen.
- Widerruf/Ersetzung markieren transitiv abhängiges Wissen als strittig.
  Ungültige Grundlagen dürfen keine neuen Bestätigungen tragen. Abgelaufene
  Intervalle werden aus dem aktuellen Abruf ausgeschlossen.
- Ein Änderungsjournal dokumentiert Annahme, Ersetzung, Widerruf und Entwertung.
  Alte Inhalte bleiben historisch lesbar. Widerruf bedeutet keine physische
  Löschung persönlicher Daten.
- Der abgeleitete Graph erhält direkte, belegte Beziehungen zwischen stabilen
  Kennungen. Inaktive Beziehungen bleiben als Claim-Historie verfügbar.
- Der lokale Modellkontext prüft Belege erneut. Zusammenfassungen sind keine
  Wissensquelle. Nach einer Gedächtnisrevision wird veralteter Gesprächskontext
  konservativ abgeschnitten; sichtbare Gesprächsnachrichten bleiben bestehen.
  Änderungen während einer Modellantwort verwerfen die veraltete Antwort und
  deren noch nicht ausgeführte Tool-Aufrufe.

Registry und Journal liegen in der bestehenden `knowledge.sqlite3` (Schema v3).
Die additive Migration bewahrt alte Claim-Dokumente. Es kommt kein
Datenbankdienst hinzu. Die vorhandene Gesamtsicherung umfasst diese Datei.

Neue HTTP-Verträge unter `/api/v1/memory/`: `registry` mit Suche, Anlage,
Umbenennen, Profil und expliziten Quellenbindungen; `claims/{id}/retract`;
`changes`. Kandidaten unterstützen `target_ref`, `valid_from`, `valid_until`
und `depends_on`. Alle verwenden die vorhandene Zugriffskontrolle.

## Noch keine vollständige Produktabnahme

Dieser Entwurf verändert keine UI-Komponente und ersetzt nicht die
Funktionsparitätsliste. Die neuen Identitäts- und Korrekturverträge müssen noch
in freigegebene Kingfisher-Abläufe eingebunden werden. Die alte Namensprojektion
und die bisherigen Gesprächsentwürfe bleiben als kompatible Übergänge bestehen;
Importadapter verwenden die neue Registry noch nicht durchgängig. Ein
automatisches Zusammenführen alter Namenskennungen ist ausdrücklich nicht
enthalten.

Abhängigkeiten werden explizit angegeben. Automatisches Erkennen aller
inhaltlichen Ableitungen, vollständiges Vergessen einschließlich sämtlicher
Kopien, semantische Graphsuche und neue proaktive Arbeitsabläufe bleiben eigene
Katalogaufgaben. Das konservative Abschneiden alten Modellverlaufs kann
zusätzliche Rückfragen verursachen und soll später durch eine gezielte
Neuberechnung belegter Kontexte verfeinert werden.

Der PC-Stand des Nutzers ist noch nicht verfügbar. Änderungen werden deshalb
als separater Entwurf gegen `integration/icarus-main` bereitgestellt. Ein Merge
und eine fertige UI/Docker-Produktabnahme sind damit nicht behauptet. In dieser
Umgebung ist Docker nicht installiert; die geprüften Backend-Verträge laufen
lokal mit SQLite und FastAPI-Testclient. Die freigegebenen Drive-Binärdateien
konnten über den verfügbaren Connector nicht lokal materialisiert werden;
eine neue visuelle Abnahme wurde daher nicht durchgeführt.

## Nachweis für diesen Entwurf

219 Tests bestanden: die verpflichtenden Suites `test_context`, `test_egress`,
`test_agent`, `test_kingfisher`, `test_claims` und `test_graph`, ergänzt um
Registry, Beziehungsregeln, Kandidatenmetadaten, Graphintegration,
Korrekturkontext, Backup, Migrationen und HTTP-Server. Zwei bestehende
Abkündigungswarnungen betreffen FastAPI/Starlette-Testabhängigkeiten.

Die gezielten Szenarien umfassen zwei konkurrierende SQLite-Verbindungen,
transitive Entwertung nach Neustart, alte v2-Dokumente nach Migration,
Gesprächsverlauf nach Widerruf und Sicherung/Wiederherstellung von Identitäten,
Quellenbindungen und Änderungsjournal. Eine absichtlich entfernte Entwertung
ließ den dafür vorgesehenen Test fehlschlagen; nach Wiederherstellung bestand
die gemeinsame Suite. Damit ist dieses Backend-Paket geprüft, nicht der
vollständige Funktionsumfang oder eine visuelle Produktabnahme.

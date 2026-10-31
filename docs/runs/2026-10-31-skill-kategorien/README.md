# Skill-Einordnung und Abschlussprüfung, 31.10.2026

## Änderung

Bestehende Ablaufbibliothek um Zweckkategorien und optionale Anwendungskontexte
ergänzt. Eigene Skills bleiben immer bei Bedarf und bis zur Bestätigung inaktiv.
Bestehende Datenbank-/Markdownfassungen werden nicht umgeschrieben; Legacy-
Vorgaben und normalisierte Wiederverwendung verhindern zusätzliche Kopien.
Die Auswahl lädt nur den eindeutig passenden Volltext; Bereich, Auslöser und
positiver Kontext werden gemeinsam geprüft. Quellen- und Versionsprüfungen
bleiben unverändert bindend. Kein zusätzlicher Modellaufruf für Kategorienwahl
oder Suchfilter; der bestehende Lernaufruf schlägt die Metadaten mit vor.

Die bestehende Einstellungsansicht hat Suche und Kategoriefilter. Direkte
Prüfziele bleiben sichtbar, neue Fassungen behalten ihre Einordnung. Keine neue
Ansicht, Abhängigkeit, Modellrolle oder Kopie pro Akte.

## Nachweise

- Ausgangsbasis: 61 vorhandene Verfahrens-/Runtime-/Modelladaptertests bestanden.
- Neue Backendprüfungen zunächst 9 Fehlschläge; anschließend Legacy-Export,
  Standardkategorien, Kontexte, Konflikte, Versionen, Quellenentzug und Metadaten-
  Katalog geprüft. HTTP-Kette mit künstlichem lokalen Antwortdouble deckt Lernen,
  Übernahme, tatsächlichen Agentkontext, Kontextwechsel und entzogene Quelle nach
  Store-Neustart ab. Keine tatsächliche Modellqualität daraus ableiten.
- Neue UI-Prüfungen zunächst 3 Fehlschläge; Filter, unverdeckte Ziel-ID und
  Metadatenerhalt bei neuer Fassung anschließend erfolgreich. Nach Review 12/12
  gezielte UI-Prüfungen bestanden; vollständige Suite folgt unten.
- Unabhängiges Review fand positive Kontextwahl aus Inline-Zitaten/nachgestellter
  Verneinung und ungeordnete Wortgruppen. Sieben neue Gegenproben schlugen vor
  der Korrektur fehl (einschließlich tatsächlichem JSON-Listenbudget); danach
  99/99 betroffene Backendprüfungen bestanden. Suche bei Grundverfahren ebenfalls
  durch RED→GREEN abgesichert. Keine offene Review-Feststellung behalten.
- Browserprüfung im getrennten Docker-Bild mit drei künstlichen Vorschlägen:
  direkte Ziel-ID, Filterwechsel, Suche, Übernahme, Rücknahme und Metadatenerhalt.
  Viewports 900 und 1280 Pixel. Persönliche Konten und Quellen nicht eingebunden.
- Vollständiger Backendversuch unter der Sandbox war ungültig: lokale DNS-/HTTP-
  Attrappen dürfen dort keine Sockets binden (`test_anbieter_erkennen`, eindeutig
  reproduziert; 372 Tests bis zur ersten blockierten Attrappe bestanden). Der
  ältere Gesamtversuch wurde nach weiterem Fix unterbrochen und ist kein grüner
  Nachweis. Abschließende Suite läuft mit freigegebenen lokalen Test-Sockets.
- Den unveränderten 24-Mail-/16-Fragen-Katalog inhaltlich vorgeprüft; ergänzende
  [Einzelabnahme](../../evaluations/memory-quality/intake/REVIEW.md) benennt auch
  Fehler, die reine Wort-/Statusprüfungen übersehen (etwa beliebiger erfundener
  Freitag oder richtige Uhrzeit bei falscher Terminrolle). Keine Sollwerte auf
  ein Modellergebnis angepasst; vollständiger Modelllauf weiterhin offen.
- Der Verfahrensstand bestand vollständig 8.372 Backendtests und 26 Subtests,
  ein Plattformfall ausgelassen. Danach fiel bei der echten nativen Prüfung eine
  zusätzliche Lücke im alten Teilnehmerindex auf: Domain-/Funktionsanzeigenamen,
  `pay` und Kampagnen-Rückkanäle konnten als Personen erscheinen. Die zusätzliche
  **lesende** Qualitätsmarkierung stellt sie zur Prüfung, verändert aber keine
  IDs, Labels, Quellen oder bestätigten Personen. Eigenes unabhängiges Review;
  Überschneidung mit eindeutig technischen Adressen durch RED→GREEN korrigiert.
  99 betroffene Qualitäts-/Zuordnungs-/Zusammenführungsprüfungen bestanden. Die
  kombinierte Gesamtsuite wird unten gesondert ausgewiesen.

## Persönlicher Mac

Die veröffentlichte Basis 1.0.33 wurde über den normalen Updateknopf installiert;
Version im Fenster und tatsächlicher Container stimmen. Vollständige Sicherung
vor dem Wechsel vorhanden. Alle 18 bestehenden Datenbanken bestanden danach
eine begrenzte lesende Integritätsprüfung. Zwei Konten erhalten, Großimport
weiterhin global pausiert. Dieser Nachweis enthält noch nicht die neue
Kategorisierung dieses Branches.

Die Vor-Update-Sicherung wurde zusätzlich mit der tatsächlichen Restore-
Vorprüfung gelesen: alle 20 enthaltenen Dateien (18 Datenbanken) bestehen
Prüfsummen- und Integritätsprüfung. Keine Wiederherstellung im persönlichen
Bestand ausgelöst. Das Fenster bestätigt weiterhin das eingerichtete Qwen9B;
Lesen der Modellwahl ist kein abgeschlossener Modelllauf.

## Offene Abnahme

Vollständige reale Qwen9B-/BGE-M3-Probe mit inhaltlicher Einzelbewertung, gemischte
echte Mailstichprobe vor Großimport und persönliche Alltagswoche bleiben offen.
Die freie Reserve lag vor dieser Umsetzung bei 41 Prozent, unter der vorher
festgelegten sicheren Startgrenze (Stufe 1, mindestens 48 Prozent stabile
Reserve). Keine Modellprobe gestartet, keine fremden Programme beendet, keine
Schutzgrenze gelockert und kein Cloudanbieter verwendet.

## Abschließende Ergebnisse

| Prüfung | Ergebnis |
|---|---|
| Kombinierte Backend-Gesamtsuite einschließlich Teilnehmerkorrektur | 8.376 bestanden, 1 Plattformfall ausgelassen, 26 Subtests bestanden; zwei Prozesse, 682,34 Sekunden |
| Gesamte UI-Suite | 969/969 bestanden |
| Gezielte Verfahrens-/Kontextprüfungen | 99/99 bestanden |
| Personenqualität, Zuordnung und Zusammenführung | 99/99 bestanden |
| Frische Mail-Qualitätsinstrumente | 38/38 bestanden |
| Version, Update, Sicherung und Restore-Prüfungen | 110/110 bestanden |
| Web-Build und Assetvertrag | bestanden; 11 Dateien und 14 Icons |
| Unabhängige Reviews | beide abgeschlossen; alle konkreten Hinweise mit Gegenproben korrigiert |

Ein Start des letzten getrennten Testcontainers scheiterte anschließend an
vollem Docker-Speicher (Host hatte ausreichend freien Platz). Eigene aktuelle
Testdaten auf dem Host gesichert, eigene Testcontainer/-bilder und ungetaggte,
unreferenzierte Zwischenbilder aus den protokollierten eigenen Builds freigegeben.
Auch eindeutig zugeordnete alte synthetische Testcontainer wurden entfernt;
**kein Datenvolume**, persönlicher Container oder Pilot-/Vorher-Stand gelöscht.
Danach wieder rund 1,1 GiB frei. Dies ist keine Behauptung eines erfolgreichen
Starts dieses letzten Containers; abschließender Paket-/Mac-Stand wird nach
Veröffentlichung in der PR-Abnahme festgehalten. Keine Schutzgrenze abgesenkt.

Entscheidungen: vorhandene lokale Providerprüfung auf Metadaten beibehalten;
Einladungen ohne Mailbezug nicht als Mail erraten; Kategorien ordnen, während
Aufgabenbereich/Auslöser/Kontext die Auswahl begrenzen; bestehende explizite
Identitätsbestätigungen haben Vorrang vor neuen lesenden Qualitätsmarkierungen.
Eine domainartige unbestätigte Bezeichnung kann zur Prüfung stehen; sie wird
dadurch weder gelöscht noch einer Organisation als Fakt zugeordnet. Keine neuen
kanonischen Identitätsregeln oder unbeobachteten Dienstvarianten eingeführt.

Erfolgreiche Form-/Runtime-/Browserprüfungen sind keine allgemeine
Fehlerfreiheitsgarantie. Modellqualität und echte Quellenprobe bleiben offen.

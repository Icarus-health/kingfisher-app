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

## Persönlicher Mac

Die veröffentlichte Basis 1.0.33 wurde über den normalen Updateknopf installiert;
Version im Fenster und tatsächlicher Container stimmen. Vollständige Sicherung
vor dem Wechsel vorhanden. Alle 18 bestehenden Datenbanken bestanden danach
eine begrenzte lesende Integritätsprüfung. Zwei Konten erhalten, Großimport
weiterhin global pausiert. Dieser Nachweis enthält noch nicht die neue
Kategorisierung dieses Branches.

## Offene Abnahme

Vollständige reale Qwen9B-/BGE-M3-Probe mit inhaltlicher Einzelbewertung, gemischte
echte Mailstichprobe vor Großimport und persönliche Alltagswoche bleiben offen.
Die freie Reserve lag vor dieser Umsetzung bei 41 Prozent, unter der vorher
festgelegten sicheren Startgrenze (Stufe 1, mindestens 48 Prozent stabile
Reserve). Keine Modellprobe gestartet, keine fremden Programme beendet, keine
Schutzgrenze gelockert und kein Cloudanbieter verwendet.

## Abschließende Ergebnisse

Noch laufende Gesamttests werden vor Veröffentlichung eingetragen. Erfolgreiche
Form-/Runtime-/Browserprüfungen sind keine allgemeine Fehlerfreiheitsgarantie.

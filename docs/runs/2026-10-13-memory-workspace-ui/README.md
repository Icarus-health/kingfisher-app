# Gedächtnisansicht – 13. Oktober 2026

Ausgangsstand: `d138e629fecb379a12add86c67d6396d68645bd9` auf `main`.
Die bestehende Gedächtnisstruktur bleibt erhalten; die Änderung betrifft ihren
Alltagszugang und eine begrenzte, modellfreie Suche in Originaltexten.

## Verhalten

- `/memory` beginnt mit einer zentralen Suche. Menschen und Projekte werden
  nach Namen gefiltert; „Suchen“ sucht zusätzlich wörtlich in Originalquellen,
  Gesprächseingaben und aktuellen Arbeitsnotizen.
- Menschen, Projekte, Dokumente, Themen und Lebensbereiche sind die direkten
  Ansichten. Seltenere Ansichten und Pflege liegen in einem aufklappbaren Bereich.
- Dokumente erscheinen als Liste. Ersetzte, ignorierte und archivierte
  Dokumentfassungen werden nicht als aktuelle Dokumente dargestellt. Historische
  Originale bleiben gespeichert.
- Personenakten beginnen mit Zusammenfassung, zugeordneten offenen Aufgaben und
  Kontaktstand. Lange Akten-/Beziehungsansichten folgen darunter. Datumsangaben
  enthalten das Jahr.
- Suchbegriff, Seite und bekannte Filter bleiben beim Öffnen und Zurückgehen in
  Personen-, Projekt-, Themen-, Organisations- und Ortslisten erhalten. Rückwege
  akzeptieren ausschließlich bekannte lokale Gedächtnisrouten.
- Originalquellen öffnen in einem reinen Lesemodus ohne Beziehungsnachlauf.
  Die bestehende Zuordnung und Berichtigung ist eine separate ausdrückliche Aktion.
- Aufnahme, Sortierung und Vorbereitung der Bedeutungssuche haben getrennte
  Statusangaben. Warte-/Pausenstände, veraltete Zahlen und Ladefehler werden nicht
  als abgeschlossene Verarbeitung oder leere Sammlung ausgegeben.
- Verdächtige automatische Firmen-/Absendernamen werden konservativ zur Prüfung
  eingeordnet. Bestätigte Identitäten, IDs und Originalnamen bleiben erhalten;
  umschließende Anführungszeichen entfallen nur in der sichtbaren Kurzbezeichnung.

## Grenzen der neuen Originalsuche

`GET /api/v1/memory/search` verwendet den bestehenden Zugriffsschutz. Die Suche
benötigt 2–200 Zeichen, arbeitet ohne Modell, ohne semantische Deutung und ohne
Schreibzugriff. Sie durchsucht höchstens 5.000 jüngste verfügbare aktuelle Quellen
und 5.000 zuletzt bearbeitete aktuelle Arbeitsnotizen. Der gemeinsame Trefferrahmen
beträgt standardmäßig 20, maximal 50; Quellen erhalten vor Notizen die Plätze.

Zitate sind unveränderte Originalausschnitte von höchstens 400 Zeichen. Titel- oder
Beteiligten-Treffer zeigen ausdrücklich den Textanfang. Eigene Suchfragen,
entzogene Grundlagen und nicht aktuelle Fassungen werden nicht als Treffer
zurückgebracht. Der Quellenstatus wird vor der Rückgabe erneut geprüft. Begrenzte
oder unvollständige Ergebnisse sind gekennzeichnet. Ein fehlender Treffer bedeutet
nicht, dass die Information im gesamten Archiv fehlt. Diese Suche ersetzt nicht
den bestehenden beleggebundenen Antwortweg und bestätigt keine Tatsachen.

## Prüfung

- UI: 607 Tests bestanden; TypeScript- und Produktionsbuild bestanden. Der
  vorhandene Hinweis auf ein großes JavaScript-Bundle bleibt bestehen.
- Fokussierte Backend-Prüfungen decken Unicode/Originaloffsets, Literalzeichen,
  Entzug, Quellenwechsel während der Anfrage, gewöhnliche Gesprächseingaben,
  Notiztexte, gemeinsame Treffergrenzen und schreibfreien Betrieb ab.
- Ein getrennt gestarteter HTTP-Testbestand mit 35 künstlichen Kontakten,
  einer Testmail, einer Gesprächseingabe, einer Notiz und zwei Dokumentfassungen
  bestätigte die drei getrennten Texttreffer und die negative Kontrolle.
- Ein unabhängiges Review der endgültigen Änderungen fand keine offenen
  wesentlichen Fehler (P1/P2); dessen fokussierte Prüfungen bestanden.
- Vollständiger endgültiger Backend-Lauf: 6.492 Tests und 26 Untertests bestanden,
  ein Test übersprungen, zwei Hinweise; Dauer 909,71 Sekunden. Dieser Lauf enthält
  die endgültige Originalsuche einschließlich Notiz-/Gesprächstexten und die
  Kennzeichnung aktueller Dokumentfassungen.

## Noch offene Bedienabnahme

Die Computersteuerung verweigert den Testzugriff durch eine gespeicherte
Browserfreigabe, auch nach Zustimmung und erneuter Verbindung. Deshalb sind
Screenshots, echtes Klicken, Tastatur-/Größenprüfung und ein neuer nativer
Fensternachweis noch nicht bestätigt. Der Testbestand enthält ausschließlich
künstliche Daten. Die installierte Mac-Fassung bleibt vorerst 1.0.7; es wurde
kein Update, Import-Neustart oder Wechsel persönlicher Daten vorgenommen.

Keine persönlichen Quellen, Zugriffsschlüssel oder privaten UI-Aufnahmen wurden
in diesen Nachweis aufgenommen. Kein Cloudmodell wurde für diese Änderung benutzt.
